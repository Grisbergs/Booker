#!/usr/bin/env python3
"""Organize local audio files into Artist/Album folders."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

try:
    from mutagen import File as MutagenFile
except ImportError:  # pragma: no cover
    MutagenFile = None


AUDIO_EXTENSIONS = {
    ".aac", ".aiff", ".alac", ".ape", ".flac", ".m4a", ".mp3",
    ".mp4", ".ogg", ".opus", ".wav", ".wma", ".wv",
}
INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


@dataclass(frozen=True)
class Track:
    source: str
    destination: str
    artist: str
    album: str
    title: str
    status: str = "ready"
    reason: str = ""


def clean_component(value: str, fallback: str) -> str:
    value = INVALID_PATH_CHARS.sub("_", value).strip().rstrip(". ")
    value = re.sub(r"\s+", " ", value)
    if not value:
        value = fallback
    if value.upper() in WINDOWS_RESERVED:
        value = f"_{value}"
    return value[:180].rstrip(". ")


def first_tag(tags: object, names: Iterable[str]) -> str:
    if not tags:
        return ""
    for name in names:
        try:
            value = tags.get(name)  # type: ignore[attr-defined]
        except (AttributeError, TypeError):
            continue
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        text = str(value).strip()
        if text:
            return text
    return ""


def read_metadata(path: Path) -> tuple[str, str, str]:
    if MutagenFile is None:
        raise RuntimeError("Mutagen is not installed. Run: python -m pip install mutagen")
    audio = MutagenFile(path, easy=True)
    if audio is None:
        raise ValueError("unsupported or unreadable audio file")
    tags = audio.tags
    artist = first_tag(tags, ("albumartist", "album artist", "artist"))
    album = first_tag(tags, ("album",))
    title = first_tag(tags, ("title",)) or path.stem
    return artist, album, title


def unique_destination(destination: Path, source: Path, reserved: set[Path]) -> Path:
    if destination.resolve() == source.resolve():
        return destination
    candidate = destination
    index = 2
    while candidate.exists() or candidate in reserved:
        candidate = destination.with_name(f"{destination.stem} ({index}){destination.suffix}")
        index += 1
    return candidate


def build_plan(source: Path, output: Path) -> list[Track]:
    plan: list[Track] = []
    reserved: set[Path] = set()
    output_resolved = output.resolve()
    paths = sorted(
        (p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS),
        key=lambda p: str(p).lower(),
    )
    for path in paths:
        try:
            if output_resolved != source.resolve() and output_resolved in path.resolve().parents:
                continue
            artist, album, title = read_metadata(path)
            artist = clean_component(artist, "Unknown Artist")
            album = clean_component(album, "Unknown Album")
            destination = output / artist / album / path.name
            destination = unique_destination(destination, path, reserved)
            reserved.add(destination)
            status = "unchanged" if destination.resolve() == path.resolve() else "ready"
            plan.append(Track(str(path), str(destination), artist, album, title, status))
        except Exception as exc:
            plan.append(Track(str(path), "", "", "", path.stem, "skipped", str(exc)))
    return plan


def apply_plan(plan: list[Track], copy: bool) -> tuple[int, int]:
    completed = failed = 0
    for track in plan:
        if track.status != "ready":
            continue
        source = Path(track.source)
        destination = Path(track.destination)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if copy:
                shutil.copy2(source, destination)
            else:
                shutil.move(str(source), str(destination))
            completed += 1
        except OSError as exc:
            failed += 1
            print(f"ERROR: {source}: {exc}", file=sys.stderr)
    return completed, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sort audio files into Artist/Album folders using embedded metadata."
    )
    parser.add_argument("source", type=Path, help="Directory containing music files")
    parser.add_argument(
        "-o", "--output", type=Path,
        help="Destination directory (default: <source>/Organized Music)",
    )
    parser.add_argument("--apply", action="store_true", help="Perform the operation")
    parser.add_argument("--copy", action="store_true", help="Copy instead of move (requires --apply)")
    parser.add_argument("--json", action="store_true", help="Print the plan as JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_dir():
        print(f"Source directory does not exist: {source}", file=sys.stderr)
        return 2
    output = (args.output or source / "Organized Music").expanduser().resolve()
    plan = build_plan(source, output)

    if args.json:
        print(json.dumps([asdict(track) for track in plan], indent=2))
    else:
        for track in plan:
            if track.status == "ready":
                action = "COPY" if args.copy else "MOVE"
                print(f"{action}: {track.source}\n   -> {track.destination}")
            elif track.status == "skipped":
                print(f"SKIP: {track.source} ({track.reason})")
        ready = sum(track.status == "ready" for track in plan)
        skipped = sum(track.status == "skipped" for track in plan)
        print(f"\nFound {len(plan)} audio files: {ready} ready, {skipped} skipped.")

    if not args.apply:
        if not args.json:
            print("Preview only. Add --apply to make these changes.")
        return 0

    completed, failed = apply_plan(plan, args.copy)
    if not args.json:
        verb = "Copied" if args.copy else "Moved"
        print(f"{verb} {completed} files; {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
