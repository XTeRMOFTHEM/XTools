<div align="center">

# ⚡ XTools

**A toolbox of sharp, single-purpose CLI utilities — each one does its job and does it well.**

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-13%20passing-brightgreen?style=for-the-badge)](#-testing)

*No bloat. No config files. Copy a file, run it, done.*

</div>

---

## 🧰 The Tools

| Tool | What it does | Dependencies |
|------|--------------|--------------|
| **filemux** | Organize messy folders by type / date / extension — dry-run by default, one-command undo | none |
| **dedupe** | Find duplicate files (size → partial hash → SHA-256), report wasted space, move or delete with confirmation | none |
| **imgpress** | Batch image optimizer — resize, convert to WebP/JPEG/PNG, compress with per-file savings report | `pillow` |
| **pdfsmith** | PDF Swiss-army knife — merge, split, extract pages, pull text, rotate, encrypt/decrypt | `pypdf` |
| **dbtool** | SQLite inspector & differ — schema overview, JSON/CSV export, SQL queries, diff two DBs, vacuum | none |
| **netcheck** | Server health checks — TCP port scan, TLS certificate expiry warnings, DNS resolution, ping | none |

---

## 📦 Install

```bash
git clone https://github.com/XTeRMOFTHEM/XTools.git
cd XTools
```

Four of the six tools are **pure standard library** — they run anywhere Python runs.
For the other two (optional):

```bash
pip install -r requirements.txt   # pillow + pypdf
```

## 🚀 Usage

### 🗂️ filemux — clean up that Downloads folder

```bash
python tools/filemux.py ~/Downloads            # preview the plan (dry run)
python tools/filemux.py ~/Downloads --apply    # execute
python tools/filemux.py ~/Downloads --by date  # group into YYYY-MM folders
python tools/filemux.py ~/Downloads --undo     # revert the last run
```

```
  Plan for Downloads  (type)  —  42 file(s)

  📁 Images
     photo.jpg  →  photo.jpg
  📁 Documents
  ...
```

### 👯 dedupe — reclaim wasted disk space

```bash
python tools/dedupe.py ~/Pictures                     # report only
python tools/dedupe.py ~/Pictures --min-size 1MB      # skip tiny files
python tools/dedupe.py ~/Pictures --move-to ~/Dupes   # keep 1 copy, park the rest
python tools/dedupe.py ~/Pictures --delete --yes      # hard delete (careful!)
```

```
#1  3 × 2.0 KB  —  vacation.png
  keep  .../vacation.png
  dupe  .../vacation (1).png
  dupe  .../backup/vacation.png

  1 group(s)  •  3.9 KB recoverable
```

### 🖼️ imgpress — shrink photos for the web

```bash
python tools/imgpress.py ~/Photos --to webp --quality 80
python tools/imgpress.py ~/Photos --max-width 1920
python tools/imgpress.py ~/Photos --out ~/Photos/web --suffix _small
```

```
  ✓ beach.jpg   4.2 MB → 380.5 KB  (-91%)
  ✓ city.jpg    3.8 MB → 295.1 KB  (-92%)

  2 optimized  •  8.0 MB → 675.6 KB  (92% saved)
```

### 📕 pdfsmith — PDF everything

```bash
python tools/pdfsmith.py info book.pdf
python tools/pdfsmith.py merge a.pdf b.pdf -o combined.pdf
python tools/pdfsmith.py split book.pdf --out pages/
python tools/pdfsmith.py extract book.pdf --pages 1-3,7 -o excerpt.pdf
python tools/pdfsmith.py text book.pdf --pages 2-4 > chapter.txt
python tools/pdfsmith.py encrypt secret.pdf --password s3cret
python tools/pdfsmith.py rotate slides.pdf --pages 2,4 --angle 90
```

### 🗄️ dbtool — see inside any SQLite file

```bash
python tools/dbtool.py info app.db
python tools/dbtool.py tables app.db
python tools/dbtool.py dump app.db --tables users --format json -o users.json
python tools/dbtool.py query app.db "SELECT * FROM users LIMIT 5"
python tools/dbtool.py diff old.db new.db
python tools/dbtool.py vacuum app.db
```

```
  demo.db
  size      8.0 KB
  integrity ok
  tables    1
    • users  (3 rows)  id, name, age
```

### 🌐 netcheck — know before your users do

```bash
python tools/netcheck.py ping myserver.example
python tools/netcheck.py port myserver.example --ports 22,80,443
python tools/netcheck.py tls api.example.com           # cert expiry warning
python tools/netcheck.py dns example.com
```

```
  TLS  github.com:443
  protocol   TLSv1.3
  subject    github.com
  issuer     Sectigo Limited
  valid to   Nov 29 23:59:59 2026 GMT  (42 days left)
```

---

## 🧪 Testing

```bash
python -m unittest discover -s tests -v
```

13 unit tests cover the core logic: dry-run safety, undo round-trips, collision
handling, duplicate detection, min-size filtering, and database diffing.

## 🤝 Contributing

Issues and PRs are welcome. Each tool lives in a single file under `tools/` on
purpose — keep them self-contained and dependency-light.

## 📄 License

[MIT](LICENSE) — use them, ship them, break them, enjoy.
