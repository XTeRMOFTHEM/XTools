#!/usr/bin/env python3
"""imgpress — Batch image optimizer: resize, convert, compress.

Shrinks folders of photos for the web. Never touches your originals unless
you tell it to; outputs go to a separate folder with a suffix by default.

Requires:  pip install pillow

Usage:
    python imgpress.py ~/Photos --to webp --quality 80
    python imgpress.py ~/Photos --max-width 1920 --out ~/Photos/web
    python imgpress.py ~/Photos --info
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if os.name == "nt":
    os.system("")

FORMATS = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}

COLOR = {"green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m",
         "cyan": "\033[96m", "dim": "\033[2m", "bold": "\033[1m", "end": "\033[0m"}


def c(text: str, *styles: str) -> str:
    if sys.stdout.isatty() and os.environ.get("NO_COLOR") is None:
        return "".join(COLOR[s] for s in styles) + text + COLOR["end"]
    return text


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


def process(path: Path, out_dir: Path, to: str, max_width: int | None,
            quality: int, suffix: str) -> tuple[Path, int, int]:
    from PIL import Image

    with Image.open(path) as im:
        im.load()
        width, height = im.size
        if max_width and width > max_width:
            height = round(height * max_width / width)
            width = max_width
            im = im.resize((width, height), Image.LANCZOS)

        fmt = FORMATS[to]
        dst = out_dir / f"{path.stem}{suffix}.{to}"
        if fmt == "JPEG" and im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        if fmt == "WEBP" and im.mode == "P":
            im = im.convert("RGB")
        save_kwargs: dict = {"quality": quality}
        if fmt == "PNG":
            save_kwargs = {"optimize": True}
        im.save(dst, fmt, **save_kwargs)
    return dst, path.stat().st_size, dst.stat().st_size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="imgpress", description="Batch-resize / convert / compress images.")
    parser.add_argument("target", type=Path, help="image file or folder (scanned recursively)")
    parser.add_argument("--to", choices=list(FORMATS), default="webp",
                        help="output format (default: webp)")
    parser.add_argument("--max-width", type=int, default=None, metavar="PX",
                        help="downscale images wider than PX (aspect preserved)")
    parser.add_argument("--quality", type=int, default=82, metavar="1-100",
                        help="output quality for lossy formats (default: 82)")
    parser.add_argument("--out", type=Path, default=None, metavar="DIR",
                        help="output folder (default: <target>/imgpress-out)")
    parser.add_argument("--suffix", default="_opt",
                        help="filename suffix for outputs (default: _opt)")
    parser.add_argument("--overwrite", action="store_true",
                        help="allow replacing existing output files")
    args = parser.parse_args(argv)

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        parser.error("Pillow is required:  pip install pillow")

    target = args.target.expanduser().resolve()
    if target.is_file():
        files = [target]
        base = target.parent
    elif target.is_dir():
        files = sorted(p for p in target.rglob("*")
                       if p.is_file() and p.suffix.lower() in SUPPORTED)
        base = target
    else:
        parser.error(f"not a file or directory: {target}")
    files = [f for f in files if f.suffix.lower() != f".{args.to}" or args.overwrite]

    if not files:
        print(c("No supported images found.", "yellow"))
        return 1

    out_dir = (args.out.expanduser() if args.out else base / "imgpress-out").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(c(f"\n  {len(files)} image(s)  →  {out_dir.name}/  ({args.to}, q={args.quality})\n", "bold", "cyan"))
    total_before = total_after = done = skipped = 0
    for path in files:
        try:
            dst, before, after = process(path, out_dir, args.to,
                                         args.max_width, args.quality, args.suffix)
        except Exception as exc:  # noqa: BLE001 — keep the batch going
            print(c(f"  ✗ {path.name}: {exc}", "red"))
            continue
        if after >= before:
            skipped += 1
            total_before += before
            total_after += before  # don't count worse outputs
            dst.unlink(missing_ok=True)
            print(c(f"  • {path.name}  {human(before)}", "dim") +
                  c("  skipped (no gain)", "yellow"))
            continue
        done += 1
        total_before += before
        total_after += after
        gain = (1 - after / before) * 100
        print(f"  ✓ {path.name}  {c(human(before), 'dim')} → {human(after)}"
              + c(f"  (-{gain:.0f}%)", "green"))

    if total_before:
        print(c(f"\n  {done} optimized  •  {skipped} skipped  •  "
                f"{human(total_before)} → {human(total_after)}  "
                f"({(1 - total_after / total_before) * 100:.0f}% saved)\n", "bold"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
