#!/usr/bin/env python3
r"""Refresh the D:\Music inventory, extract metadata, and plan artist/title duplicates."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import extract_metadata
import purge_duplicates
import scan_music


DEFAULT_ROOTS = [
    Path(r"D:\Music\just music"),
    Path(r"D:\Music\_Sorted_By_Artist"),
]
DEFAULT_DB_PATH = Path("d_music_inventory.db")
DEFAULT_EXPORT_DIR = Path("exports_d_music")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan D:\\Music\\just music and D:\\Music\\_Sorted_By_Artist, "
            "extract tags, and create a duplicate plan grouped by metadata artist + title."
        )
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--root", action="append", type=Path, dest="roots")
    return parser.parse_args()


def print_lock_help(db_path: Path) -> None:
    print(f"Database is locked: {db_path}")
    print("Close any running review_app.py, music_review_app.py, DB browser, or other refresh process, then try again.")
    print("This refresh now waits up to 60 seconds for locks before giving up.")


def main() -> None:
    args = parse_args()
    roots = args.roots or DEFAULT_ROOTS
    try:
        run_refresh(args, roots)
    except sqlite3.OperationalError as exc:
        if "database is locked" in str(exc).casefold():
            print_lock_help(args.db)
            raise SystemExit(1) from exc
        raise


def run_refresh(args: argparse.Namespace, roots: list[Path]) -> None:

    connection = scan_music.connect(args.db)
    try:
        scan_music.create_schema(connection)
        for root_arg in roots:
            root = scan_music.resolve_root(root_arg)
            directory_count, file_count = scan_music.replace_inventory(connection, root)
            print(f"Scanned root: {root}")
            print(f"  Directories inventoried: {directory_count}")
            print(f"  Files inventoried: {file_count}")
        scan_music.export_csvs(connection, args.export_dir)
    finally:
        connection.close()

    metadata_connection = extract_metadata.connect(args.db)
    try:
        extract_metadata.ensure_schema(metadata_connection)
        metadata_rows = extract_metadata.fetch_audio_files(metadata_connection)
        review_rows = extract_metadata.update_metadata(metadata_connection, metadata_rows)
        extract_metadata.export_review(review_rows, args.export_dir / "metadata_review.csv")
    finally:
        metadata_connection.close()

    duplicate_connection = purge_duplicates.connect(args.db)
    try:
        purge_duplicates.ensure_schema(duplicate_connection)
        tracks = purge_duplicates.fetch_tracks(duplicate_connection)
        actions = purge_duplicates.build_plan(
            tracks,
            Path(r"D:\Music\_Duplicate_Quarantine"),
        )
        purge_duplicates.write_report(actions, args.export_dir / "duplicate_purge_plan.csv")
        purge_duplicates.record_plan(duplicate_connection, actions)
    finally:
        duplicate_connection.close()

    counts = purge_duplicates.summarize(actions)
    print(f"Audio files processed: {len(review_rows)}")
    print(f"Duplicate groups: {len(set(action.duplicate_key for action in actions))}")
    for action, count in sorted(counts.items()):
        print(f"{action}: {count}")
    print(f"Database: {args.db}")
    print(f"CSV exports: {args.export_dir}")


if __name__ == "__main__":
    main()

