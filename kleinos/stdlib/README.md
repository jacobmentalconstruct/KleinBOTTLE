# kleinos/stdlib — KleinOS Standard Library

The internal capability layer for KleinBOTTLE. Provides analysis, introspection,
and operations tools that **KleinOS apps call into**. The main KleinBOTTLE app
does not depend on this directly — only KleinOS apps do.

---

## Role in the Architecture

```
KleinBOTTLE (main app)
└── kleinos/           ← KleinOS in-game computer
    ├── apps/          ← KleinOS app UI + logic (each may depend on stdlib)
    └── stdlib/        ← YOU ARE HERE: capability engine apps call into
        ├── manifest.json        ← machine-readable capability index
        ├── src/
        │   ├── common.py        ← shared CLI contract + JSON envelope
        │   ├── mcp_server.py    ← MCP stdio server (exposes all tools)
        │   └── tools/           ← individual capability modules
        └── seeds/               ← agent briefing documents
```

Each stdlib tool is a standalone Python module. Tools are **read-only by default**;
only a small set (docker_ops push, k8s apply, runtime_artifact_cleaner with
`confirm: true`) mutate anything, and all require explicit confirmation.

---

## Capability Groups

| Group | What it provides |
|-------|-----------------|
| `ast_analysis` | Duplicate detection, dead code, complexity, import graphs, blocking-call scan, domain boundaries, decomposition planning |
| `introspection` | File tree snapshot, full-text search, project orientation, agent bootstrap packet |
| `environment` | Host/dependency/process/port probing, dev server lifecycle, secret scan, Docker/k8s ops |
| `sqlite` | Schema introspection, schema diffing |
| `scaffold_test` | Test skeleton generation, smoke test runner, whitespace-immune patcher |
| `journal` | SQLite-backed journal: write, query, export, snapshot, action ledger |

See `manifest.json` for the full capability index with tool paths and summaries.

---

## Tool Contract

Every tool follows the same interface:

```python
# Programmatic
from kleinos.stdlib.src.tools import duplicate_code_finder
result = duplicate_code_finder.run({"target_path": "/path/to/project"})

# CLI
python kleinos/stdlib/src/tools/duplicate_code_finder.py run --input-json '{"target_path": "."}'

# Metadata / schema
python kleinos/stdlib/src/tools/duplicate_code_finder.py metadata
```

Result is always a JSON envelope defined in `src/common.py`:
```json
{ "ok": true, "data": { ... } }
{ "ok": false, "error": "...", "detail": "..." }
```

---

## MCP Server

Exposes all tools to Claude Code and other MCP clients over stdio:

```bash
python kleinos/stdlib/src/mcp_server.py
```

---

## Adding a KleinOS App That Uses stdlib

1. Create `kleinos/apps/<your_app>/` with its own `__init__.py`
2. Import the tool you need: `from kleinos.stdlib.src.tools import <tool>`
3. Call `tool.run({...})` — handle the `ok`/`error` envelope
4. Register the app in `kleinos/apps/manifest.json` (once that exists)
5. The app is listed in `kleinos/stdlib/manifest.json` under `"apps"`

The first example of this pattern is `kleinos/apps/duplicate_finder/`.

---

## Running Tests

```bash
python kleinos/stdlib/src/smoke_test.py
python -m pytest kleinos/stdlib/tests/
```
