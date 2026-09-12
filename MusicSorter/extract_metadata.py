#!/usr/bin/env python3
"""Extract embedded audio metadata into the music inventory database."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from mutagen import File as MutagenFile
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: mutagen. Install it with: python3 -m pip install -r requirements.txt"
    ) from exc


DEFAULT_DB_PATH = Path("d_music_inventory.db")
DEFAULT_EXPORT_PATH = Path("exports_d_music/metadata_review.csv")

TAG_KEYS = {
    "artist": ["artist", "TPE1", "©ART", "Author"],
    "album_artist": ["albumartist", "album_artist", "TPE2", "aART"],
    "album": ["album", "TALB", "©alb"],
    "title": ["title", "TIT2", "©nam"],
    "track_number": ["tracknumber", "track", "TRCK", "trkn"],
    "disc_number": ["discnumber", "disc", "TPOS", "disk"],
    "year": ["date", "year", "TDRC", "TYER", "©day"],
    "genre": ["genre", "TCON", "©gen"],
}


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path, timeout=60)
    connection.execute("PRAGMA busy_timeout = 60000")
    connection.row_factory = sqlite3.Row
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(files)")}
    additions = {
        "album_artist": "TEXT",
        "genre": "TEXT",
        "metadata_status": "TEXT",
        "metadata_error": "TEXT",
    }
    for column, column_type in additions.items():
        if column not in columns:
            connection.execute(f"ALTER TABLE files ADD COLUMN {column} {column_type}")
    connection.commit()


def fetch_audio_files(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(files)")}
    containing_directory = (
        "containing_directory"
        if "containing_directory" in columns
        else "parent_path AS containing_directory"
    )
    return list(
        connection.execute(
            f"""
            SELECT id, path, relative_path, filename, {containing_directory}, artist
            FROM files
            WHERE is_audio = 1
            ORDER BY root_path, relative_path
            """
        )
    )


def stringify_tag(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        if len(value) == 1:
            return stringify_tag(value[0])
        return "; ".join(filter(None, (stringify_tag(item) for item in value))) or None
    if hasattr(value, "text"):
        return stringify_tag(value.text)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip() or None
    text = str(value).strip()
    return text or None


def first_tag(tags: Any, keys: list[str]) -> str | None:
    if not tags:
        return None
    for key in keys:
        if key in tags:
            value = stringify_tag(tags[key])
            if value:
                return value
    lower_map = {str(key).lower(): key for key in tags.keys()}
    for key in keys:
        actual_key = lower_map.get(key.lower())
        if actual_key is not None:
            value = stringify_tag(tags[actual_key])
            if value:
                return value
    return None


def resolve_audio_path(path_text: str) -> Path:
    normalized = path_text.replace("\\", "/")
    if normalized.startswith("/mnt/") and len(normalized) > 6 and normalized[6] == "/":
        drive = normalized[5].upper()
        rest = normalized[7:]
        return Path(f"{drive}:/{rest}")
    return Path(path_text)


def read_metadata(path_text: str) -> tuple[dict[str, str | None], str | None]:
    path = resolve_audio_path(path_text)
    try:
        audio = MutagenFile(path, easy=True)
        if audio is None:
            audio = MutagenFile(path, easy=False)
        if audio is None:
            return {}, "unsupported or unreadable audio file"
    except Exception as exc:
        return {}, str(exc)

    tags = audio.tags or {}
    values = {field: first_tag(tags, keys) for field, keys in TAG_KEYS.items()}
    return values, None


def norm(value: str | None) -> str:
    return (value or "").strip().casefold()


def confidence_from_tags(row: sqlite3.Row, metadata: dict[str, str | None]) -> tuple[str, float, str]:
    folder_artist = norm(row["artist"])
    tag_artist = norm(metadata.get("artist"))
    album_artist = norm(metadata.get("album_artist"))

    if album_artist and album_artist == folder_artist:
        return "confirmed", 1.0, "album_artist matches folder artist guess"
    if tag_artist and tag_artist == folder_artist:
        return "confirmed", 0.98, "artist tag matches folder artist guess"
    if album_artist or tag_artist:
        return "metadata-conflict", 0.6, "metadata artist differs from folder artist guess"
    return "missing-metadata", 0.25, "no embedded artist metadata found"


def update_metadata(connection: sqlite3.Connection, rows: list[sqlite3.Row]) -> list[dict[str, object]]:
    updates = []
    export_rows: list[dict[str, object]] = []

    for row in rows:
        metadata, error = read_metadata(row["path"])
        if error:
            status, confidence, reason = "metadata-error", 0.0, error
        else:
            status, confidence, reason = confidence_from_tags(row, metadata)

        updates.append(
            (
                metadata.get("artist"),
                metadata.get("album_artist"),
                metadata.get("album"),
                metadata.get("title"),
                metadata.get("track_number"),
                metadata.get("disc_number"),
                metadata.get("year"),
                metadata.get("genre"),
                confidence,
                status,
                error,
                row["id"],
            )
        )

        export_rows.append(
            {
                "id": row["id"],
                "relative_path": row["relative_path"],
                "filename": row["filename"],
                "containing_directory": row["containing_directory"] or "",
                "folder_artist_guess": row["artist"] or "",
                "tag_artist": metadata.get("artist") or "",
                "tag_album_artist": metadata.get("album_artist") or "",
                "tag_album": metadata.get("album") or "",
                "tag_title": metadata.get("title") or "",
                "tag_track_number": metadata.get("track_number") or "",
                "tag_disc_number": metadata.get("disc_number") or "",
                "tag_year": metadata.get("year") or "",
                "tag_genre": metadata.get("genre") or "",
                "metadata_status": status,
                "confidence": confidence,
                "reason": reason,
            }
        )

    with connection:
        connection.executemany(
            """
            UPDATE files
            SET artist = COALESCE(?, artist),
                album_artist = ?,
                album = ?,
                title = ?,
                track_number = ?,
                disc_number = ?,
                year = ?,
                genre = ?,
                confidence = ?,
                metadata_status = ?,
                metadata_error = ?
            WHERE id = ?
            """,
            updates,
        )

    return export_rows


def export_review(rows: list[dict[str, object]], export_path: Path) -> None:
    export_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "relative_path",
        "filename",
        "containing_directory",
        "folder_artist_guess",
        "tag_artist",
        "tag_album_artist",
        "tag_album",
        "tag_title",
        "tag_track_number",
        "tag_disc_number",
        "tag_year",
        "tag_genre",
        "metadata_status",
        "confidence",
        "reason",
    ]
    with export_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract embedded audio metadata into SQLite.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--export", type=Path, default=DEFAULT_EXPORT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    connection = connect(args.db)
    try:
        ensure_schema(connection)
        rows = fetch_audio_files(connection)
        export_rows = update_metadata(connection, rows)
        export_review(export_rows, args.export)
    finally:
        connection.close()

    status_counts: dict[str, int] = {}
    for row in export_rows:
        status = str(row["metadata_status"])
        status_counts[status] = status_counts.get(status, 0) + 1

    print(f"Audio files processed: {len(export_rows)}")
    print(f"Review CSV: {args.export}")
    print("Metadata status counts:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()

