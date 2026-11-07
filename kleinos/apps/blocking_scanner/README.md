# blocking_scanner

KleinOS safety audit app. Scans a directory for blocking calls that can freeze
a UI thread or async event loop. Depends on `kleinos/stdlib` only — not wired
into the main KleinBOTTLE app.

---

## What it finds

Calls known to block the calling thread:

- `subprocess.*` — process spawning
- `time.sleep` — explicit sleeps
- `requests.*`, `httpx.*`, `urllib.*` — synchronous HTTP
- `socket.*` — raw socket I/O
- `input()` — stdin reads
- Any additional patterns you pass via `--extra`

Each hit is a manual review item. Some are intentional (CLI tools, background
worker threads, startup code) — the report flags them for inspection, not
automatic removal.

---

## Usage

```bash
# Scan a directory
python kleinos/apps/blocking_scanner/app.py <target>

# Add custom patterns
python kleinos/apps/blocking_scanner/app.py <target> --extra mylib.fetch db.query_sync

# Export to file
python kleinos/apps/blocking_scanner/app.py <target> --export md  --out report.md
python kleinos/apps/blocking_scanner/app.py <target> --export json --out report.json

# Full option list
python kleinos/apps/blocking_scanner/app.py --help
```

---

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--extra PATTERN…` | — | Additional dotted call patterns to flag |
| `--export` | `md` | `md` \| `json` |
| `--out FILE` | stdout | Write report to file |

---

## Module Layout

```
blocking_scanner/
  app.py      CLI entry point
  scanner.py  Build report dict (wraps stdlib scan_blocking_calls)
  render.py   Markdown and JSON renderers (no I/O)
```

---

## stdlib Dependency

| Tool | stdlib path |
|------|-------------|
| `scan_blocking_calls` | `kleinos/stdlib/src/tools/scan_blocking_calls.py` |
