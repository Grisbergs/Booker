# Music Organizer

A small, local-first command-line tool that reads embedded metadata from music
files and sorts them into:

```text
Artist/
└── Album/
    └── song.mp3
```

Files with missing tags are placed under `Unknown Artist` or `Unknown Album`.
Name collisions are preserved by adding `(2)`, `(3)`, and so on. The tool
previews everything by default and does not contact any online service.

## Install

Python 3.9 or newer is recommended.

```bash
python -m pip install -r requirements.txt
```

## Use

Preview the proposed moves:

```bash
python music_organizer.py "/path/to/Music"
```

Apply them:

```bash
python music_organizer.py "/path/to/Music" --apply
```

Copy files instead of moving them:

```bash
python music_organizer.py "/path/to/Music" --apply --copy
```

Choose another destination:

```bash
python music_organizer.py "/path/to/Music" --output "/path/to/Sorted Music"
```

For scripting, add `--json` to receive the plan as structured JSON.

Supported extensions include MP3, FLAC, M4A/MP4, OGG/Opus, WAV, WMA, AAC,
AIFF, APE, ALAC, and WavPack, subject to Mutagen format support.
