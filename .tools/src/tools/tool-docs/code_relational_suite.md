# `.tools` — Code & Relation Suite (minimal overlay)

Designed against `_HuduORACLE` `main` commit `0d4654506c54f98d7fc9b3e473eae187b63e9f71` (26 Oct 2026).

**Scope:** one shared stdlib extractor, three read-only tools, one additive MCP registration patch, one self-test module. No GUI, Git, SQLite, vector database, caching service, network dependency, or automatic code modification.

## Included files

| Target | Responsibility |
|---|---|
| `.tools/src/lib/python_code_units.py` | Find Python functions/methods; produce source IDs, locations, exact/structural fingerprints and compatible virtual hierarchy nodes. |
| `.tools/src/tools/duplicate_code_finder.py` | Group matching AST fingerprints as exact or local-binding-renamed structural duplicate candidates. |
| `.tools/src/tools/similar_code_finder.py` | Rank non-identical functions via stdlib `difflib`, with optional already-local `sentence-transformers` model. |
| `.tools/src/tools/relation_walker.py` | Navigate arbitrary nodes, existing `file_tree_snapshot` filesystem nodes, **or** the new `python_root` function hierarchy. |
| `.tools/tests/test_code_relation_suite.py` | Portable offline test fixtures. |
| `mcp_registration.patch` | **Optional** additive import/registry edits for existing `.tools/src/mcp_server.py`. |
| `component_blueprint.json` | Natural-language component contracts and stop conditions. |

## Install into a checkout

Extract the ZIP **at the root of** `_HuduORACLE`; paths are already relative to repo root. This creates new files under `.tools` (the existing `common.py`, `file_tree_snapshot.py`, and `mcp_server.py` are not bundled or overwritten).

From the repository root:

```bash
python .tools/tests/test_code_relation_suite.py

git apply --check mcp_registration.patch
git apply mcp_registration.patch

python .tools/src/smoke_test.py
```

The `git apply` step is required only if you want all three tools listed by the MCP server. Each tool also runs directly from CLI without that patch.

## CLI examples

```bash
python .tools/src/tools/duplicate_code_finder.py run --input-json '{"target":"src","min_lines":5}'
python .tools/src/tools/similar_code_finder.py run --input-json '{"target":"src","method":"difflib","threshold":0.80,"top_n":30}'
python .tools/src/tools/relation_walker.py run --input-json '{"action":"inspect","project_root":".","node":"src"}'
python .tools/src/tools/relation_walker.py run --input-json '{"action":"relate","nodes":[{"id":"root","parent":null},{"id":"a","parent":"root"},{"id":"b","parent":"root"}],"a":"a","b":"b"}'
```

For Python function hierarchy, use `relation_walker` with `python_root` instead of `project_root`. Function IDs use `relative/file.py::qualified_name@L<line>`. Fetch exact IDs from `duplicate_code_finder` output, or from `collect_python_units()` if calling the library directly. Its `python_root` mode includes directory, file and lexical scope nodes; the filesystem mode includes files/directories only.

## Optional embedding mode

```bash
python .tools/src/tools/similar_code_finder.py run --input-json '{"target":"src","method":"embedding","threshold":0.75,"top_n":25}'
```

Uses `sentence-transformers` and the **already locally cached** `sentence-transformers/all-MiniLM-L6-v2` model. Missing packages/models produce a plain JSON error. The tool does not download models or add ML dependencies to `.tools` requirements. If the host's `sentence-transformers` version lacks `local_files_only`, upgrade that optional dependency; the default difflib mode remains dependency-free.

No guarantee is made that embedding similarity implies equivalent behavior. It is a candidate generator only.

## Explicit boundaries

- Exact hashes remove formatting/comments and a function's leading docstring; they do **not** normalize its variables.
- Structural hashes normalize local parameter/assignment names in the **current function scope**, retaining operation names, calls, attributes and constant values. This is a heuristic and is not a proof of semantic equivalence.
- Names captured dynamically (`globals`, `locals`, reflection), closure binding subtleties and annotations are **not** proved equivalent by the structural fingerprint; candidate review remains the agent's responsibility.
- `similar_code_finder` compares up to `max_units` code units per run (default 250) to keep pairwise comparison tractable. Narrow `target` for large projects.
- All outputs use existing `FILE_METADATA`, `run(arguments)`, `standard_main`, `tool_result` / `tool_error` semantics; nothing adds an orchestration framework.
- The toolbox's current directory skip list is reused. This is **not** a `.gitignore` interpreter.

## Verification status

Seven offline fixture tests pass in the generated overlay (including the mocked existing filesystem snapshot adapter). All three tools passed standalone CLI calls with a toolbox-compatible test shim. A patch-application check passed on a matching MCP registry fixture. **Not tested:** full live `_HuduORACLE` installation, its full smoke suite, local embedding inference with a cached model, or real repository MCP startup. No GitHub repository changes have been pushed.
