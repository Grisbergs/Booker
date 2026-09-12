#!/usr/bin/env python3
"""Plan and optionally purge duplicate sorted tracks by metadata."""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB_PATH = Path("d_music_inventory.db")
DEFAULT_REPORT = Path("exports_d_music/duplicate_purge_plan.csv")
DEFAULT_QUARANTINE = Path("/mnt/d/Music/_Duplicate_Quarantine")
SORTED_MARKER = "_Sorted_By_Artist"


@dataclass
class Track:
    id: int
    path: Path
    filename: str
    artist: str
    album: str
    title: str
    size_bytes: int
    modified_at: str | None


@dataclass
class DuplicateAction:
    duplicate_key: str
    action: str
    reason: str
    track: Track
    keep_path: Path
    quarantine_path: Path | None


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path, timeout=60)
    connection.execute("PRAGMA busy_timeout = 60000")
    connection.row_factory = sqlite3.Row
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(files)")}
    additions = {
        "reviewed_artist": "TEXT",
        "reviewed_album": "TEXT",
        "reviewed_title": "TEXT",
        "review_status": "TEXT",
        "duplicate_status": "TEXT",
        "duplicate_group_key": "TEXT",
        "duplicate_keep_path": "TEXT",
        "duplicate_removed_at": "TEXT",
        "duplicate_error": "TEXT",
    }
    for column, column_type in additions.items():
        if column not in columns:
            connection.execute(f"ALTER TABLE files ADD COLUMN {column} {column_type}")
    connection.commit()


def resolve_path(path_text: str) -> Path:
    normalized = path_text.replace("\\", "/")
    if os.name == "nt" and normalized.startswith("/mnt/") and len(normalized) > 6:
        drive = normalized[5].upper()
        return Path(f"{drive}:/{normalized[7:]}")
    return Path(normalized)


def normalize(value: str | None) -> str:
    value = (value or "").casefold().strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"^[\W_]+|[\W_]+$", "", value)
    return value


def duplicate_key(track: Track) -> str:
    return "\x1f".join([normalize(track.artist), normalize(track.title)])


def is_inside_sorted_folder(path: Path) -> bool:
    return SORTED_MARKER in path.parts


def fetch_tracks(connection: sqlite3.Connection) -> list[Track]:
    rows = connection.execute(
        """
        SELECT
            id,
            path,
            filename,
            COALESCE(reviewed_artist, album_artist, artist) AS meta_artist,
            COALESCE(reviewed_album, album) AS meta_album,
            COALESCE(reviewed_title, title) AS meta_title,
            size_bytes,
            modified_at
        FROM files
        WHERE is_audio = 1
          AND COALESCE(reviewed_artist, album_artist, artist, '') <> ''
          AND COALESCE(reviewed_title, title, '') <> ''
        """
    ).fetchall()

    tracks = []
    for row in rows:
        path = resolve_path(row["path"])
        tracks.append(
            Track(
                id=row["id"],
                path=path,
                filename=row["filename"],
                artist=row["meta_artist"],
                album=row["meta_album"],
                title=row["meta_title"],
                size_bytes=row["size_bytes"] or 0,
                modified_at=row["modified_at"],
            )
        )
    return tracks


def path_has_artist_folder(track: Track) -> bool:
    artist = normalize(track.artist)
    return any(normalize(part) == artist for part in track.path.parts)


def choose_keeper(tracks: list[Track]) -> Track:
    # Prefer the matching artist folder, then already-sorted files, then largest file.
    return sorted(
        tracks,
        key=lambda item: (
            0 if path_has_artist_folder(item) else 1,
            0 if is_inside_sorted_folder(item.path) else 1,
            -item.size_bytes,
            str(item.path).casefold(),
        ),
    )[0]


def unique_quarantine_path(base: Path, used: set[str]) -> Path:
    candidate = base
    counter = 2
    while str(candidate).casefold() in used or candidate.exists():
        candidate = base.with_name(f"{base.stem} ({counter}){base.suffix}")
        counter += 1
    used.add(str(candidate).casefold())
    return candidate


def build_plan(tracks: list[Track], quarantine_root: Path) -> list[DuplicateAction]:
    groups: dict[str, list[Track]] = defaultdict(list)
    for track in tracks:
        key = duplicate_key(track)
        if key.count("\x1f") == 1 and all(key.split("\x1f")):
            groups[key].append(track)

    actions: list[DuplicateAction] = []
    used_quarantine_paths: set[str] = set()
    for key, group in sorted(groups.items()):
        if len(group) < 2:
            continue
        keeper = choose_keeper(group)
        artist, title = key.split("\x1f")
        readable_key = f"{artist} | {title}"
        for track in group:
            if track.id == keeper.id:
                actions.append(
                    DuplicateAction(
                        duplicate_key=readable_key,
                        action="keep",
                        reason="largest file in duplicate metadata group",
                        track=track,
                        keep_path=keeper.path,
                        quarantine_path=None,
                    )
                )
                continue

            quarantine_path = unique_quarantine_path(
                quarantine_root / track.path.name,
                used_quarantine_paths,
            )
            actions.append(
                DuplicateAction(
                    duplicate_key=readable_key,
                    action="quarantine",
                    reason="same metadata artist and title as kept file",
                    track=track,
                    keep_path=keeper.path,
                    quarantine_path=quarantine_path,
                )
            )
    return actions


def write_report(actions: list[DuplicateAction], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "file_id",
                "action",
                "reason",
                "duplicate_key",
                "artist",
                "album",
                "title",
                "size_bytes",
                "source_path",
                "keep_path",
                "quarantine_path",
            ],
        )
        writer.writeheader()
        for action in actions:
            writer.writerow(
                {
                    "file_id": action.track.id,
                    "action": action.action,
                    "reason": action.reason,
                    "duplicate_key": action.duplicate_key,
                    "artist": action.track.artist,
                    "album": action.track.album,
                    "title": action.track.title,
                    "size_bytes": action.track.size_bytes,
                    "source_path": action.track.path,
                    "keep_path": action.keep_path,
                    "quarantine_path": action.quarantine_path or "",
                }
            )


def record_plan(connection: sqlite3.Connection, actions: list[DuplicateAction]) -> None:
    with connection:
        connection.executemany(
            """
            UPDATE files
            SET duplicate_status = ?,
                duplicate_group_key = ?,
                duplicate_keep_path = ?,
                duplicate_error = NULL
            WHERE id = ?
            """,
            [
                (
                    action.action,
                    action.duplicate_key,
                    str(action.keep_path),
                    action.track.id,
                )
                for action in actions
            ],
        )


def apply_quarantine(connection: sqlite3.Connection, actions: list[DuplicateAction]) -> tuple[int, int]:
    moved = 0
    failed = 0
    for action in actions:
        if action.action != "quarantine" or action.quarantine_path is None:
            continue
        try:
            action.quarantine_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(action.track.path), str(action.quarantine_path))
            removed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            with connection:
                connection.execute(
                    """
                    UPDATE files
                    SET path = ?,
                        parent_path = ?,
                        filename = ?,
                        duplicate_status = 'quarantined',
                        duplicate_removed_at = ?,
                        duplicate_error = NULL
                    WHERE id = ?
                    """,
                    (
                        str(action.quarantine_path),
                        str(action.quarantine_path.parent),
                        action.quarantine_path.name,
                        removed_at,
                        action.track.id,
                    ),
                )
            moved += 1
        except Exception as exc:
            failed += 1
            with connection:
                connection.execute(
                    "UPDATE files SET duplicate_status = 'error', duplicate_error = ? WHERE id = ?",
                    (str(exc), action.track.id),
                )
    return moved, failed


def summarize(actions: list[DuplicateAction]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for action in actions:
        counts[action.action] = counts.get(action.action, 0) + 1
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find duplicate sorted tracks with the same metadata artist, album, and title."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--quarantine", type=Path, default=DEFAULT_QUARANTINE)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Move duplicate files into the quarantine folder. Dry-run by default.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    connection = connect(args.db)
    try:
        ensure_schema(connection)
        tracks = fetch_tracks(connection)
        actions = build_plan(tracks, args.quarantine)
        write_report(actions, args.report)
        record_plan(connection, actions)
        counts = summarize(actions)
        print(f"Sorted tracks considered: {len(tracks)}")
        print(f"Duplicate groups: {len(set(action.duplicate_key for action in actions))}")
        print(f"Report: {args.report}")
        for action, count in sorted(counts.items()):
            print(f"{action}: {count}")
        if args.apply:
            moved, failed = apply_quarantine(connection, actions)
            print(f"Quarantined: {moved}")
            print(f"Failed: {failed}")
        else:
            print("Dry run only. Re-run with --apply to quarantine duplicates.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()

