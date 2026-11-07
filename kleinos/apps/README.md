# kleinos/apps — Code Audit Suite

KleinOS apps that use `kleinos/stdlib` as their capability engine. Each app
is standalone: point it at a directory, get a report, optionally export it.
None are wired into the main KleinBOTTLE app — they can be added to KleinOS
surfaces independently.

---

## Apps

### `duplicate_finder` — Code Structure Audit

Three modes, one target directory:

| Mode | Question it answers |
|------|---------------------|
| `duplicates` | What functions are copy-pasted? |
| `dead-code` | What's defined but never called? |
| `complexity` | What's too tangled to safely change? |

```bash
python kleinos/apps/duplicate_finder/app.py <target> [--mode duplicates|dead-code|complexity]
```

### `blocking_scanner` — Safety Audit

Finds calls that can freeze a UI or async thread (subprocess, sleep, requests, socket, etc.).

```bash
python kleinos/apps/blocking_scanner/app.py <target>
```

---

## Shared Pattern

Every app follows the same structure:

```
<app>/
  app.py      CLI entry point — parses args, dispatches, calls renderer
  *.py        One module per concern — build_report() only, no rendering
  render.py   All renderers — returns strings, no I/O
  README.md   Usage, options, module layout, stdlib deps
```

All reports export as **Markdown** (default) or **JSON** (`--export json`).
All support `--out FILE` to write to a file instead of stdout.

---

## Adding a New App

1. Create `kleinos/apps/<name>/` with the structure above
2. Each analysis module imports from `kleinos/stdlib/src/tools/` via `sys.path`
3. `build_report()` returns a plain dict; `render.py` turns it into a string
4. Register the app in `kleinos/stdlib/manifest.json` under `"apps"`
5. Add it here

---

## stdlib Dependency Map

| App | stdlib tools used |
|-----|-------------------|
| `duplicate_finder` (duplicates mode) | `duplicate_code_finder`, `similar_code_finder` |
| `duplicate_finder` (dead-code mode) | `dead_code_finder` |
| `duplicate_finder` (complexity mode) | `python_complexity_scorer` |
| `blocking_scanner` | `scan_blocking_calls` |
