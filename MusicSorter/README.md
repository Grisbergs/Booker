# MusicSorter

A small Python toolkit for building an inventory of music directories and files before planning any renames or moves.

The first step is intentionally read-only: scan a music folder, store the results in SQLite, and export CSV files for review.

## Quick Start

```bash
python3 scan_music.py /path/to/music
```

That creates:

- `music_inventory.db`
- `exports/files.csv`
- `exports/directories.csv`

You can re-run the scanner safely. Existing inventory rows are replaced for the scanned root.

## Why SQLite?

SQLite gives us a durable catalog that Python can query later when we start adding sorting and renaming rules. It also lets us keep planned paths separate from current paths, which makes review and undo workflows much safer.

## Current Tables

- `scan_roots`: one row per scanned source folder
- `directories`: every discovered subdirectory
- `files`: every discovered file, with path, extension, size, timestamps, and optional audio metadata columns

The scanner does not rename, move, or delete anything.

## Review Interface

Run the local validation dashboard with:

```bash
python3 review_app.py
```

Then open:

```text
http://127.0.0.1:8765
```

The interface writes review decisions to separate database columns:

- `reviewed_artist`
- `reviewed_album`
- `reviewed_title`
- `review_status`
- `review_notes`
- `reviewed_at`

It does not rename, move, or delete music files.

## Artist Folder Moves

Create a dry-run move plan:

```bash
python3 plan_artist_moves.py
```

Apply the approved move plan:

```bash
python3 plan_artist_moves.py --apply
```

By default, approved tracks with album metadata are moved into:

```text
D:\Music\_Sorted_By_Artist\<Artist>\<Album>\<Filename>
```

Tracks without album metadata are moved directly under the artist folder:

```text
D:\Music\_Sorted_By_Artist\<Artist>\<Filename>
```

The generated plan is written to:

- `exports_d_music/move_plan.csv`

Rows marked `needs_review`, `skipped`, `metadata-error`, or unresolved missing metadata are not moved.

## Duplicate Purge

Create a dry-run duplicate plan for sorted tracks:

```bash
python3 purge_duplicates.py
```

Quarantine duplicate files:

```bash
python3 purge_duplicates.py --apply
```

Duplicates are grouped by normalized metadata artist, album, and title. The largest file in each duplicate group is kept. Other copies are moved to:

```text
D:\Music\_Duplicate_Quarantine
```

The plan is written to:

- `exports_d_music/duplicate_purge_plan.csv`
## Metadata Editing App

For the new review inbox, run the desktop metadata editor:

```powershell
python -m pip install -r requirements.txt
python music_review_app.py
```

It defaults to reviewing:

```text
D:\Music\just music
```

and moves saved tracks with album metadata into:

```text
D:\Music\_Sorted_By_Artist\<Artist>\<Album>\01 - Title.ext
```

If album metadata is blank, the app moves the track directly under the artist folder.

Use `Save Metadata` to only write tags, or `Save + Sort` to write tags and move the file. Existing files at the same target path are shown as possible duplicates before you sort.



