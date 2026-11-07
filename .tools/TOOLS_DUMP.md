# .tools — Dev Toolbox Dump

**Generated:** 2026-11-04  
**Total files:** 94 (excluding `.venv`)  
**Total size:** ~676 KB  

---

## Directory Tree

```
.tools/
├── LICENSE.md
├── README.md
├── requirements.txt
├── run.sh
├── setup_env.sh
├── seeds/
│   ├── mini-spine-agent-seed.md         (241 lines)
│   ├── query-seed.md                    (696 lines)
│   └── the-cell-seed.md                 (255 lines)
├── src/
│   ├── common.py                        (134 lines)  ← shared CLI/result envelope
│   ├── mcp_server.py                    (381 lines)  ← MCP stdio entry point
│   ├── smoke_test.py                    (992 lines)
│   ├── lib/
│   │   ├── __init__.py
│   │   ├── builtin_contract.md          (1330 lines)
│   │   ├── contract.py                  (171 lines)
│   │   ├── intake.py                    (219 lines)
│   │   ├── journal_store.py             (777 lines)
│   │   ├── project_setup.py             (177 lines)
│   │   ├── python_code_units.py         (207 lines)  ← AST fingerprinting shared lib
│   │   ├── scaffolds.py                 (139 lines)
│   │   ├── sidecar_release.py           (266 lines)
│   │   ├── snapshots.py                 (132 lines)
│   │   ├── tool_pack.py                 (146 lines)
│   │   └── builtin_templates/           (25 scaffold template files)
│   └── tools/
│       ├── tool-docs/
│       │   └── code_relational_suite.md (68 lines)
│       ├── context_bundle_builder.py    (249 lines)
│       ├── dead_code_finder.py          (295 lines)
│       ├── dependency_env_check.py      (237 lines)
│       ├── dev_server_manager.py        (381 lines)
│       ├── docker_ops.py                (252 lines)
│       ├── domain_boundary_audit.py     (313 lines)
│       ├── duplicate_code_finder.py     (82 lines)
│       ├── file_tree_snapshot.py        (227 lines)
│       ├── host_capability_probe.py     (151 lines)
│       ├── import_graph_mapper.py       (300 lines)
│       ├── journal_acknowledge.py       (61 lines)
│       ├── journal_actions.py           (52 lines)
│       ├── journal_export.py            (60 lines)
│       ├── journal_init.py              (81 lines)
│       ├── journal_manifest.py          (46 lines)
│       ├── journal_pack.py              (78 lines)
│       ├── journal_query.py             (68 lines)
│       ├── journal_scaffold.py          (66 lines)
│       ├── journal_snapshot.py          (77 lines)
│       ├── journal_write.py             (74 lines)
│       ├── k8s_ops.py                   (315 lines)
│       ├── local_agent_bootstrap.py     (256 lines)
│       ├── module_decomp_planner.py     (460 lines)
│       ├── onboarding_site_check.py     (36 lines)
│       ├── process_port_inspector.py    (197 lines)
│       ├── project_command_profile.py   (268 lines)
│       ├── project_orientation.py       (230 lines)
│       ├── project_setup.py             (64 lines)
│       ├── python_complexity_scorer.py  (274 lines)
│       ├── relation_walker.py           (252 lines)
│       ├── repo_search.py               (332 lines)
│       ├── runtime_artifact_cleaner.py  (207 lines)
│       ├── scan_blocking_calls.py       (170 lines)
│       ├── schema_diff_tool.py          (258 lines)
│       ├── secret_surface_audit.py      (189 lines)
│       ├── sidecar_install.py           (46 lines)
│       ├── similar_code_finder.py       (128 lines)
│       ├── smoke_test_runner.py         (236 lines)
│       ├── sqlite_schema_inspector.py   (233 lines)
│       ├── test_scaffold_generator.py   (291 lines)
│       ├── tkinter_widget_tree.py       (318 lines)
│       ├── tokenizing_patcher.py        (459 lines)
│       ├── workflow_state_report.py     (196 lines)
│       ├── workflow_tranche_init.py     (297 lines)
│       └── workspace_boundary_audit.py  (170 lines)
└── tests/
    └── test_code_relation_suite.py      (172 lines)
```

---

## File Inventory

### Root

| File | Lines | Notes |
|------|-------|-------|
| `README.md` | 229 | Project overview and setup instructions |
| `LICENSE.md` | 53 | License |
| `requirements.txt` | 3 | Minimal runtime deps |
| `run.sh` | 4 | Dev server launcher |
| `setup_env.sh` | 23 | venv bootstrap script |

---

### `src/` — Runtime

| File | Lines | Role |
|------|-------|------|
| `common.py` | 134 | Shared CLI contract, JSON result envelope, `collect_py_files()`, `should_skip_dir()` |
| `mcp_server.py` | 381 | MCP stdio server — exposes all tools to Claude Code and other MCP clients |
| `smoke_test.py` | 992 | Portable self-test suite for the full journal/DB stack |

---

### `src/lib/` — Shared Libraries

| File | Lines | Role |
|------|-------|------|
| `python_code_units.py` | 207 | AST fingerprinting: exact + structural fingerprints via `_Bindings`, `_RenameLocals`; shared by duplicate/similar finders |
| `journal_store.py` | 777 | SQLite store: content-addressed blobs, journal entries, action ledger, scaffold templates, project registry |
| `contract.py` | 171 | Builder constraint contract authority — seeds, serves, and tracks acknowledgment |
| `intake.py` | 219 | Project DB ingestion — imports journal entries with namespacing, detects tool diffs |
| `scaffolds.py` | 139 | Scaffold template management — seeds builtin templates into DB, unpacks to disk |
| `snapshots.py` | 132 | Merkle snapshot management — point-in-time DB fingerprints, integrity verification |
| `tool_pack.py` | 146 | Tool packing/unpacking — stores tool source as blobs in DB, extracts on demand |
| `sidecar_release.py` | 266 | Sidecar release tooling |
| `project_setup.py` | 177 | Project setup helpers |
| `builtin_contract.md` | 1330 | Full builder constraint contract document |
| `builtin_templates/` | 25 files | Scaffold templates for standard project layout |

---

### `src/tools/` — MCP-Exposed Toolbox

#### AST / Code Analysis

| Tool | Lines | What it does |
|------|-------|-------------|
| `python_complexity_scorer.py` | 274 | Cyclomatic complexity + nesting + line count + param count composite score per function. Flags decomposition targets. |
| `dead_code_finder.py` | 295 | Finds unused functions, classes, and imports via cross-file reference analysis. Respects `__all__` and per-file scoping. |
| `duplicate_code_finder.py` | 82 | Exact and structural (locally-renamed) duplicate detection via AST fingerprints. |
| `similar_code_finder.py` | 128 | Structural similarity ranking via difflib or optional sentence-transformers embeddings. |
| `import_graph_mapper.py` | 300 | Full import dependency graph: internal/external classification, circular chain detection, fan-in/fan-out metrics. |
| `scan_blocking_calls.py` | 170 | Finds blocking calls that can freeze a UI thread (subprocess, time.sleep, requests.*, socket.*, httpx.*, input, etc.). |
| `domain_boundary_audit.py` | 313 | Counts distinct domain access per function/class/file; flags contract violations (components ≤1 domain, managers ≤3, etc.). |
| `module_decomp_planner.py` | 460 | Plans safe decomposition of large Python modules by grouping definitions, detecting shared closures, ranking by coupling. |
| `tkinter_widget_tree.py` | 318 | Maps Tkinter widget hierarchy from source: parent-child nesting, geometry managers, variable bindings, event bindings. |
| `relation_walker.py` | 252 | Navigate filesystem, Python code units, or caller-supplied hierarchies. |

#### Introspection / Orientation

| Tool | Lines | What it does |
|------|-------|-------------|
| `file_tree_snapshot.py` | 227 | Snapshot file tree with sizes, line counts, timestamps, optional docstrings. |
| `repo_search.py` | 332 | Full-text search via ripgrep with safe Python-native fallback. |
| `project_orientation.py` | 230 | Single-document agent orientation: tool inventory + env + constraints + journal state. |
| `local_agent_bootstrap.py` | 256 | Launch packet for local/podded agents: host + workspace + commands + deps + journal + constraints. |
| `workspace_boundary_audit.py` | 170 | Resolves project/sidecar/git roots; reports key operational surfaces. Read-only. |
| `context_bundle_builder.py` | 249 | Assembles a single-file adversarial review bundle: tree + filedump + git diff. |
| `workflow_state_report.py` | 196 | Reads CONTROL.md + STATUS.md + recent journal → structured current-state report. |

#### Environment / DevOps

| Tool | Lines | What it does |
|------|-------|-------------|
| `dependency_env_check.py` | 237 | Checks venv, lockfiles, requirements, package manifests, tool availability. Read-only. |
| `host_capability_probe.py` | 151 | Reports OS, Python, shell, and dev command availability. Read-only. |
| `process_port_inspector.py` | 197 | Reports running processes and listening ports. Read-only. |
| `project_command_profile.py` | 268 | Discovers declared setup/test/run/build/dev commands from project files. Read-only. |
| `dev_server_manager.py` | 381 | Guarded dev-server lifecycle: start/stop/status/logs for discovered commands only. |
| `runtime_artifact_cleaner.py` | 207 | Dry-run-first cleanup of generated artifacts (caches, logs, exports). Confirm required for deletion. |
| `secret_surface_audit.py` | 189 | Scans for committed secrets and risky env exposure. Redacts discovered values. Read-only. |
| `docker_ops.py` | 252 | Guarded Docker: build, smoke-run, logs. Push gated behind explicit confirmation. |
| `k8s_ops.py` | 315 | Guarded kubectl: dry-run/apply/status/logs. Mutation gated behind confirmation. |

#### SQLite

| Tool | Lines | What it does |
|------|-------|-------------|
| `sqlite_schema_inspector.py` | 233 | Schema introspection: tables, columns, types, PKs, indexes, FKs, row counts, sample rows. |
| `schema_diff_tool.py` | 258 | Diffs two SQLite schemas: added/dropped tables+columns, index/FK changes, row count deltas. |

#### Scaffolding / Testing

| Tool | Lines | What it does |
|------|-------|-------------|
| `test_scaffold_generator.py` | 291 | Generates test file skeletons from Python source (AST-extracted public functions/classes). |
| `smoke_test_runner.py` | 236 | Meta-runner: discovers and runs all `smoke_test.py` files across the toolbox. |
| `tokenizing_patcher.py` | 459 | Whitespace-immune hunk patcher using tokenization; supports single-file, multi-target, and manifest modes. |

#### Journal Tools (DB-backed, requires `journal_init` first)

| Tool | Lines | What it does |
|------|-------|-------------|
| `journal_init.py` | 81 | Bootstrap: creates SQLite DB, project folders, seeds contract, optionally scaffolds layout. |
| `journal_write.py` | 74 | Create/update/append journal entries with CAS body storage. |
| `journal_query.py` | 68 | Search and filter journal entries or fetch by UID. |
| `journal_export.py` | 60 | Export filtered entries to Markdown or JSON files. |
| `journal_actions.py` | 52 | Query the shared human/AI action ledger. |
| `journal_manifest.py` | 46 | Returns package manifest, DB manifest, schema summary, migration history. |
| `journal_scaffold.py` | 66 | Unpacks standard project layout templates from DB to disk. |
| `journal_pack.py` | 78 | Pack/unpack tool source code into/from the DB. |
| `journal_snapshot.py` | 77 | Create, list, inspect, and verify merkle snapshots. |
| `journal_acknowledge.py` | 61 | Record contract acknowledgment by agent or human. |

---

### `seeds/` — Agent Seed Documents

| File | Lines | Purpose |
|------|-------|---------|
| `mini-spine-agent-seed.md` | 241 | Compact spine-writing agent briefing |
| `query-seed.md` | 696 | Full journal query agent seed |
| `the-cell-seed.md` | 255 | "The Cell" agent architecture seed |

---

### `tests/`

| File | Lines | Purpose |
|------|-------|---------|
| `test_code_relation_suite.py` | 172 | Offline self-tests for the code/relation suite tools — no model, no network, no prod files touched |

---

## Notes

- All tools share a uniform CLI contract via `src/common.py`: `metadata` subcommand returns JSON schema, `run --input-json` / `--input-file` runs the tool.
- All analysis tools are **read-only** unless explicitly noted (docker_ops push, k8s apply, runtime_artifact_cleaner with `confirm: true`).
- The MCP server (`src/mcp_server.py`) exposes every tool listed above to MCP-capable clients (Claude Code, etc.) over stdio.
- Shared AST library: `src/lib/python_code_units.py` — used by `duplicate_code_finder`, `similar_code_finder`, and `relation_walker`.
- Journal tools require `journal_init` to run first; AST/analysis tools are standalone with no DB dependency.
