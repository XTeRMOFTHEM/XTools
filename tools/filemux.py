#!/usr/bin/env python3
"""filemux — Smart file organizer for messy folders (Downloads, Desktop, ...).

Sorts files into category folders (Images, Documents, Video, ...), by month,
or by extension. Dry-run by default; every applied run is journaled so it can
be undone with a single command.

Usage:
    python filemux.py ~/Downloads            # preview the plan
    python filemux.py ~/Downloads --apply    # actually move files
    python filemux.py ~/Downloads --by date  # group into YYYY-MM folders
    python filemux.py ~/Downloads --undo     # revert the last applied run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

if os.name == "nt":
    os.system("")  # enable ANSI escape codes on Windows terminals

JOURNAL_NAME = ".filemux_journal.json"

CATEGORIES: dict[str, set[str]] = {
    "Images": {"jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "ico", "tiff", "heic"},
    "Documents": {"pdf", "doc", "docx", "txt", "md", "rtf", "odt", "ppt", "pptx"},
    "Spreadsheets": {"xls", "xlsx", "csv", "ods"},
    "Audio": {"mp3", "wav", "flac", "aac", "ogg", "m4a", "wma"},
    "Video": {"mp4", "mkv", "avi", "mov", "webm", "flv", "wmv"},
    "Archives": {"zip", "rar", "7z", "tar", "gz", "bz2", "xz", "iso"},
    "Code": {"py", "js", "ts", "html", "css", "java", "kt", "c", "cpp", "h", "cs",
             "go", "rs", "rb", "php", "sh", "bat", "ps1", "json", "xml", "yml",
             "yaml", "sql", "dart", "lua"},
    "Fonts": {"ttf", "otf", "woff", "woff2"},
    "Executables": {"exe", "msi", "apk", "dmg", "deb", "rpm", "appimage"},
}

COLOR = {"cyan": "\033[96m", "green": "\033[92m", "yellow": "\033[93m",
         "red": "\033[91m", "dim": "\033[2m", "bold": "\033[1m", "end": "\033[0m"}


def c(text: str, *styles: str) -> str:
    if sys.stdout.isatty() and os.environ.get("NO_COLOR") is None:
        return "".join(COLOR[s] for s in styles) + text + COLOR["end"]
    return text


def category_of(suffix: str) -> str:
    for cat, exts in CATEGORIES.items():
        if suffix in exts:
            return cat
    return "Other"


def unique_path(path: Path) -> Path:
    """Return a non-existing path by appending ' (1)', ' (2)', ... if needed."""
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    n = 1
    while True:
        candidate = parent / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def build_plan(target: Path, mode: str, dest: Path | None) -> list[tuple[Path, Path]]:
    dest_root = dest if dest is not None else target
    plan: list[tuple[Path, Path]] = []
    for item in sorted(target.iterdir()):
        if not item.is_file() or item.name == JOURNAL_NAME:
            continue
        if mode == "type":
            sub = category_of(item.suffix.lower().lstrip("."))
            dst = dest_root / sub / item.name
        elif mode == "date":
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            dst = dest_root / mtime.strftime("%Y-%m") / item.name
        else:  # ext
            ext = item.suffix.lower().lstrip(".") or "noext"
            dst = dest_root / ext / item.name
        if dst.parent == item.parent and dst == item:
            continue
        plan.append((item, dst))
    return plan


def apply_plan(plan: list[tuple[Path, Path]]) -> list[tuple[str, str]]:
    journal: list[tuple[str, str]] = []
    for src, dst in plan:
        dst.parent.mkdir(parents=True, exist_ok=True)
        final = unique_path(dst)
        src.rename(final)
        journal.append((str(src), str(final)))
    return journal


def undo(target: Path) -> None:
    journal_path = target / JOURNAL_NAME
    if not journal_path.exists():
        print(c("No journal found — nothing to undo.", "yellow"))
        return
    moves = [(Path(dst), Path(src)) for src, dst in json.loads(journal_path.read_text(encoding="utf-8"))]
    restored = 0
    touched_folders: set[Path] = set()
    for dst, src in moves:  # journal stores (original, new) — reverse them
        if dst.exists():
            touched_folders.add(dst.parent)
            src.parent.mkdir(parents=True, exist_ok=True)
            dst.rename(src)
            restored += 1
    journal_path.unlink()
    for folder in touched_folders:  # clean up now-empty category folders
        try:
            folder.rmdir()
        except OSError:
            pass
    print(c(f"↩  Restored {restored} file(s).", "green"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="filemux", description="Organize a messy folder — dry-run by default.")
    parser.add_argument("target", type=Path, help="folder to organize")
    parser.add_argument("--by", choices=["type", "date", "ext"], default="type",
                        help="grouping strategy (default: type)")
    parser.add_argument("--dest", type=Path, default=None,
                        help="move files into this folder instead of organizing in place")
    parser.add_argument("--apply", action="store_true",
                        help="actually move files (default is a dry-run preview)")
    parser.add_argument("--undo", action="store_true",
                        help="revert the last applied run in TARGET")
    args = parser.parse_args(argv)

    target = args.target.expanduser().resolve()
    if args.undo:
        undo(target)
        return 0
    if not target.is_dir():
        parser.error(f"not a directory: {target}")

    plan = build_plan(target, args.by, args.dest.expanduser() if args.dest else None)
    if not plan:
        print(c("Nothing to do — folder is already clean. ✨", "green"))
        return 0

    grouped: dict[str, list[tuple[Path, Path]]] = defaultdict(list)
    for src, dst in plan:
        grouped[dst.parent.name].append((src, dst))

    print(c(f"\n  Plan for {target.name}  ({args.by})  —  {len(plan)} file(s)\n", "bold", "cyan"))
    for folder, moves in sorted(grouped.items()):
        print(c(f"  📁 {folder}", "bold"))
        for src, dst in moves:
            print(c(f"     {src.name}", "dim") + "  →  " + dst.name)
    print()

    if not args.apply:
        print(c("Dry run — nothing moved. Add ", "yellow") +
              c("--apply", "bold") + c(" to execute.", "yellow"))
        return 0

    journal = apply_plan(plan)
    dest_root = (args.dest.expanduser() if args.dest else target).resolve()
    (dest_root / JOURNAL_NAME).write_text(
        json.dumps(journal, ensure_ascii=False), encoding="utf-8")
    print(c(f"✓  Moved {len(journal)} file(s). Revert anytime with ", "green") +
          c(f"--undo", "bold") + c(".", "green"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
