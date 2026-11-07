# duplicate_finder

KleinOS code audit app. Points at a directory and reports on three aspects of
code structure. Depends on `kleinos/stdlib` only — not wired into the main
KleinBOTTLE app.

---

## Modes

### `duplicates` (default)
Finds exact and structurally-similar duplicate functions across a codebase.
Uses AST fingerprinting — exact matches are identical bodies; structural matches
are the same logic with locally renamed variables. Near-duplicates are detected
via difflib structural similarity scoring.

### `dead-code`
Finds unused functions, classes, and imports. Cross-references definitions
against all usages across the scanned directory. Private names (`_`, `test_`)
and common entry points (`main`, `run`, `app`) are excluded by default.

### `complexity`
Scores every function by a composite of cyclomatic complexity, nesting depth,
line count, and parameter count. Flags functions above the threshold as
decomposition candidates.

---

## Usage

```bash
# Duplicates (default mode)
python kleinos/apps/duplicate_finder/app.py <target>

# Dead code
python kleinos/apps/duplicate_finder/app.py <target> --mode dead-code

# Complexity
python kleinos/apps/duplicate_finder/app.py <target> --mode complexity

# Export to file
python kleinos/apps/duplicate_finder/app.py <target> --mode duplicates --export md --out report.md
python kleinos/apps/duplicate_finder/app.py <target> --mode complexity  --export json --out report.json

# Full option list
python kleinos/apps/duplicate_finder/app.py --help
```

---

## Options

| Flag | Default | Applies to | Description |
|------|---------|------------|-------------|
| `--mode` | `duplicates` | all | `duplicates` \| `dead-code` \| `complexity` |
| `--export` | `md` | all | `md` \| `json` |
| `--out FILE` | stdout | all | Write report to file |
| `--min-lines N` | 5 | duplicates | Min function length to consider |
| `--threshold F` | 0.85 | duplicates | Similarity threshold (0–1) |
| `--top-n N` | 20 | duplicates, complexity | Max results to include |
| `--include-private` | off | dead-code | Include `_` and `test_` names |
| `--complexity-threshold N` | 8 | complexity | Composite score threshold |

---

## Module Layout

```
duplicate_finder/
  app.py          CLI entry point and mode dispatcher
  duplicates.py   Build report dict for duplicates mode
  dead_code.py    Build report dict for dead-code mode
  complexity.py   Build report dict for complexity mode
  render.py       All Markdown and JSON renderers (no I/O)
```

Each module has a single responsibility. `app.py` wires them together.
`render.py` is the only module that knows about output format.

---

## stdlib Dependencies

| Mode | stdlib tool |
|------|-------------|
| duplicates | `duplicate_code_finder`, `similar_code_finder` |
| dead-code | `dead_code_finder` |
| complexity | `python_complexity_scorer` |
