#!/usr/bin/env python3
"""pdfsmith — Swiss-army knife for PDF files.

Merge, split, extract pages, pull text, rotate, encrypt and decrypt —
all from one command, no GUI needed.

Requires:  pip install pypdf

Usage:
    python pdfsmith.py info book.pdf
    python pdfsmith.py merge a.pdf b.pdf c.pdf -o combined.pdf
    python pdfsmith.py split book.pdf --out pages/
    python pdfsmith.py extract book.pdf --pages 1-3,7 -o excerpt.pdf
    python pdfsmith.py text book.pdf --pages 2-4
    python pdfsmith.py encrypt secret.pdf --password s3cret
    python pdfsmith.py rotate slides.pdf --pages 2,4 --angle 90
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if os.name == "nt":
    os.system("")

COLOR = {"green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m",
         "cyan": "\033[96m", "dim": "\033[2m", "bold": "\033[1m", "end": "\033[0m"}


def c(text: str, *styles: str) -> str:
    if sys.stdout.isatty() and os.environ.get("NO_COLOR") is None:
        return "".join(COLOR[s] for s in styles) + text + COLOR["end"]
    return text


def parse_pages(spec: str, last_page: int) -> list[int]:
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            start = int(start) if start else 1
            end = int(end) if end else last_page
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(part))
    return sorted({p for p in pages if 1 <= p <= last_page})


def require_pypdf() -> None:
    try:
        import pypdf  # noqa: F401
    except ImportError:
        raise SystemExit(c("pypdf is required:  pip install pypdf", "red"))


def open_pdf(path: Path, password: str | None = None):
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        if not reader.decrypt(password or ""):
            raise SystemExit(c(f"wrong password for {path.name}", "red"))
    return reader


def out_path(source: Path, suffix: str, out: Path | None, default: Path | None = None) -> Path:
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        return out
    target = default or source.with_name(f"{source.stem}{suffix}.pdf")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def write_pdf(writer, dest: Path) -> None:
    with dest.open("wb") as fh:
        writer.write(fh)


def cmd_info(args) -> int:
    reader = open_pdf(args.file, args.password)
    meta = reader.metadata or {}
    size = args.file.stat().st_size
    print(c(f"\n  {args.file.name}", "bold", "cyan"))
    print(f"  pages     {len(reader.pages)}")
    print(f"  size      {size / 1024:.1f} KB")
    print(f"  encrypted {'yes' if reader.is_encrypted else 'no'}")
    for key in ("/Title", "/Author"):
        if meta.get(key):
            print(f"  {key[1:].lower():<10}{meta[key]}")
    print()
    return 0


def cmd_merge(args) -> int:
    from pypdf import PdfWriter
    writer = PdfWriter()
    for file in args.files:
        writer.append(str(file))
    dest = out_path(args.files[0], "_merged", args.out, args.out)
    write_pdf(writer, dest)
    print(c(f"✓  {len(args.files)} file(s) → {dest} ({len(writer.pages)} pages)", "green"))
    return 0


def cmd_split(args) -> int:
    reader = open_pdf(args.file, args.password)
    from pypdf import PdfWriter
    out_dir = args.out or (args.file.parent / f"{args.file.stem}_pages")
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, page in enumerate(reader.pages, 1):
        writer = PdfWriter()
        writer.add_page(page)
        write_pdf(writer, out_dir / f"{args.file.stem}_p{i:03d}.pdf")
    print(c(f"✓  {len(reader.pages)} page file(s) in {out_dir}", "green"))
    return 0


def cmd_extract(args) -> int:
    reader = open_pdf(args.file, args.password)
    pages = parse_pages(args.pages, len(reader.pages)) if args.pages else list(range(1, len(reader.pages) + 1))
    from pypdf import PdfWriter
    writer = PdfWriter()
    for p in pages:
        writer.add_page(reader.pages[p - 1])
    dest = out_path(args.file, "_extract", args.out)
    write_pdf(writer, dest)
    print(c(f"✓  {len(pages)} page(s) → {dest}", "green"))
    return 0


def cmd_text(args) -> int:
    reader = open_pdf(args.file, args.password)
    pages = parse_pages(args.pages, len(reader.pages)) if args.pages else list(range(1, len(reader.pages) + 1))
    chunks = []
    for p in pages:
        chunks.append(f"--- page {p} ---\n" + (reader.pages[p - 1].extract_text() or ""))
    text = "\n\n".join(chunks)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(c(f"✓  text from {len(pages)} page(s) → {args.out}", "green"))
    else:
        print(text)
    return 0


def cmd_encrypt(args) -> int:
    from pypdf import PdfWriter
    reader = open_pdf(args.file, args.password)
    writer = PdfWriter()
    writer.append(reader)
    writer.encrypt(args.set_password)
    dest = out_path(args.file, "_enc", args.out)
    write_pdf(writer, dest)
    print(c(f"✓  encrypted → {dest}", "green"))
    return 0


def cmd_decrypt(args) -> int:
    from pypdf import PdfWriter
    reader = open_pdf(args.file, args.password)
    writer = PdfWriter()
    writer.append(reader)
    dest = out_path(args.file, "_dec", args.out)
    write_pdf(writer, dest)
    print(c(f"✓  decrypted → {dest}", "green"))
    return 0


def cmd_rotate(args) -> int:
    reader = open_pdf(args.file, args.password)
    pages = parse_pages(args.pages, len(reader.pages)) if args.pages else list(range(1, len(reader.pages) + 1))
    from pypdf import PdfWriter
    writer = PdfWriter()
    for i, page in enumerate(reader.pages, 1):
        if i in pages:
            page.rotate(args.angle)
        writer.add_page(page)
    dest = out_path(args.file, "_rot", args.out)
    write_pdf(writer, dest)
    print(c(f"✓  rotated {len(pages)} page(s) by {args.angle}° → {dest}", "green"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pdfsmith", description="PDF toolkit: merge, split, extract, text, encrypt, rotate.")
    parser.add_argument("--password", default=None, help="password for encrypted inputs")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("info", help="show page count, size, metadata")
    p.add_argument("file", type=Path)
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("merge", help="merge multiple PDFs into one")
    p.add_argument("files", type=Path, nargs="+")
    p.add_argument("-o", "--out", type=Path, default=None)
    p.set_defaults(func=cmd_merge)

    p = sub.add_parser("split", help="split a PDF into single-page files")
    p.add_argument("file", type=Path)
    p.add_argument("--out", type=Path, default=None)
    p.set_defaults(func=cmd_split)

    p = sub.add_parser("extract", help="extract a page range into a new PDF")
    p.add_argument("file", type=Path)
    p.add_argument("--pages", default=None, help="e.g. 1-3,7 (default: all)")
    p.add_argument("-o", "--out", type=Path, default=None)
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("text", help="extract text from pages")
    p.add_argument("file", type=Path)
    p.add_argument("--pages", default=None, help="e.g. 2-4 (default: all)")
    p.add_argument("-o", "--out", type=Path, default=None)
    p.set_defaults(func=cmd_text)

    p = sub.add_parser("encrypt", help="password-protect a PDF")
    p.add_argument("file", type=Path)
    p.add_argument("--set-password", required=True)
    p.add_argument("-o", "--out", type=Path, default=None)
    p.set_defaults(func=cmd_encrypt)

    p = sub.add_parser("decrypt", help="remove password protection")
    p.add_argument("file", type=Path)
    p.add_argument("-o", "--out", type=Path, default=None)
    p.set_defaults(func=cmd_decrypt)

    p = sub.add_parser("rotate", help="rotate pages (0/90/180/270)")
    p.add_argument("file", type=Path)
    p.add_argument("--pages", default=None, help="e.g. 2,4 (default: all)")
    p.add_argument("--angle", type=int, default=90, choices=[0, 90, 180, 270])
    p.add_argument("-o", "--out", type=Path, default=None)
    p.set_defaults(func=cmd_rotate)

    args = parser.parse_args(argv)
    require_pypdf()
    if args.file.exists() is False and args.cmd != "merge":
        parser.error(f"file not found: {args.file}")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
