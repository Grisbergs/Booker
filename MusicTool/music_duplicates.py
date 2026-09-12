#!/usr/bin/env python3
"""Find and quarantine duplicate songs using album and title metadata."""

from __future__ import annotations

import argparse
import re
import shutil
from collections import defaultdict
from pathlib import Path

from mutagen import File as MutagenFile


EXTENSIONS = {
    ".aac", ".aiff", ".ape", ".flac", ".m4a", ".mp3", ".mp4",
    ".ogg", ".opus", ".wav", ".wma", ".wv",
}


def tag(audio, name: str) -> str:
    value = (audio.tags or {}).get(name, [""])
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value).strip()


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def safe_name(value: str, fallback: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip().rstrip(". ")
    return value or fallback


def unique_path(path: Path) -> Path:
    candidate = path
    number = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}")
        number += 1
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--delete", action="store_true")
    parser.add_argument("--quarantine", type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    quarantine = (args.quarantine or source / "Duplicate Quarantine").resolve()
    groups = defaultdict(list)

    for path in source.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        if quarantine in path.resolve().parents:
            continue
        try:
            audio = MutagenFile(path, easy=True)
            if audio is None:
                continue
            album = tag(audio, "album")
            title = tag(audio, "title")
            artist = tag(audio, "albumartist") or tag(audio, "artist")
            key = normalized(album), normalized(title)
            if all(key):
                groups[key].append((path, artist, album, title))
        except Exception as exc:
            print(f"SKIP: {path} ({exc})")

    duplicate_groups = [group for group in groups.values() if len(group) > 1]
    count = 0
    for group in duplicate_groups:
        keep = max(group, key=lambda item: (item[0].stat().st_size, str(item[0])))
        print(f"\n{keep[2]} — {keep[3]}")
        print(f"  KEEP: {keep[0]}")
        for item in group:
            if item == keep:
                continue
            count += 1
            print(f"  DUPLICATE: {item[0]}")
            if args.apply:
                if args.delete:
                    item[0].unlink()
                else:
                    destination = unique_path(
                        quarantine
                        / safe_name(item[1], "Unknown Artist")
                        / safe_name(item[2], "Unknown Album")
                        / item[0].name
                    )
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(item[0]), str(destination))

    print(f"\nFound {count} duplicate copies in {len(duplicate_groups)} groups.")
    if not args.apply:
        print("Preview only. Add --apply to quarantine duplicate copies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
