#!/usr/bin/env python3
"""Local web interface for validating MusicSorter metadata."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DEFAULT_DB_PATH = Path("d_music_inventory.db")
COLLECTION_FOLDERS = {"itunes", "itunes music", "music", "just music"}
REVIEW_ACTIONS = {
    "accept_metadata": "accepted_metadata",
    "accept_folder": "accepted_folder",
    "various_artists": "various_artists",
    "unknown": "unknown",
    "needs_review": "needs_review",
    "skip": "skipped",
}


def guess_folder_artist(relative_path: str) -> str:
    parts = Path(relative_path).parts
    if len(parts) < 2:
        return ""
    folders = list(parts[:-1])
    while folders and folders[0].strip().casefold() in COLLECTION_FOLDERS:
        folders.pop(0)
    return folders[0].strip() if folders else ""


def dict_row(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict[str, object]:
    return {description[0]: row[index] for index, description in enumerate(cursor.description)}


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = dict_row
    return connection


def ensure_schema(db_path: Path) -> None:
    with connect(db_path) as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(files)")}
        additions = {
            "reviewed_artist": "TEXT",
            "reviewed_album": "TEXT",
            "reviewed_title": "TEXT",
            "review_status": "TEXT NOT NULL DEFAULT 'unreviewed'",
            "review_notes": "TEXT",
            "reviewed_at": "TEXT",
        }
        for column, column_type in additions.items():
            if column not in columns:
                connection.execute(f"ALTER TABLE files ADD COLUMN {column} {column_type}")
        connection.commit()


def status_counts(db_path: Path) -> dict[str, dict[str, int]]:
    with connect(db_path) as connection:
        metadata_rows = connection.execute(
            """
            SELECT COALESCE(metadata_status, 'unknown') AS status, COUNT(*) AS count
            FROM files
            WHERE is_audio = 1
            GROUP BY COALESCE(metadata_status, 'unknown')
            ORDER BY status
            """
        ).fetchall()
        review_rows = connection.execute(
            """
            SELECT COALESCE(review_status, 'unreviewed') AS status, COUNT(*) AS count
            FROM files
            WHERE is_audio = 1
            GROUP BY COALESCE(review_status, 'unreviewed')
            ORDER BY status
            """
        ).fetchall()
    return {
        "metadata": {row["status"]: row["count"] for row in metadata_rows},
        "review": {row["status"]: row["count"] for row in review_rows},
    }


def track_query(db_path: Path, params: dict[str, list[str]]) -> dict[str, object]:
    metadata_status = params.get("status", ["metadata-conflict"])[0]
    review_status = params.get("review", ["all"])[0]
    search = params.get("q", [""])[0].strip()
    page = max(int(params.get("page", ["1"])[0] or 1), 1)
    limit = min(max(int(params.get("limit", ["60"])[0] or 60), 10), 200)
    offset = (page - 1) * limit

    where = ["is_audio = 1"]
    values: list[object] = []
    if metadata_status and metadata_status != "all":
        where.append("COALESCE(metadata_status, 'unknown') = ?")
        values.append(metadata_status)
    if review_status and review_status != "all":
        where.append("COALESCE(review_status, 'unreviewed') = ?")
        values.append(review_status)
    if search:
        where.append(
            """
            (relative_path LIKE ? OR filename LIKE ? OR COALESCE(artist, '') LIKE ? OR
             COALESCE(album_artist, '') LIKE ? OR COALESCE(album, '') LIKE ? OR
             COALESCE(title, '') LIKE ? OR COALESCE(containing_directory, '') LIKE ?)
            """
        )
        values.extend([f"%{search}%"] * 7)

    where_sql = " AND ".join(where)
    with connect(db_path) as connection:
        total = connection.execute(
            f"SELECT COUNT(*) AS count FROM files WHERE {where_sql}", values
        ).fetchone()["count"]
        rows = connection.execute(
            f"""
            SELECT
                id, relative_path, filename, extension, containing_directory,
                artist AS tag_artist, album_artist, album, title, track_number,
                disc_number, year, genre, metadata_status, metadata_error,
                confidence, reviewed_artist, reviewed_album, reviewed_title,
                review_status, review_notes, reviewed_at
            FROM files
            WHERE {where_sql}
            ORDER BY
                CASE COALESCE(review_status, 'unreviewed') WHEN 'unreviewed' THEN 0 ELSE 1 END,
                relative_path
            LIMIT ? OFFSET ?
            """,
            [*values, limit, offset],
        ).fetchall()

    for row in rows:
        row["folder_artist_guess"] = guess_folder_artist(str(row.get("relative_path") or ""))

    return {
        "tracks": rows,
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit,
    }


def update_review(db_path: Path, payload: dict[str, object]) -> dict[str, object]:
    track_id = int(payload.get("id") or 0)
    action = str(payload.get("action") or "")
    notes = str(payload.get("notes") or "").strip()
    if track_id <= 0:
        raise ValueError("Missing track id")
    if action not in REVIEW_ACTIONS:
        raise ValueError("Unknown review action")

    with connect(db_path) as connection:
        track = connection.execute(
            """
            SELECT id, relative_path, artist AS tag_artist, album_artist, album, title
            FROM files
            WHERE id = ? AND is_audio = 1
            """,
            (track_id,),
        ).fetchone()
        if not track:
            raise ValueError("Track not found")

        folder_artist = guess_folder_artist(str(track.get("relative_path") or ""))
        if action == "accept_metadata":
            reviewed_artist = str(
                payload.get("reviewed_artist")
                or track.get("album_artist")
                or track.get("tag_artist")
                or ""
            ).strip()
        elif action == "accept_folder":
            reviewed_artist = folder_artist
        elif action == "various_artists":
            reviewed_artist = "Various Artists"
        elif action == "unknown":
            reviewed_artist = "Unknown Artist"
        else:
            reviewed_artist = str(payload.get("reviewed_artist") or "").strip()

        reviewed_album = str(payload.get("reviewed_album") or track.get("album") or "").strip()
        reviewed_title = str(payload.get("reviewed_title") or track.get("title") or "").strip()
        review_status = REVIEW_ACTIONS[action]
        reviewed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        connection.execute(
            """
            UPDATE files
            SET reviewed_artist = ?, reviewed_album = ?, reviewed_title = ?,
                review_status = ?, review_notes = ?, reviewed_at = ?
            WHERE id = ?
            """,
            (reviewed_artist, reviewed_album, reviewed_title, review_status, notes, reviewed_at, track_id),
        )
        connection.commit()

    return {
        "ok": True,
        "id": track_id,
        "review_status": review_status,
        "reviewed_artist": reviewed_artist,
        "reviewed_at": reviewed_at,
    }


HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MusicSorter Review</title>
  <style>
    :root { --bg:#f6f7f9; --panel:#fff; --ink:#1f2933; --muted:#667085; --line:#d8dee8; --accent:#1b6f7a; --accent2:#734b9b; --ok:#207044; --bad:#a33434; --shadow:0 1px 2px rgba(16,24,40,.08); }
    * { box-sizing:border-box; }
    body { margin:0; font-family:"Segoe UI",system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--ink); font-size:14px; }
    button,input,select,textarea { font:inherit; } button { cursor:pointer; }
    .app { min-height:100vh; display:grid; grid-template-columns:280px minmax(0,1fr); }
    aside { border-right:1px solid var(--line); background:#eef2f6; padding:16px; display:flex; flex-direction:column; gap:16px; }
    main { min-width:0; display:grid; grid-template-rows:auto minmax(0,1fr); }
    h1 { font-size:20px; line-height:1.2; margin:0; letter-spacing:0; } h2 { font-size:13px; text-transform:uppercase; color:var(--muted); margin:0 0 8px; letter-spacing:.04em; }
    .toolbar { padding:14px 18px; border-bottom:1px solid var(--line); background:var(--panel); display:grid; grid-template-columns:minmax(180px,1fr) 190px 170px auto auto; gap:10px; align-items:center; }
    .search,select,textarea,.edit-field { width:100%; border:1px solid var(--line); background:#fff; color:var(--ink); border-radius:6px; min-height:36px; padding:8px 10px; }
    textarea { min-height:72px; resize:vertical; }
    .button { min-height:36px; border:1px solid var(--line); background:#fff; color:var(--ink); border-radius:6px; padding:8px 10px; box-shadow:var(--shadow); white-space:nowrap; }
    .button.primary { background:var(--accent); color:#fff; border-color:var(--accent); } .button.secondary { background:var(--accent2); color:#fff; border-color:var(--accent2); } .button.good { background:var(--ok); color:#fff; border-color:var(--ok); } .button.warn { background:#fff8eb; color:#6f4200; border-color:#e6b15c; } .button.danger { background:#fff2f2; color:var(--bad); border-color:#e3a3a3; }
    .stats { display:grid; gap:8px; } .stat-row { display:flex; justify-content:space-between; gap:10px; padding:8px 10px; border:1px solid var(--line); background:#fff; border-radius:6px; box-shadow:var(--shadow); } .stat-row strong { font-variant-numeric:tabular-nums; } .muted { color:var(--muted); }
    .workspace { min-height:0; display:grid; grid-template-columns:minmax(360px,46%) minmax(360px,54%); } .list-pane,.detail-pane { min-width:0; min-height:0; overflow:auto; } .list-pane { border-right:1px solid var(--line); background:#fbfcfd; }
    .track-row { width:100%; display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px; text-align:left; border:0; border-bottom:1px solid var(--line); background:transparent; padding:12px 14px; } .track-row:hover,.track-row.active { background:#e9f3f5; }
    .track-title { font-weight:650; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; } .track-path { color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-top:4px; }
    .pill { display:inline-flex; align-items:center; min-height:24px; border-radius:999px; padding:3px 8px; border:1px solid var(--line); background:#fff; font-size:12px; white-space:nowrap; } .pill.conflict { border-color:#dfb46d; background:#fff8eb; color:#6f4200; } .pill.confirmed { border-color:#93c5aa; background:#eef9f2; color:#155f37; } .pill.error { border-color:#df9a9a; background:#fff2f2; color:var(--bad); }
    .detail-pane { padding:18px; background:var(--bg); } .detail-head { display:flex; justify-content:space-between; gap:12px; margin-bottom:16px; align-items:flex-start; } .detail-title { font-size:18px; font-weight:700; margin-bottom:4px; overflow-wrap:anywhere; } .detail-subtitle { color:var(--muted); overflow-wrap:anywhere; }
    .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; } .field { background:var(--panel); border:1px solid var(--line); border-radius:6px; box-shadow:var(--shadow); padding:10px; min-width:0; } .field label { display:block; color:var(--muted); font-size:12px; margin-bottom:5px; } .field div { overflow-wrap:anywhere; min-height:20px; } .wide { grid-column:1/-1; }
    .actions { margin-top:14px; display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; } .review-editor { margin-top:14px; display:grid; gap:8px; } .pager { display:flex; align-items:center; gap:8px; justify-content:flex-end; } .empty { padding:28px; color:var(--muted); }
    @media (max-width:980px) { .app { grid-template-columns:1fr; } aside { border-right:0; border-bottom:1px solid var(--line); } .toolbar { grid-template-columns:1fr 1fr; } .workspace { grid-template-columns:1fr; } .list-pane { border-right:0; border-bottom:1px solid var(--line); max-height:44vh; } .grid,.actions { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <div class="app"><aside><div><h1>MusicSorter Review</h1><div class="muted" id="summaryText">Loading library state</div></div><section><h2>Metadata</h2><div class="stats" id="metadataStats"></div></section><section><h2>Review</h2><div class="stats" id="reviewStats"></div></section></aside>
  <main><div class="toolbar"><input class="search" id="searchInput" placeholder="Search artist, album, title, path" autocomplete="off"><select id="statusFilter" aria-label="Metadata status"><option value="metadata-conflict">Conflicts</option><option value="missing-metadata">Missing metadata</option><option value="metadata-error">Metadata errors</option><option value="confirmed">Confirmed</option><option value="all">All audio</option></select><select id="reviewFilter" aria-label="Review status"><option value="all">Any review</option><option value="unreviewed">Unreviewed</option><option value="accepted_metadata">Accepted tags</option><option value="accepted_folder">Accepted folder</option><option value="various_artists">Various Artists</option><option value="needs_review">Needs review</option><option value="skipped">Skipped</option></select><button class="button" id="refreshButton" title="Refresh">Refresh</button><div class="pager"><button class="button" id="prevButton" title="Previous page">Prev</button><span class="muted" id="pageText">Page 1</span><button class="button" id="nextButton" title="Next page">Next</button></div></div><div class="workspace"><section class="list-pane" id="trackList"></section><section class="detail-pane" id="detailPane"><div class="empty">Select a track to validate it.</div></section></div></main></div>
  <script>
    const state = { tracks: [], selected: null, page: 1, pages: 1, total: 0, searchTimer: null };
    const $ = id => document.getElementById(id);
    const text = value => value === null || value === undefined || value === '' ? 'None' : String(value);
    const escapeHtml = value => text(value).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
    const statusClass = status => status === 'confirmed' ? 'confirmed' : status === 'metadata-error' ? 'error' : (status === 'metadata-conflict' || status === 'missing-metadata') ? 'conflict' : '';
    async function fetchJson(url, options) { const response = await fetch(url, options); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || 'Request failed'); return payload; }
    async function loadStats() { const stats = await fetchJson('/api/stats'); renderStats('metadataStats', stats.metadata); renderStats('reviewStats', stats.review); }
    function renderStats(id, stats) { const entries = Object.entries(stats || {}); $(id).innerHTML = entries.map(([key,count]) => `<div class="stat-row"><span>${escapeHtml(key)}</span><strong>${count}</strong></div>`).join('') || '<div class="muted">No rows</div>'; }
    async function loadTracks() { const params = new URLSearchParams({status:$('statusFilter').value, review:$('reviewFilter').value, q:$('searchInput').value, page:String(state.page), limit:'60'}); const result = await fetchJson('/api/tracks?' + params.toString()); state.tracks = result.tracks; state.total = result.total; state.pages = Math.max(result.pages, 1); state.page = result.page; $('summaryText').textContent = `${state.total} matching tracks`; $('pageText').textContent = `Page ${state.page} of ${state.pages}`; $('prevButton').disabled = state.page <= 1; $('nextButton').disabled = state.page >= state.pages; renderList(); if (state.tracks.length) selectTrack(state.tracks[0].id); else renderEmpty(); }
    function renderList() { $('trackList').innerHTML = state.tracks.map(track => `<button class="track-row ${state.selected && state.selected.id === track.id ? 'active' : ''}" data-id="${track.id}"><span><div class="track-title">${escapeHtml(track.title || track.filename)}</div><div class="track-path">${escapeHtml(track.relative_path)}</div></span><span class="pill ${statusClass(track.metadata_status)}">${escapeHtml(track.metadata_status || 'unknown')}</span></button>`).join('') || '<div class="empty">No tracks match the current filters.</div>'; document.querySelectorAll('.track-row').forEach(row => row.addEventListener('click', () => selectTrack(Number(row.dataset.id)))); }
    function renderEmpty() { state.selected = null; $('detailPane').innerHTML = '<div class="empty">No tracks match the current filters.</div>'; }
    function selectTrack(id) { state.selected = state.tracks.find(track => track.id === id) || null; renderList(); renderDetail(); }
    function field(label, value, wide=false) { return `<div class="field ${wide ? 'wide' : ''}"><label>${escapeHtml(label)}</label><div>${escapeHtml(value)}</div></div>`; }
    function renderDetail() { const track = state.selected; if (!track) return renderEmpty(); $('detailPane').innerHTML = `<div class="detail-head"><div><div class="detail-title">${escapeHtml(track.title || track.filename)}</div><div class="detail-subtitle">${escapeHtml(track.relative_path)}</div></div><span class="pill ${statusClass(track.metadata_status)}">${escapeHtml(track.metadata_status || 'unknown')}</span></div><div class="grid">${field('Folder artist guess', track.folder_artist_guess)}${field('Tag artist', track.tag_artist)}${field('Album artist', track.album_artist)}${field('Containing directory', track.containing_directory)}${field('Album', track.album)}${field('Title', track.title)}${field('Track', track.track_number)}${field('Disc', track.disc_number)}${field('Year', track.year)}${field('Genre', track.genre)}${field('Confidence', track.confidence)}${field('Review status', track.review_status || 'unreviewed')}${field('Metadata error', track.metadata_error, true)}</div><div class="review-editor"><input class="edit-field" id="reviewedArtist" value="${escapeHtml(track.reviewed_artist || track.album_artist || track.tag_artist || track.folder_artist_guess || '')}" placeholder="Reviewed artist"><input class="edit-field" id="reviewedAlbum" value="${escapeHtml(track.reviewed_album || track.album || '')}" placeholder="Reviewed album"><input class="edit-field" id="reviewedTitle" value="${escapeHtml(track.reviewed_title || track.title || '')}" placeholder="Reviewed title"><textarea id="reviewNotes" placeholder="Review notes">${escapeHtml(track.review_notes || '')}</textarea></div><div class="actions"><button class="button good" data-action="accept_metadata">Accept tags</button><button class="button primary" data-action="accept_folder">Accept folder</button><button class="button secondary" data-action="various_artists">Various Artists</button><button class="button warn" data-action="needs_review">Needs review</button><button class="button danger" data-action="unknown">Unknown</button><button class="button" data-action="skip">Skip</button></div>`; document.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', () => saveReview(button.dataset.action))); }
    async function saveReview(action) { const track = state.selected; if (!track) return; const result = await fetchJson('/api/review', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id:track.id, action, reviewed_artist:$('reviewedArtist').value, reviewed_album:$('reviewedAlbum').value, reviewed_title:$('reviewedTitle').value, notes:$('reviewNotes').value})}); Object.assign(track, result); const currentIndex = state.tracks.findIndex(item => item.id === track.id); await loadStats(); if (currentIndex >= 0 && currentIndex < state.tracks.length - 1) { state.tracks.splice(currentIndex, 1); renderList(); selectTrack(state.tracks[currentIndex].id); } else { await loadTracks(); } }
    $('refreshButton').addEventListener('click', async () => { await loadStats(); await loadTracks(); }); $('prevButton').addEventListener('click', () => { if (state.page > 1) { state.page--; loadTracks(); } }); $('nextButton').addEventListener('click', () => { if (state.page < state.pages) { state.page++; loadTracks(); } }); $('statusFilter').addEventListener('change', () => { state.page = 1; loadTracks(); }); $('reviewFilter').addEventListener('change', () => { state.page = 1; loadTracks(); }); $('searchInput').addEventListener('input', () => { clearTimeout(state.searchTimer); state.searchTimer = setTimeout(() => { state.page = 1; loadTracks(); }, 250); });
    loadStats().then(loadTracks).catch(error => { $('detailPane').innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`; });
  </script>
</body>
</html>
"""


class ReviewHandler(BaseHTTPRequestHandler):
    db_path: Path

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self) -> None:
        body = HTML.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                self.send_html()
            elif parsed.path == "/api/stats":
                self.send_json(status_counts(self.db_path))
            elif parsed.path == "/api/tracks":
                self.send_json(track_query(self.db_path, parse_qs(parsed.query)))
            elif parsed.path == "/health":
                self.send_json({"ok": True})
            else:
                self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/review":
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            self.send_json(update_review(self.db_path, payload))
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the MusicSorter validation interface.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_schema(args.db)
    ReviewHandler.db_path = args.db
    server = ThreadingHTTPServer((args.host, args.port), ReviewHandler)
    print(f"MusicSorter review app: http://{args.host}:{args.port}")
    print(f"Database: {args.db}")
    server.serve_forever()


if __name__ == "__main__":
    main()
