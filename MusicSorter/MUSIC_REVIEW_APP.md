# Music Review App

This repo now includes a small desktop app for reviewing files from:

- `D:\Music\just music`

and sorting cleaned tracks into:

- `D:\Music\_Sorted_By_Artist`

## Run

Install the tag editing dependency:

```powershell
python -m pip install -r requirements.txt
```

Start the app:

```powershell
python music_review_app.py
```

## Workflow

1. Click `Scan`.
2. Select a file in the left list.
3. Fix title, artist, album, album artist, genre, date, or track number.
4. Use `Save Metadata` to only update tags, or `Save + Sort` to update tags and move the file into the sorted artist folder.

The app sorts files with album metadata as:

```text
D:\Music\_Sorted_By_Artist\Artist\Album\01 - Title.ext
```

If album metadata is blank, the file goes directly under the artist folder.

Possible duplicates are flagged with `*` when the app finds an existing file at the same target path in the sorted library.


