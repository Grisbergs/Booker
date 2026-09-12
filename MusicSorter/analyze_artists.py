#!/usr/bin/env python3
"""Record containing folders and guess artist names from inventoried audio paths."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from collections import Counter
from pathlib import Path


DEFAULT_DB_PATH = Path("d_music_inventory.db")
DEFAULT_EXPORT_PATH = Path("exports_d_music/artist_guesses.csv")
COLLECTION_FOLDERS = {"itunes", "itunes music", "music", "just music"}


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_schema(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(files)")
    }
    if "containing_directory" not in columns:
        connection.execute("ALTER TABLE files ADD COLUMN containing_directory TEXT")
        connection.commit()


def path_parts(relative_path: str) -> tuple[str, ...]:
    return Path(relative_path).parts


def containing_directory(relative_path: str) -> str | None:
    parts = path_parts(relative_path)
    if len(parts) < 2:
        return None
    return parts[-2]


def guess_artist(relative_path: str) -> tuple[str | None, float, str]:
    parts = path_parts(relative_path)
    if len(parts) < 2:
        return None, 0.0, "audio file is directly inside the scan root"

    folder_parts = list(parts[:-1])
    skipped: list[str] = []
    while folder_parts and folder_parts[0].strip().lower() in COLLECTION_FOLDERS:
        skipped.append(folder_parts.pop(0).strip())

    if not folder_parts:
        return None, 0.0, "only collection folders before filename"

    artist = folder_parts[0].strip()
    if not artist:
        return None, 0.0, "no usable artist folder"

    if skipped:
        reason = "artist folder after collection folder"
        if len(skipped) > 1:
            reason = "artist folder after collection folders"
        return artist, 0.95, f"{reason}: {' / '.join(skipped)}"

    if len(folder_parts) >= 2:
        return artist, 0.9, "top-level folder looks like artist folder"

    return artist, 0.75, "top-level folder contains the audio file"


def fetch_audio_files(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT id, root_path, relative_path, path, filename, artist
            FROM files
            WHERE is_audio = 1
            ORDER BY root_path, relative_path
            """
        )
    )


def artist_note(existing_artist: str | None, reason: str, folder_name: str | None) -> str:
    base = f"artist folder guess; {reason}"
    if folder_name:
        base = f"{base}; containing_directory={folder_name}"
    if existing_artist:
        return f"{base}; overwrote previous artist={existing_artist}"
    return base


def build_export_row(
    row: sqlite3.Row,
    guessed_artist: str | None,
    confidence: float,
    reason: str,
    updated: str,
) -> dict[str, object]:
    return {
        "id": row["id"],
        "filename": row["filename"],
        "relative_path": row["relative_path"],
        "containing_directory": containing_directory(row["relative_path"]) or "",
        "current_artist": row["artist"] or "",
        "guessed_artist": guessed_artist or "",
        "confidence": confidence,
        "reason": reason,
        "updated": updated,
    }


def update_artist_guesses(
    connection: sqlite3.Connection,
    rows: list[sqlite3.Row],
    overwrite: bool,
) -> tuple[int, list[dict[str, object]]]:
    updates = []
    export_rows: list[dict[str, object]] = []

    for row in rows:
        guessed_artist, confidence, reason = guess_artist(row["relative_path"])
        folder_name = containing_directory(row["relative_path"])
        existing_artist = row["artist"]
        should_update_artist = bool(guessed_artist and (overwrite or not existing_artist))
        artist_value = guessed_artist if should_update_artist else existing_artist

        updates.append(
            (
                folder_name,
                artist_value,
                confidence if should_update_artist else None,
                artist_note(existing_artist=existing_artist, reason=reason, folder_name=folder_name),
                row["id"],
            )
        )

        export_rows.append(
            build_export_row(
                row=row,
                guessed_artist=guessed_artist,
                confidence=confidence,
                reason=reason,
                updated="yes" if should_update_artist else "folder-only",
            )
        )

    if updates:
        with connection:
            connection.executemany(
                """
                UPDATE files
                SET containing_directory = ?,
                    artist = COALESCE(?, artist),
                    confidence = COALESCE(?, confidence),
                    notes = ?
                WHERE id = ?
                """,
                updates,
            )

    changed_artists = sum(1 for row in export_rows if row["updated"] == "yes")
    return changed_artists, export_rows


def dry_run_rows(rows: list[sqlite3.Row]) -> list[dict[str, object]]:
    export_rows: list[dict[str, object]] = []
    for row in rows:
        guessed_artist, confidence, reason = guess_artist(row["relative_path"])
        export_rows.append(
            build_export_row(
                row=row,
                guessed_artist=guessed_artist,
                confidence=confidence,
                reason=reason,
                updated="dry-run",
            )
        )
    return export_rows


def export_artist_guesses(rows: list[dict[str, object]], export_path: Path) -> None:
    export_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "filename",
        "relative_path",
        "containing_directory",
        "current_artist",
        "guessed_artist",
        "confidence",
        "reason",
        "updated",
    ]

    with export_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, object]]) -> list[tuple[str, int]]:
    counts = Counter(str(row["guessed_artist"]) for row in rows if row["guessed_artist"])
    return counts.most_common(20)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record containing folders and guess artists from folder structure."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite database path. Default: {DEFAULT_DB_PATH}",
    )
    parser.add_argument(
        "--export",
        type=Path,
        default=DEFAULT_EXPORT_PATH,
        help=f"Review CSV path. Default: {DEFAULT_EXPORT_PATH}",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing artist values. Default only fills blank artists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Create the review CSV without updating the database.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    connection = connect(args.db)
    try:
        ensure_schema(connection)
        rows = fetch_audio_files(connection)
        if args.dry_run:
            updated_count = 0
            export_rows = dry_run_rows(rows)
        else:
            updated_count, export_rows = update_artist_guesses(
                connection,
                rows,
                overwrite=args.overwrite,
            )

        export_artist_guesses(export_rows, args.export)
    finally:
        connection.close()

    print(f"Audio files analyzed: {len(rows)}")
    print(f"Database artist values updated: {updated_count}")
    print(f"Review CSV: {args.export}")
    print("Top guessed artists:")
    for artist, count in summarize(export_rows):
        print(f"  {artist}: {count}")


if __name__ == "__main__":
    main()
