#!/usr/bin/env python3
"""Plan and optionally apply artist-folder moves for validated audio files."""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB_PATH = Path("d_music_inventory.db")
DEFAULT_PLAN_PATH = Path("exports_d_music/move_plan.csv")
SAFE_REVIEW_STATUSES = {"accepted_metadata", "accepted_folder", "various_artists", "unknown"}
BLOCKED_REVIEW_STATUSES = {"needs_review", "skipped"}
RESERVED_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


@dataclass
class MovePlanRow:
    file_id: int
    metadata_status: str
    review_status: str
    artist: str
    album: str
    title: str
    source_path: Path
    destination_path: Path
    action: str
    reason: str


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(files)")}
    additions = {
        "move_status": "TEXT",
        "planned_path": "TEXT",
        "moved_at": "TEXT",
        "move_error": "TEXT",
    }
    for column, column_type in additions.items():
        if column not in columns:
            connection.execute(f"ALTER TABLE files ADD COLUMN {column} {column_type}")
    connection.commit()


def resolve_path(path_text: str) -> Path:
    normalized = path_text.replace("\\", "/")
    if os.name == "nt" and normalized.startswith("/mnt/") and len(normalized) > 6 and normalized[6] == "/":
        drive = normalized[5].upper()
        rest = normalized[7:]
        return Path(f"{drive}:/{rest}")
    return Path(normalized)


def default_destination(root_path: str) -> Path:
    return resolve_path(root_path) / "_Sorted_By_Artist"


def clean_part(value: str, fallback: str) -> str:
    value = (value or "").strip() or fallback
    value = re.sub(r"[<>:\"/\\|?*]+", "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    if not value:
        value = fallback
    if value.upper() in RESERVED_WINDOWS_NAMES:
        value = f"_{value}"
    return value[:120]


def unique_destination(path: Path, planned: set[str]) -> Path:
    candidate = path
    counter = 2
    while str(candidate).casefold() in planned or candidate.exists():
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        counter += 1
    planned.add(str(candidate).casefold())
    return candidate


def row_is_safe(row: sqlite3.Row) -> bool:
    review_status = row["review_status"] or "unreviewed"
    metadata_status = row["metadata_status"] or "unknown"
    if review_status in BLOCKED_REVIEW_STATUSES:
        return False
    if review_status in SAFE_REVIEW_STATUSES:
        return True
    return metadata_status == "confirmed" and review_status == "unreviewed"


def artist_for_row(row: sqlite3.Row) -> str:
    review_status = row["review_status"] or "unreviewed"
    if review_status in SAFE_REVIEW_STATUSES and row["reviewed_artist"]:
        return row["reviewed_artist"]
    return row["album_artist"] or row["artist"] or row["reviewed_artist"] or "Unknown Artist"


def destination_for_row(root_destination: Path, artist: str, album: str, filename: str) -> Path:
    artist_destination = root_destination / artist
    if album.strip():
        return artist_destination / clean_part(album, "Unknown Album") / clean_part(filename, "track")
    return artist_destination / clean_part(filename, "track")


def fetch_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT
                id, root_path, path, filename, metadata_status, review_status,
                reviewed_artist, reviewed_album, reviewed_title,
                artist, album_artist, album, title, move_status
            FROM files
            WHERE is_audio = 1
            ORDER BY root_path, artist, album, title, filename
            """
        )
    )


def build_plan(connection: sqlite3.Connection, destination: Path | None) -> list[MovePlanRow]:
    rows = fetch_rows(connection)
    planned_destinations: set[str] = set()
    plan: list[MovePlanRow] = []

    for row in rows:
        source = resolve_path(row["path"])
        root_destination = destination or default_destination(row["root_path"])
        metadata_status = row["metadata_status"] or "unknown"
        review_status = row["review_status"] or "unreviewed"
        artist = clean_part(artist_for_row(row), "Unknown Artist")
        album = row["reviewed_album"] or row["album"] or ""
        title = row["reviewed_title"] or row["title"] or ""
        destination_path = destination_for_row(root_destination, artist, album, row["filename"])

        if not row_is_safe(row):
            action = "skip"
            reason = f"not approved for moving: metadata_status={metadata_status}, review_status={review_status}"
        elif not source.exists():
            action = "error"
            reason = "source file is missing"
        elif root_destination in source.parents or source == root_destination:
            action = "skip"
            reason = "source is already inside destination folder"
            destination_path = source
        else:
            destination_path = unique_destination(destination_path, planned_destinations)
            action = "move"
            reason = "confirmed metadata or accepted review"

        plan.append(
            MovePlanRow(
                file_id=row["id"],
                metadata_status=metadata_status,
                review_status=review_status,
                artist=artist,
                album=album,
                title=title,
                source_path=source,
                destination_path=destination_path,
                action=action,
                reason=reason,
            )
        )

    return plan


def write_plan(plan: list[MovePlanRow], plan_path: Path) -> None:
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    with plan_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "file_id", "action", "reason", "metadata_status", "review_status",
                "artist", "album", "title", "source_path", "destination_path",
            ],
        )
        writer.writeheader()
        for row in plan:
            writer.writerow(
                {
                    "file_id": row.file_id,
                    "action": row.action,
                    "reason": row.reason,
                    "metadata_status": row.metadata_status,
                    "review_status": row.review_status,
                    "artist": row.artist,
                    "album": row.album,
                    "title": row.title,
                    "source_path": row.source_path,
                    "destination_path": row.destination_path,
                }
            )


def record_plan(connection: sqlite3.Connection, plan: list[MovePlanRow]) -> None:
    with connection:
        connection.executemany(
            """
            UPDATE files
            SET planned_path = ?, move_status = ?, move_error = ?
            WHERE id = ?
            """,
            [
                (
                    str(row.destination_path),
                    "planned" if row.action == "move" else row.action,
                    None if row.action == "move" else row.reason,
                    row.file_id,
                )
                for row in plan
            ],
        )


def apply_plan(connection: sqlite3.Connection, plan: list[MovePlanRow]) -> tuple[int, int]:
    moved = 0
    failed = 0
    for row in plan:
        if row.action != "move":
            continue
        try:
            row.destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(row.source_path), str(row.destination_path))
            moved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            with connection:
                connection.execute(
                    """
                    UPDATE files
                    SET path = ?, parent_path = ?, filename = ?, planned_path = ?,
                        move_status = 'moved', moved_at = ?, move_error = NULL
                    WHERE id = ?
                    """,
                    (
                        str(row.destination_path),
                        str(row.destination_path.parent),
                        row.destination_path.name,
                        str(row.destination_path),
                        moved_at,
                        row.file_id,
                    ),
                )
            moved += 1
        except Exception as exc:
            failed += 1
            with connection:
                connection.execute(
                    "UPDATE files SET move_status = 'error', move_error = ? WHERE id = ?",
                    (str(exc), row.file_id),
                )
    return moved, failed


def summarize(plan: list[MovePlanRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in plan:
        counts[row.action] = counts.get(row.action, 0) + 1
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or apply artist-folder moves for validated audio files.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN_PATH)
    parser.add_argument("--destination", type=Path, help="Destination root. Default: <music root>/_Sorted_By_Artist")
    parser.add_argument("--apply", action="store_true", help="Actually move files. Without this, only creates a plan.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    connection = connect(args.db)
    try:
        ensure_schema(connection)
        destination = args.destination.resolve() if args.destination else None
        plan = build_plan(connection, destination)
        write_plan(plan, args.plan)
        record_plan(connection, plan)
        counts = summarize(plan)
        print(f"Plan CSV: {args.plan}")
        for action, count in sorted(counts.items()):
            print(f"{action}: {count}")
        if args.apply:
            moved, failed = apply_plan(connection, plan)
            print(f"Moved: {moved}")
            print(f"Failed: {failed}")
        else:
            print("Dry run only. Re-run with --apply to move files.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()

