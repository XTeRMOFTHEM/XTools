#!/usr/bin/env python3
"""dbtool — Zero-dependency SQLite inspector, exporter and differ.

Everything you want to know about a .sqlite/.db file, exported as JSON/CSV,
and a schema+rows diff between two databases. Uses only the standard library.

Usage:
    python dbtool.py info app.db
    python dbtool.py tables app.db
    python dbtool.py dump app.db --tables users,posts --format json -o out.json
    python dbtool.py diff old.db new.db
    python dbtool.py query app.db "SELECT * FROM users LIMIT 5"
    python dbtool.py vacuum app.db
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

if os.name == "nt":
    os.system("")

COLOR = {"green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m",
         "cyan": "\033[96m", "dim": "\033[2m", "bold": "\033[1m", "end": "\033[0m"}


def c(text: str, *styles: str) -> str:
    if sys.stdout.isatty() and os.environ.get("NO_COLOR") is None:
        return "".join(COLOR[s] for s in styles) + text + COLOR["end"]
    return text


def connect(path: Path, readonly: bool = True) -> sqlite3.Connection:
    if readonly:
        if not path.exists():
            raise SystemExit(c(f"database not found: {path}", "red"))
        con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    else:
        con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    return con


def table_names(con: sqlite3.Connection) -> list[str]:
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    return [r["name"] for r in rows]


def row_count(con: sqlite3.Connection, table: str) -> int:
    return con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def columns_of(con: sqlite3.Connection, table: str) -> list[tuple[str, str]]:
    return [(r["name"], r["type"]) for r in con.execute(f'PRAGMA table_info("{table}")')]


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def cmd_info(args) -> int:
    path = args.db.expanduser().resolve()
    with closing(connect(path)) as con:
        size = path.stat().st_size
        page_size = con.execute("PRAGMA page_size").fetchone()[0]
        page_count = con.execute("PRAGMA page_count").fetchone()[0]
        print(c(f"\n  {path.name}", "bold", "cyan"))
        print(f"  size      {human(size)}")
        print(f"  pages     {page_count} × {page_size} B")
        print(f"  integrity {con.execute('PRAGMA integrity_check').fetchone()[0]}")
        tables = table_names(con)
        print(f"  tables    {len(tables)}")
        for t in tables:
            cols = ", ".join(name for name, _ in columns_of(con, t))
            print(c(f"    • {t}", "bold") + c(f"  ({row_count(con, t)} rows)  {cols}", "dim"))
    print()
    return 0


def cmd_tables(args) -> int:
    with closing(connect(args.db.expanduser().resolve())) as con:
        for t in table_names(con):
            print(t)
    return 0


def cmd_dump(args) -> int:
    with closing(connect(args.db.expanduser().resolve())) as con:
        tables = args.tables.split(",") if args.tables else table_names(con)
        tables = [t.strip() for t in tables if t.strip()]
        data = {t: [dict(r) for r in con.execute(f'SELECT * FROM "{t}"')] for t in tables}

    if args.format == "json":
        text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        dest = args.out or Path("dump.json")
        dest.write_text(text, encoding="utf-8")
    else:
        dest = args.out or Path("dump.csv")
        with dest.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            for t, rows in data.items():
                writer.writerow([f"# table: {t}"])
                if rows:
                    writer.writerow(rows[0].keys())
                    writer.writerows(rows)
    total = sum(len(rows) for rows in data.values())
    print(c(f"✓  {total} row(s) from {len(tables)} table(s) → {dest}", "green"))
    return 0


def cmd_diff(args) -> int:
    a, b = args.db1.expanduser().resolve(), args.db2.expanduser().resolve()
    with closing(connect(a)) as con_a, closing(connect(b)) as con_b:
        tables_a, tables_b = set(table_names(con_a)), set(table_names(con_b))
        print(c(f"\n  diff  {a.name}  →  {b.name}\n", "bold", "cyan"))

        changes = 0
        for t in sorted(tables_a - tables_b):
            print(c(f"  − table removed:  {t}", "red")); changes += 1
        for t in sorted(tables_b - tables_a):
            print(c(f"  + table added:    {t}", "green")); changes += 1
        for t in sorted(tables_a & tables_b):
            cols_a = dict(columns_of(con_a, t))
            cols_b = dict(columns_of(con_b, t))
            for col in sorted(set(cols_a) - set(cols_b)):
                print(c(f"  − column:  {t}.{col}", "red")); changes += 1
            for col in sorted(set(cols_b) - set(cols_a)):
                print(c(f"  + column:  {t}.{col} {cols_b[col]}", "green")); changes += 1
            rows_a, rows_b = row_count(con_a, t), row_count(con_b, t)
            if rows_a != rows_b:
                delta = rows_b - rows_a
                style = "green" if delta > 0 else "yellow"
                print(f"  ~ rows:    {t}  {rows_a} → {rows_b}  ({delta:+d})"
                      .replace(f"({delta:+d})", c(f"({delta:+d})", style)))
                changes += 1
    if not changes:
        print(c("  Databases are identical. ✨", "green"))
    else:
        print(c(f"\n  {changes} change(s)", "bold"))
    print()
    return 0


def cmd_query(args) -> int:
    with closing(connect(args.db.expanduser().resolve())) as con:
        try:
            cur = con.execute(args.sql)
        except sqlite3.Error as exc:
            raise SystemExit(c(f"SQL error: {exc}", "red"))
        rows = cur.fetchmany(args.limit)
    if not rows:
        print(c("(no rows)", "dim"))
        return 0
    widths = [len(h) for h in rows[0].keys()]
    table_rows = [[str(v) for v in r] for r in rows]
    for row in table_rows:
        widths = [max(w, len(v)) for w, v in zip(widths, row)]
    header = " | ".join(h.ljust(w) for h, w in zip(rows[0].keys(), widths))
    print(c(header, "bold"))
    print(c("-" * len(header), "dim"))
    for row in table_rows:
        print(" | ".join(v.ljust(w) for v, w in zip(row, widths)))
    print(c(f"\n({len(rows)} row(s))", "dim"))
    return 0


def cmd_vacuum(args) -> int:
    path = args.db.expanduser().resolve()
    before = path.stat().st_size
    con = connect(path, readonly=False)
    con.execute("VACUUM")
    con.close()
    after = path.stat().st_size
    saved = before - after
    if saved > 0:
        print(c(f"✓  {human(before)} → {human(after)}  ({human(saved)} reclaimed)", "green"))
    else:
        print(c(f"✓  already compact ({human(after)})", "green"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dbtool", description="SQLite inspector / exporter / differ — stdlib only.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("info", help="tables, row counts, size, integrity")
    p.add_argument("db", type=Path)
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("tables", help="list table names")
    p.add_argument("db", type=Path)
    p.set_defaults(func=cmd_tables)

    p = sub.add_parser("dump", help="export tables to JSON or CSV")
    p.add_argument("db", type=Path)
    p.add_argument("--tables", default=None, help="comma-separated table names (default: all)")
    p.add_argument("--format", choices=["json", "csv"], default="json")
    p.add_argument("-o", "--out", type=Path, default=None)
    p.set_defaults(func=cmd_dump)

    p = sub.add_parser("diff", help="compare schema and row counts of two databases")
    p.add_argument("db1", type=Path)
    p.add_argument("db2", type=Path)
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("query", help="run a read-only SQL query")
    p.add_argument("db", type=Path)
    p.add_argument("sql")
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("vacuum", help="compact the database file")
    p.add_argument("db", type=Path)
    p.set_defaults(func=cmd_vacuum)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
