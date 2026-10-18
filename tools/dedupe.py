#!/usr/bin/env python3
"""dedupe — Fast duplicate file finder.

Finds duplicate files by size → partial hash → full hash (SHA-256), then
reports them grouped, with the total wasted space. Never deletes anything
unless you explicitly ask for it.

Usage:
    python dedupe.py ~/Pictures                    # just report
    python dedupe.py ~/Downloads --min-size 1MB    # skip tiny files
    python dedupe.py ~/Pictures --move-to ~/Trash  # keep 1 copy per group
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

if os.name == "nt":
    os.system("")

CHUNK = 1 << 16

COLOR = {"green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m",
         "cyan": "\033[96m", "dim": "\033[2m", "bold": "\033[1m", "end": "\033[0m"}


def c(text: str, *styles: str) -> str:
    if sys.stdout.isatty() and os.environ.get("NO_COLOR") is None:
        return "".join(COLOR[s] for s in styles) + text + COLOR["end"]
    return text


def parse_size(text: str) -> int:
    units = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}
    m = text.strip().lower()
    for suffix, factor in sorted(units.items(), key=lambda kv: -len(kv[0])):
        if m.endswith(suffix):
            return int(float(m[: -len(suffix)]) * factor)
    return int(m)


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} PB"


def hash_file(path: Path, full: bool = True, size: int | None = None) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        if not full:
            h.update(f.read(CHUNK))
            return h.hexdigest()
        while block := f.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def find_duplicates(root: Path, min_size: int) -> list[list[Path]]:
    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            size = path.stat().st_size
            if size >= min_size:
                by_size[size].append(path)
    candidates = [files for files in by_size.values() if len(files) > 1]

    by_head: dict[tuple[int, str], list[Path]] = defaultdict(list)
    for files in candidates:
        for path in files:
            by_head[(path.stat().st_size, hash_file(path, full=False))].append(path)

    by_full: dict[str, list[Path]] = defaultdict(list)
    for files in by_head.values():
        if len(files) > 1:
            for path in files:
                by_full[hash_file(path)].append(path)

    return sorted(
        (sorted(files) for files in by_full.values() if len(files) > 1),
        key=lambda g: g[0].stat().st_size,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dedupe", description="Find duplicate files — report by default, delete only on request.")
    parser.add_argument("target", type=Path, help="folder to scan recursively")
    parser.add_argument("--min-size", type=parse_size, default="0",
                        help="ignore files smaller than this (e.g. 100KB, 1MB)")
    parser.add_argument("--move-to", type=Path, default=None, metavar="DIR",
                        help="keep the first copy of each group and move the rest to DIR")
    parser.add_argument("--delete", action="store_true",
                        help="delete duplicates (kept copy: first in each group)")
    parser.add_argument("--yes", action="store_true",
                        help="skip the confirmation prompt")
    args = parser.parse_args(argv)

    root = args.target.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")

    groups = find_duplicates(root, args.min_size)
    if not groups:
        print(c("No duplicate files found. ✨", "green"))
        return 0

    wasted = sum(sum(f.stat().st_size for f in group[1:]) for group in groups)
    for i, group in enumerate(groups, 1):
        print(c(f"\n#{i}  {len(group)} × {human(group[0].stat().st_size)}  {c('—', 'dim')}  {group[0].name}", "bold", "cyan"))
        for j, path in enumerate(group):
            mark = c("keep  ", "green") if j == 0 else c("dupe  ", "red")
            print(f"  {mark}{c(str(path), 'dim') if j else path}")

    print(c(f"\n  {len(groups)} group(s)  •  {human(wasted)} recoverable\n", "bold"))

    if args.move_to is None and not args.delete:
        print(c("Report only — add ", "yellow") + c("--move-to DIR", "bold") +
              c(" or ", "yellow") + c("--delete", "bold") + c(" to act.", "yellow"))
        return 0

    dupes = [f for group in groups for f in group[1:]]
    if not args.yes:
        answer = input(c(f"Process {len(dupes)} duplicate file(s)? [y/N] ", "yellow"))
        if answer.strip().lower() != "y":
            print(c("Aborted — nothing changed.", "yellow"))
            return 1

    if args.move_to is not None:
        dest = args.move_to.expanduser().resolve()
        dest.mkdir(parents=True, exist_ok=True)
        moved = 0
        for path in dupes:
            target = dest / path.name
            n = 1
            while target.exists():
                target = dest / f"{path.stem} ({n}){path.suffix}"
                n += 1
            shutil.move(str(path), str(target))
            moved += 1
        print(c(f"✓  Moved {moved} duplicate(s) to {dest}", "green"))
    else:
        removed = 0
        for path in dupes:
            path.unlink()
            removed += 1
        print(c(f"✓  Deleted {removed} duplicate(s) — {human(wasted)} freed.", "green"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
