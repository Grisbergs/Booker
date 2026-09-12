#!/usr/bin/env python3
"""Small desktop app for reviewing music metadata before sorting by artist."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, TOP, VERTICAL, W, X, Y, Button, Entry, Frame, Label, Listbox, Scrollbar, StringVar, Tk, filedialog, messagebox, ttk

try:
    from mutagen import File as MutagenFile
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import ID3NoHeaderError
    from mutagen.mp4 import MP4
except ImportError:  # pragma: no cover - shown in GUI/CLI at runtime
    MutagenFile = None
    EasyID3 = None
    ID3NoHeaderError = Exception
    MP4 = None


REVIEW_DIR = Path(r"D:\Music\just music")
SORTED_DIR = Path(r"D:\Music\_Sorted_By_Artist")
SUPPORTED_EXTENSIONS = {
    ".aac",
    ".aiff",
    ".alac",
    ".ape",
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}


@dataclass
class Track:
    path: Path
    title: str = ""
    artist: str = ""
    album: str = ""
    albumartist: str = ""
    genre: str = ""
    date: str = ""
    tracknumber: str = ""
    duplicate_hint: str = ""


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def clean_part(value: str, fallback: str) -> str:
    value = value.strip() or fallback
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value or fallback


def first_tag(tags: dict, key: str) -> str:
    value = tags.get(key, [""])
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def first_mp4_text(tags: dict, key: str) -> str:
    value = tags.get(key, [])
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def parse_track_pair(value: str) -> tuple[int, int]:
    match = re.match(r"\s*(\d+)(?:\s*/\s*(\d+))?", value or "")
    if not match:
        return (0, 0)
    return (int(match.group(1)), int(match.group(2) or 0))


def read_mp4_track(path: Path) -> Track:
    if MP4 is None:
        raise ValueError("MP4 support requires mutagen. Install it with: python -m pip install mutagen")
    audio = MP4(path)
    tags = audio.tags or {}
    track_pairs = tags.get("trkn", [])
    tracknumber = ""
    if track_pairs:
        number, total = track_pairs[0]
        tracknumber = f"{number}/{total}" if total else str(number)
    title = first_mp4_text(tags, "\xa9nam") or path.stem
    return Track(
        path=path,
        title=title,
        artist=first_mp4_text(tags, "\xa9ART"),
        album=first_mp4_text(tags, "\xa9alb"),
        albumartist=first_mp4_text(tags, "aART"),
        genre=first_mp4_text(tags, "\xa9gen"),
        date=first_mp4_text(tags, "\xa9day"),
        tracknumber=tracknumber,
    )


def read_track(path: Path) -> Track:
    if path.suffix.casefold() in {".m4a", ".mp4"}:
        return read_mp4_track(path)
    audio = MutagenFile(path, easy=True)
    tags = dict(audio or {})
    title = first_tag(tags, "title") or path.stem
    return Track(
        path=path,
        title=title,
        artist=first_tag(tags, "artist"),
        album=first_tag(tags, "album"),
        albumartist=first_tag(tags, "albumartist"),
        genre=first_tag(tags, "genre"),
        date=first_tag(tags, "date"),
        tracknumber=first_tag(tags, "tracknumber"),
    )


def ensure_mp3_tags(path: Path) -> None:
    if path.suffix.casefold() != ".mp3":
        return
    try:
        EasyID3(path)
    except ID3NoHeaderError:
        tags = EasyID3()
        tags.save(path)


def write_mp4_text(tags: dict, key: str, value: str) -> None:
    value = value.strip()
    if value:
        tags[key] = [value]
    elif key in tags:
        del tags[key]


def write_mp4_track(track: Track) -> None:
    if MP4 is None:
        raise ValueError("MP4 support requires mutagen. Install it with: python -m pip install mutagen")
    audio = MP4(track.path)
    if audio.tags is None:
        audio.add_tags()
    tags = audio.tags
    write_mp4_text(tags, "\xa9nam", track.title)
    write_mp4_text(tags, "\xa9ART", track.artist)
    write_mp4_text(tags, "\xa9alb", track.album)
    write_mp4_text(tags, "aART", track.albumartist)
    write_mp4_text(tags, "\xa9gen", track.genre)
    write_mp4_text(tags, "\xa9day", track.date)
    track_pair = parse_track_pair(track.tracknumber)
    if track_pair[0]:
        tags["trkn"] = [track_pair]
    elif "trkn" in tags:
        del tags["trkn"]
    audio.save()


def write_track(track: Track) -> None:
    if track.path.suffix.casefold() in {".m4a", ".mp4"}:
        write_mp4_track(track)
        return

    ensure_mp3_tags(track.path)
    audio = MutagenFile(track.path, easy=True)
    if audio is None:
        raise ValueError(f"Unsupported or unreadable audio file: {track.path}")

    values = {
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "albumartist": track.albumartist,
        "genre": track.genre,
        "date": track.date,
        "tracknumber": track.tracknumber,
    }
    for key, value in values.items():
        if value.strip():
            audio[key] = [value.strip()]
        elif key in audio:
            del audio[key]
    audio.save()


def target_path(track: Track, sorted_dir: Path) -> Path:
    artist = clean_part(track.albumartist or track.artist, "Unknown Artist")
    title = clean_part(track.title or track.path.stem, track.path.stem)
    prefix = ""
    if track.tracknumber.strip():
        number = re.match(r"\d+", track.tracknumber.strip())
        if number:
            prefix = f"{int(number.group(0)):02d} - "
    filename = f"{prefix}{title}{track.path.suffix.lower()}"
    artist_destination = sorted_dir / artist
    if track.album.strip():
        return artist_destination / clean_part(track.album, "Unknown Album") / filename
    return artist_destination / filename


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


class MusicReviewApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Music Metadata Review")
        self.review_dir = StringVar(value=str(REVIEW_DIR))
        self.sorted_dir = StringVar(value=str(SORTED_DIR))
        self.status = StringVar(value="Ready")
        self.current_index = -1
        self.tracks: list[Track] = []
        self.sorted_index: dict[str, list[Path]] = {}
        self.fields = {
            "title": StringVar(),
            "artist": StringVar(),
            "album": StringVar(),
            "albumartist": StringVar(),
            "genre": StringVar(),
            "date": StringVar(),
            "tracknumber": StringVar(),
        }
        self.path_var = StringVar()
        self.target_var = StringVar()
        self.duplicate_var = StringVar()
        self._build_ui()

    def _build_ui(self) -> None:
        self.root.geometry("1120x720")
        self.root.minsize(900, 560)

        top = Frame(self.root, padx=10, pady=8)
        top.pack(side=TOP, fill=X)
        self._path_row(top, "Review", self.review_dir, self.choose_review_dir).pack(fill=X, pady=2)
        self._path_row(top, "Sorted", self.sorted_dir, self.choose_sorted_dir).pack(fill=X, pady=2)

        actions = Frame(top)
        actions.pack(fill=X, pady=(8, 0))
        Button(actions, text="Scan", command=self.scan).pack(side=LEFT)
        Button(actions, text="Save Metadata", command=self.save_current).pack(side=LEFT, padx=6)
        Button(actions, text="Save + Sort", command=self.save_and_sort).pack(side=LEFT)
        Button(actions, text="Skip", command=self.next_track).pack(side=LEFT, padx=6)
        Label(actions, textvariable=self.status).pack(side=RIGHT)

        body = Frame(self.root, padx=10, pady=8)
        body.pack(fill=BOTH, expand=True)

        left = Frame(body)
        left.pack(side=LEFT, fill=Y)
        scrollbar = Scrollbar(left, orient=VERTICAL)
        self.listbox = Listbox(left, width=44, yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.pack(side=LEFT, fill=Y)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        right = Frame(body, padx=16)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        Label(right, text="File").grid(row=0, column=0, sticky=W, pady=(0, 4))
        Entry(right, textvariable=self.path_var, state="readonly").grid(row=0, column=1, sticky="ew", pady=(0, 4))

        row = 1
        labels = {
            "title": "Title",
            "artist": "Artist",
            "album": "Album",
            "albumartist": "Album Artist",
            "genre": "Genre",
            "date": "Year/Date",
            "tracknumber": "Track #",
        }
        for key, label in labels.items():
            Label(right, text=label).grid(row=row, column=0, sticky=W, pady=4)
            Entry(right, textvariable=self.fields[key]).grid(row=row, column=1, sticky="ew", pady=4)
            row += 1

        Label(right, text="Sort Target").grid(row=row, column=0, sticky=W, pady=(12, 4))
        Entry(right, textvariable=self.target_var, state="readonly").grid(row=row, column=1, sticky="ew", pady=(12, 4))
        row += 1
        Label(right, text="Possible Duplicates").grid(row=row, column=0, sticky=W, pady=4)
        Entry(right, textvariable=self.duplicate_var, state="readonly").grid(row=row, column=1, sticky="ew", pady=4)

        for variable in self.fields.values():
            variable.trace_add("write", lambda *_: self.refresh_preview())
        right.columnconfigure(1, weight=1)

    def _path_row(self, parent: Frame, label: str, variable: StringVar, command) -> Frame:
        row = Frame(parent)
        Label(row, text=label, width=8, anchor=W).pack(side=LEFT)
        Entry(row, textvariable=variable).pack(side=LEFT, fill=X, expand=True)
        Button(row, text="Browse", command=command).pack(side=LEFT, padx=(6, 0))
        return row

    def choose_review_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.review_dir.get())
        if chosen:
            self.review_dir.set(chosen)

    def choose_sorted_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.sorted_dir.get())
        if chosen:
            self.sorted_dir.set(chosen)

    def scan(self) -> None:
        if MutagenFile is None:
            messagebox.showerror("Missing dependency", "Install mutagen first:\n\npython -m pip install mutagen")
            return
        self.status.set("Scanning...")
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self) -> None:
        try:
            review = Path(self.review_dir.get())
            sorted_dir = Path(self.sorted_dir.get())
            tracks: list[Track] = []
            scan_errors: list[str] = []
            for path in review.rglob("*"):
                if path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
                    continue
                try:
                    tracks.append(read_track(path))
                    if len(tracks) % 25 == 0:
                        count = len(tracks)
                        self.root.after(0, lambda count=count: self.status.set(f"Scanning... loaded {count} review files"))
                except Exception as exc:
                    scan_errors.append(f"{path}: {exc}")

            sorted_index: dict[str, list[Path]] = {}
            for track in tracks:
                destination = target_path(track, sorted_dir)
                if destination.exists():
                    track.duplicate_hint = str(destination)
            self.root.after(0, lambda: self._scan_done(tracks, sorted_index, scan_errors))
        except Exception as exc:
            error = str(exc)
            self.root.after(0, lambda: messagebox.showerror("Scan failed", error))
            self.root.after(0, lambda: self.status.set("Scan failed"))

    def _build_sorted_index(self, sorted_dir: Path) -> dict[str, list[Path]]:
        index: dict[str, list[Path]] = {}
        if not sorted_dir.exists():
            return index
        for path in sorted_dir.rglob("*"):
            if path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                track = read_track(path)
                key = self.track_key(track)
                if key:
                    index.setdefault(key, []).append(path)
            except Exception:
                continue
        return index

    def _scan_done(self, tracks: list[Track], sorted_index: dict[str, list[Path]], scan_errors: list[str]) -> None:
        self.tracks = tracks
        self.sorted_index = sorted_index
        self.listbox.delete(0, END)
        for track in tracks:
            marker = " *" if track.duplicate_hint else ""
            self.listbox.insert(END, f"{track.artist or 'Unknown'} - {track.title}{marker}")
        status = f"Found {len(tracks)} review files"
        if scan_errors:
            status += f"; skipped {len(scan_errors)} unreadable files"
        self.status.set(status)
        if scan_errors:
            shown = "\n".join(scan_errors[:12])
            extra = "" if len(scan_errors) <= 12 else f"\n\n...and {len(scan_errors) - 12} more."
            messagebox.showwarning(
                "Skipped unreadable files",
                f"These files could not be read as audio metadata:\n\n{shown}{extra}",
            )
        if tracks:
            self.listbox.selection_set(0)
            self.load_track(0)

    def track_key(self, track: Track) -> str:
        artist = normalize_key(track.artist or track.albumartist)
        title = normalize_key(track.title)
        return f"{artist}:{title}" if artist and title else ""

    def on_select(self, _event=None) -> None:
        selection = self.listbox.curselection()
        if selection:
            self.load_track(selection[0])

    def load_track(self, index: int) -> None:
        self.current_index = index
        track = self.tracks[index]
        self.path_var.set(str(track.path))
        for key, variable in self.fields.items():
            variable.set(getattr(track, key))
        self.duplicate_var.set(track.duplicate_hint or "No exact target-path duplicate found")
        self.refresh_preview()

    def current_track_from_form(self) -> Track:
        if self.current_index < 0:
            raise ValueError("No track selected")
        original = self.tracks[self.current_index]
        return Track(
            path=original.path,
            title=self.fields["title"].get(),
            artist=self.fields["artist"].get(),
            album=self.fields["album"].get(),
            albumartist=self.fields["albumartist"].get(),
            genre=self.fields["genre"].get(),
            date=self.fields["date"].get(),
            tracknumber=self.fields["tracknumber"].get(),
            duplicate_hint=original.duplicate_hint,
        )

    def refresh_preview(self) -> None:
        if self.current_index < 0:
            self.target_var.set("")
            return
        try:
            self.target_var.set(str(target_path(self.current_track_from_form(), Path(self.sorted_dir.get()))))
        except Exception:
            self.target_var.set("")

    def save_current(self) -> None:
        try:
            track = self.current_track_from_form()
            write_track(track)
            self.tracks[self.current_index] = track
            self.status.set("Metadata saved")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    def save_and_sort(self) -> None:
        try:
            track = self.current_track_from_form()
            write_track(track)
            intended_destination = target_path(track, Path(self.sorted_dir.get()))
            intended_destination.parent.mkdir(parents=True, exist_ok=True)
            if intended_destination.exists() and file_hash(track.path) == file_hash(intended_destination):
                track.path.unlink()
                destination = intended_destination
            else:
                destination = unique_path(intended_destination)
                shutil.move(str(track.path), str(destination))
            self.remove_current()
            self.status.set(f"Sorted to {destination}")
        except Exception as exc:
            messagebox.showerror("Sort failed", str(exc))

    def remove_current(self) -> None:
        index = self.current_index
        self.listbox.delete(index)
        del self.tracks[index]
        self.current_index = -1
        if self.tracks:
            next_index = min(index, len(self.tracks) - 1)
            self.listbox.selection_set(next_index)
            self.load_track(next_index)
        else:
            self.path_var.set("")
            self.target_var.set("")
            self.duplicate_var.set("")
            for variable in self.fields.values():
                variable.set("")

    def next_track(self) -> None:
        if not self.tracks:
            return
        next_index = min(self.current_index + 1, len(self.tracks) - 1)
        self.listbox.selection_clear(0, END)
        self.listbox.selection_set(next_index)
        self.load_track(next_index)


def main() -> int:
    root = Tk()
    style = ttk.Style()
    if "vista" in style.theme_names():
        style.theme_use("vista")
    app = MusicReviewApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())






