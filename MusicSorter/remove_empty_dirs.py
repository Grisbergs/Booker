#!/usr/bin/env python3
"""Find and optionally remove empty directories from the original music tree."""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path


DEFAULT_ROOT = Path("/mnt/d/Music")
DEFAULT_REPORT = Path("exports_d_music/empty_directories.csv")
DEFAULT_EXCLUDES = {"_Sorted_By_Artist"}


def is_excluded(path: Path, root: Path, excludes: set[str]) -> bool:
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        return True
    return bool(relative_parts and relative_parts[0] in excludes)


def find_empty_dirs(root: Path, excludes: set[str]) -> list[Path]:
    empty_dirs: list[Path] = []
    for current, dirnames, filenames in os.walk(root, topdown=False):
        current_path = Path(current)
        if current_path == root or is_excluded(current_path, root, excludes):
            continue
        if filenames:
            continue
        if any((current_path / dirname).exists() for dirname in dirnames):
            continue
        empty_dirs.append(current_path)
    return empty_dirs


def write_report(paths: list[Path], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["path"])
        for path in paths:
            writer.writerow([path])


def remove_dirs(paths: list[Path]) -> tuple[int, list[tuple[Path, str]]]:
    removed = 0
    failures: list[tuple[Path, str]] = []
    for path in paths:
        try:
            path.rmdir()
            removed += 1
        except OSError as exc:
            failures.append((path, str(exc)))
    return removed, failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find and optionally remove empty directories under the original music root."
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--exclude",
        action="append",
        default=sorted(DEFAULT_EXCLUDES),
        help="Top-level folder name to exclude. Can be repeated.",
    )
    parser.add_argument("--apply", action="store_true", help="Actually remove empty directories.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root is not a directory: {root}")

    excludes = set(args.exclude or [])
    empty_dirs = find_empty_dirs(root, excludes)
    write_report(empty_dirs, args.report)

    print(f"Root: {root}")
    print(f"Excluded top-level folders: {', '.join(sorted(excludes)) or 'none'}")
    print(f"Empty directories found: {len(empty_dirs)}")
    print(f"Report: {args.report}")

    if not args.apply:
        print("Dry run only. Re-run with --apply to remove these directories.")
        return

    removed, failures = remove_dirs(empty_dirs)
    print(f"Removed: {removed}")
    print(f"Failed: {len(failures)}")
    for path, error in failures[:20]:
        print(f"Failed: {path} | {error}")


if __name__ == "__main__":
    main()
