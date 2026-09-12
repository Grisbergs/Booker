#!/usr/bin/env python3
"""Build a SQLite inventory of directories and files for a music library."""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_DB_PATH = Path("music_inventory.db")
DEFAULT_EXPORT_DIR = Path("exports")

AUDIO_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".alac",
    ".flac",
    ".m4a",
    ".m4p",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}


@dataclass(frozen=True)
class DirectoryRow:
    root_path: str
    path: str
    relative_path: str
    parent_path: str | None
    name: str
    modified_at: str | None


@dataclass(frozen=True)
class FileRow:
    root_path: str
    path: str
    relative_path: str
    parent_path: str
    filename: str
    stem: str
    extension: str
    size_bytes: int
    modified_at: str | None
    is_audio: int


def utc_timestamp(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat(timespec="seconds")


def resolve_root(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Scan root does not exist: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"Scan root is not a directory: {resolved}")
    return resolved


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=60)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 60000")
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS scan_roots (
            root_path TEXT PRIMARY KEY,
            scanned_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS directories (
            id INTEGER PRIMARY KEY,
            root_path TEXT NOT NULL,
            path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            parent_path TEXT,
            name TEXT NOT NULL,
            modified_at TEXT,
            UNIQUE(root_path, path),
            FOREIGN KEY(root_path) REFERENCES scan_roots(root_path) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_directories_root_relative_path
            ON directories(root_path, relative_path);

        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            root_path TEXT NOT NULL,
            path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            parent_path TEXT NOT NULL,
            filename TEXT NOT NULL,
            stem TEXT NOT NULL,
            extension TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            modified_at TEXT,
            is_audio INTEGER NOT NULL DEFAULT 0,
            artist TEXT,
            album TEXT,
            title TEXT,
            track_number TEXT,
            disc_number TEXT,
            year TEXT,
            suggested_path TEXT,
            suggested_filename TEXT,
            status TEXT NOT NULL DEFAULT 'inventoried',
            notes TEXT,
            confidence REAL,
            UNIQUE(root_path, path),
            FOREIGN KEY(root_path) REFERENCES scan_roots(root_path) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_files_root_relative_path
            ON files(root_path, relative_path);

        CREATE INDEX IF NOT EXISTS idx_files_extension
            ON files(extension);

        CREATE INDEX IF NOT EXISTS idx_files_is_audio
            ON files(is_audio);
        """
    )


def path_text(path: Path) -> str:
    return str(path)


def relative_text(path: Path, root: Path) -> str:
    if path == root:
        return "."
    return str(path.relative_to(root))


def scan_directories(root: Path) -> Iterable[DirectoryRow]:
    for current, dirnames, _filenames in os.walk(root):
        dirnames.sort(key=str.lower)
        current_path = Path(current)
        try:
            stat = current_path.stat()
            modified_at = utc_timestamp(stat.st_mtime)
        except OSError:
            modified_at = None

        yield DirectoryRow(
            root_path=path_text(root),
            path=path_text(current_path),
            relative_path=relative_text(current_path, root),
            parent_path=path_text(current_path.parent) if current_path != root else None,
            name=current_path.name,
            modified_at=modified_at,
        )


def scan_files(root: Path) -> Iterable[FileRow]:
    for current, dirnames, filenames in os.walk(root):
        dirnames.sort(key=str.lower)
        for filename in sorted(filenames, key=str.lower):
            file_path = Path(current) / filename
            try:
                stat = file_path.stat()
            except OSError:
                continue

            extension = file_path.suffix.lower()
            yield FileRow(
                root_path=path_text(root),
                path=path_text(file_path),
                relative_path=relative_text(file_path, root),
                parent_path=path_text(file_path.parent),
                filename=file_path.name,
                stem=file_path.stem,
                extension=extension,
                size_bytes=stat.st_size,
                modified_at=utc_timestamp(stat.st_mtime),
                is_audio=1 if extension in AUDIO_EXTENSIONS else 0,
            )


def replace_inventory(connection: sqlite3.Connection, root: Path) -> tuple[int, int]:
    root_value = path_text(root)
    scanned_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with connection:
        connection.execute("DELETE FROM scan_roots WHERE root_path = ?", (root_value,))
        connection.execute(
            "INSERT INTO scan_roots (root_path, scanned_at) VALUES (?, ?)",
            (root_value, scanned_at),
        )

        directories = list(scan_directories(root))
        connection.executemany(
            """
            INSERT INTO directories (
                root_path, path, relative_path, parent_path, name, modified_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.root_path,
                    row.path,
                    row.relative_path,
                    row.parent_path,
                    row.name,
                    row.modified_at,
                )
                for row in directories
            ],
        )

        files = list(scan_files(root))
        connection.executemany(
            """
            INSERT INTO files (
                root_path, path, relative_path, parent_path, filename, stem,
                extension, size_bytes, modified_at, is_audio
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.root_path,
                    row.path,
                    row.relative_path,
                    row.parent_path,
                    row.filename,
                    row.stem,
                    row.extension,
                    row.size_bytes,
                    row.modified_at,
                    row.is_audio,
                )
                for row in files
            ],
        )

    return len(directories), len(files)


def export_query(connection: sqlite3.Connection, query: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    cursor = connection.execute(query)
    headers = [description[0] for description in cursor.description]

    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(cursor.fetchall())


def export_csvs(connection: sqlite3.Connection, export_dir: Path) -> None:
    export_query(
        connection,
        """
        SELECT root_path, relative_path, path, parent_path, name, modified_at
        FROM directories
        ORDER BY root_path, relative_path
        """,
        export_dir / "directories.csv",
    )
    export_query(
        connection,
        """
        SELECT
            root_path,
            relative_path,
            path,
            parent_path,
            filename,
            stem,
            extension,
            size_bytes,
            modified_at,
            is_audio,
            artist,
            album,
            title,
            track_number,
            disc_number,
            year,
            suggested_path,
            suggested_filename,
            status,
            notes,
            confidence
        FROM files
        ORDER BY root_path, relative_path
        """,
        export_dir / "files.csv",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a SQLite inventory of directories and files."
    )
    parser.add_argument("root", type=Path, help="Directory to scan")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite database path. Default: {DEFAULT_DB_PATH}",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help=f"CSV export directory. Default: {DEFAULT_EXPORT_DIR}",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Skip CSV export and only update the SQLite database.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = resolve_root(args.root)

    connection = connect(args.db)
    try:
        create_schema(connection)
        directory_count, file_count = replace_inventory(connection, root)
        if not args.no_export:
            export_csvs(connection, args.export_dir)
    finally:
        connection.close()

    print(f"Scanned root: {root}")
    print(f"Directories inventoried: {directory_count}")
    print(f"Files inventoried: {file_count}")
    print(f"Database: {args.db}")
    if not args.no_export:
        print(f"CSV exports: {args.export_dir}")


if __name__ == "__main__":
    main()

