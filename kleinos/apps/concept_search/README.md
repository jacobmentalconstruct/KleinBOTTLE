# concept_search

KleinOS donor-material finder. Given a plain-language description of something
you want to build, scans a directory and surfaces existing Python functions that
may already implement the same idea — or enough of it to use as a starting point.

Depends on `kleinos/stdlib` only. Not wired into the main KleinBOTTLE app.
`sentence-transformers` is an optional dependency: the app prompts to install
it on first semantic use and falls back to keyword mode until it is available.

---

## What it does

Takes a concept like:

> "walk a file tree and collect every Python file, skipping hidden directories"

and ranks every function in the target directory by how well it matches that
description. The result is a list of candidates with relevance scores — evidence
to review, not a definitive answer.

---

## Search modes

### `combined` (default)
Runs both keyword and semantic scoring and combines them (semantic weighted 80%,
keyword 20%). Best signal overall. Requires sentence-transformers for the
semantic half; falls back to keyword-only if unavailable.

### `keyword`
Counts concept keyword hits per function (stop words removed). Always available,
no extra deps. Coarse but instant — useful for large codebases or when
sentence-transformers is not installed.

### `semantic`
Embeds the concept and all functions using a local sentence-transformers model,
ranks by cosine similarity. Fine-grained — can surface functions that use
different vocabulary to do the same thing. Requires sentence-transformers.

---

## sentence-transformers dependency

The semantic path requires `sentence-transformers` (pulls PyTorch, ~1–2 GB
first install). The app handles this:

1. If sentence-transformers **is installed** → semantic mode runs immediately
2. If it **is not installed** → app prompts:
   ```
   sentence-transformers is not installed.
   sentence-transformers requires PyTorch (~1-2 GB on first install).
   Install now? [y/N]
   ```
3. On **yes** → installs live, proceeds with semantic mode in the same session
4. On **no** → falls back to keyword mode (combined) or exits (semantic-only)
5. Pass `--install` to skip the prompt and install non-interactively

**UI integration:** `deps.is_semantic_available()` returns a bool that a KleinOS
UI panel can query at startup to grey the semantic/combined mode buttons until
the dependency is present.

---

## Usage

```bash
# Combined mode (default) — prompts to install sentence-transformers if needed
python kleinos/apps/concept_search/app.py "your concept here" <target>

# Keyword only — no deps needed
python kleinos/apps/concept_search/app.py "your concept here" <target> --mode keyword

# Semantic only
python kleinos/apps/concept_search/app.py "your concept here" <target> --mode semantic

# Non-interactive install + run
python kleinos/apps/concept_search/app.py "your concept here" <target> --install

# Export to file
python kleinos/apps/concept_search/app.py "your concept here" <target> --export md --out report.md
python kleinos/apps/concept_search/app.py "your concept here" <target> --export json --out report.json
```

---

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `combined` | `combined` \| `keyword` \| `semantic` |
| `--top-n N` | 15 | Max candidates to show |
| `--min-lines N` | 3 | Min function length to consider |
| `--model NAME` | `all-MiniLM-L6-v2` | sentence-transformers model name |
| `--install` | off | Install sentence-transformers without prompting |
| `--export` | `md` | `md` \| `json` |
| `--out FILE` | stdout | Write report to file |

---

## Module layout

```
concept_search/
  app.py        CLI entry point, dep gating, mode dispatch
  deps.py       is_semantic_available(), ensure_semantic(), prompt_install()
  searcher.py   build_report(): keyword scoring + semantic scoring, combined rank
  render.py     Markdown and JSON renderers (no I/O)
```

---

## stdlib dependency

| Path used | Purpose |
|-----------|---------|
| `kleinos/stdlib/src/lib/python_code_units.py` | collect_python_units(), public_unit() |
