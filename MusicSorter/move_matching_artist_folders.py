#!/usr/bin/env python3
"""Move files from Just Music artist folders into matching sorted artist folders."""

from __future__ import annotations

import argparse
import csv
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_JUST_MUSIC = Path(r"D:\Music\just music")
DEFAULT_SORTED = Path(r"D:\Music\_Sorted_By_Artist")
DEFAULT_REPORT = Path(r"D:\Music\music_inventory_exports_refreshed\matching_artist_folder_moves.csv")


@dataclass(frozen=True)
class MoveRow:
    action: str
    reason: str
    artist_folder: str
    source_path: Path
    destination_path: Path


def folder_key(path: Path) -> str:
    return path.name.strip().casefold()


def build_sorted_artist_index(sorted_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for child in sorted_root.iterdir():
        if child.is_dir():
            index.setdefault(folder_key(child), child)
    return index


def unique_destination(path: Path, planned: set[str]) -> Path:
    candidate = path
    counter = 2
    while str(candidate).casefold() in planned or candidate.exists():
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        counter += 1
    planned.add(str(candidate).casefold())
    return candidate


def build_plan(just_root: Path, sorted_root: Path) -> list[MoveRow]:
    sorted_artists = build_sorted_artist_index(sorted_root)
    planned: set[str] = set()
    rows: list[MoveRow] = []

    for artist_dir in sorted(just_root.iterdir(), key=lambda item: item.name.casefold()):
        if not artist_dir.is_dir():
            continue
        sorted_artist_dir = sorted_artists.get(folder_key(artist_dir))
        if sorted_artist_dir is None:
            continue

        for source in sorted(artist_dir.rglob("*"), key=lambda item: str(item).casefold()):
            if not source.is_file():
                continue
            relative = source.relative_to(artist_dir)
            destination = unique_destination(sorted_artist_dir / relative, planned)
            rows.append(
                MoveRow(
                    action="move",
                    reason="top-level Just Music artist folder matches an existing sorted artist folder",
                    artist_folder=sorted_artist_dir.name,
                    source_path=source,
                    destination_path=destination,
                )
            )
    return rows


def write_report(rows: list[MoveRow], report: Path, results: dict[str, str] | None = None) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "action",
                "reason",
                "artist_folder",
                "source_path",
                "destination_path",
                "moved_at",
                "move_error",
            ],
        )
        writer.writeheader()
        for row in rows:
            key = str(row.source_path)
            result = results.get(key, "") if results else ""
            writer.writerow(
                {
                    "action": row.action,
                    "reason": row.reason,
                    "artist_folder": row.artist_folder,
                    "source_path": row.source_path,
                    "destination_path": row.destination_path,
                    "moved_at": result if result and not result.startswith("ERROR: ") else "",
                    "move_error": result[7:] if result.startswith("ERROR: ") else "",
                }
            )


def apply_plan(rows: list[MoveRow]) -> tuple[int, int, dict[str, str]]:
    moved = 0
    failed = 0
    results: dict[str, str] = {}
    for row in rows:
        key = str(row.source_path)
        try:
            row.destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(row.source_path), str(row.destination_path))
            results[key] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            moved += 1
        except Exception as exc:
            results[key] = f"ERROR: {exc}"
            failed += 1
    return moved, failed, results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Move files from Just Music artist folders into matching sorted artist folders."
    )
    parser.add_argument("--just-music", type=Path, default=DEFAULT_JUST_MUSIC)
    parser.add_argument("--sorted", type=Path, default=DEFAULT_SORTED)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--apply", action="store_true", help="Actually move files. Dry-run by default.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_plan(args.just_music, args.sorted)
    results: dict[str, str] | None = None
    moved = failed = 0
    if args.apply:
        moved, failed, results = apply_plan(rows)
    write_report(rows, args.report, results)

    matched_artists = len({row.artist_folder.casefold() for row in rows})
    print(f"Matched artist folders with files: {matched_artists}")
    print(f"Files planned: {len(rows)}")
    print(f"Report: {args.report}")
    if args.apply:
        print(f"Moved: {moved}")
        print(f"Failed: {failed}")
    else:
        print("Dry run only. Re-run with --apply to move files.")


if __name__ == "__main__":
    main()
