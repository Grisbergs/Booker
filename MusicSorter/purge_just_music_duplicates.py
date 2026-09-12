#!/usr/bin/env python3
"""Delete Just Music files that already exist in the sorted artist library."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import extract_metadata
from scan_music import AUDIO_EXTENSIONS


DEFAULT_JUST_MUSIC = Path(r"D:\Music\just music")
DEFAULT_SORTED = Path(r"D:\Music\_Sorted_By_Artist")
DEFAULT_REPORT = Path(r"D:\Music\music_inventory_exports_refreshed\just_music_existing_in_sorted.csv")


@dataclass(frozen=True)
class Track:
    path: Path
    artist: str
    title: str
    album: str
    size_bytes: int
    sha256: str | None = None


def normalize(value: str | None) -> str:
    value = (value or "").casefold().strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"^[\W_]+|[\W_]+$", "", value)
    return value


def key_for(artist: str | None, title: str | None) -> str:
    artist_key = normalize(artist)
    title_key = normalize(title)
    return f"{artist_key}\x1f{title_key}" if artist_key and title_key else ""


def iter_audio(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.casefold() in AUDIO_EXTENSIONS:
            yield path


def track_from_path(path: Path, with_hash: bool = False) -> Track | None:
    metadata, error = extract_metadata.read_metadata(str(path))
    if error:
        return None
    artist = metadata.get("album_artist") or metadata.get("artist") or ""
    title = metadata.get("title") or ""
    if not artist or not title:
        return None
    digest = file_hash(path) if with_hash else None
    return Track(
        path=path,
        artist=artist,
        title=title,
        album=metadata.get("album") or "",
        size_bytes=path.stat().st_size,
        sha256=digest,
    )


def file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_sorted_index(sorted_root: Path) -> dict[str, list[Track]]:
    index: dict[str, list[Track]] = {}
    for path in iter_audio(sorted_root):
        track = track_from_path(path, with_hash=False)
        if track is None:
            continue
        key = key_for(track.artist, track.title)
        if key:
            index.setdefault(key, []).append(track)
    return index


def find_matches(just_root: Path, sorted_index: dict[str, list[Track]]) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for path in iter_audio(just_root):
        track = track_from_path(path, with_hash=False)
        if track is None:
            continue
        key = key_for(track.artist, track.title)
        sorted_matches = sorted_index.get(key, [])
        if not sorted_matches:
            continue
        best = sorted(sorted_matches, key=lambda item: (-item.size_bytes, str(item.path).casefold()))[0]
        matches.append(
            {
                "action": "delete_from_just_music",
                "reason": "same metadata artist and title exists in sorted artist library",
                "artist": track.artist,
                "title": track.title,
                "just_music_album": track.album,
                "sorted_album": best.album,
                "just_music_size_bytes": track.size_bytes,
                "sorted_size_bytes": best.size_bytes,
                "just_music_path": str(track.path),
                "matching_sorted_path": str(best.path),
                "deleted_at": "",
                "delete_error": "",
            }
        )
    return matches


def write_report(rows: list[dict[str, object]], report: Path) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "action",
        "reason",
        "artist",
        "title",
        "just_music_album",
        "sorted_album",
        "just_music_size_bytes",
        "sorted_size_bytes",
        "just_music_path",
        "matching_sorted_path",
        "deleted_at",
        "delete_error",
    ]
    with report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def apply_deletes(rows: list[dict[str, object]]) -> tuple[int, int]:
    deleted = 0
    failed = 0
    for row in rows:
        path = Path(str(row["just_music_path"]))
        try:
            path.unlink()
            row["deleted_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            deleted += 1
        except Exception as exc:
            row["delete_error"] = str(exc)
            failed += 1
    return deleted, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find Just Music files whose metadata artist + title already exists in the sorted library."
    )
    parser.add_argument("--just-music", type=Path, default=DEFAULT_JUST_MUSIC)
    parser.add_argument("--sorted", type=Path, default=DEFAULT_SORTED)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--apply", action="store_true", help="Delete matching files from Just Music.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sorted_index = build_sorted_index(args.sorted)
    rows = find_matches(args.just_music, sorted_index)
    deleted = failed = 0
    if args.apply:
        deleted, failed = apply_deletes(rows)
    write_report(rows, args.report)
    print(f"Sorted metadata keys: {len(sorted_index)}")
    print(f"Just Music files matching sorted library: {len(rows)}")
    print(f"Report: {args.report}")
    if args.apply:
        print(f"Deleted from Just Music: {deleted}")
        print(f"Failed: {failed}")
    else:
        print("Dry run only. Re-run with --apply to delete matching Just Music files.")


if __name__ == "__main__":
    main()
