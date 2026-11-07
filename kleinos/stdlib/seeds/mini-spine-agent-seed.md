# mini-spine-agent-seed.md

Extracted from `runtime/agent.py`. Flask web UI block stripped.
Single-file agent runtime: workspace I/O, Ollama inference, git blob capture,
JSON state transform, ordered workflow execution, HITL proposal/approve/reject,
and history logging. No external deps beyond `flask` (optional, now removed).

---

## Why This Is Interesting

**Phase B executor candidate.** `run_workflow()` already IS a task list runner:
ordered steps, `$step_id` result references, bounded (MAX_STEPS=10), one op at a
time. The HITL loop (`make_proposal` → human approves/rejects → `execute_proposal`)
maps directly to WORKFLOW.md's Coding Gate.

**Swarm-ready by design.** Each agent gets an isolated workspace directory:
`agent.json` (state), `files/` (outputs), `history.jsonl` (event log). A
coordinator can spawn N workspaces and read each one's `history.jsonl` to track
progress — no shared state, no message bus needed.

**Task list = workflow steps.** A task list encoded as a JSON array of
`{"id": "s1", "op": "R|W|T|I", "params": {...}}` objects IS the executable plan.
Feed it to `run_workflow()` after human approval.

---

## Tool Contracts

```python
TOOL_CONTRACTS = {
    "R": {
        "description": "Read a permitted workspace path or anchored Git object.",
        "params": {"path": "str — workspace-relative path or git-ref:filename"},
    },
    "W": {
        "description": "Validated atomic write to a permitted workspace path under files/.",
        "params": {"path": "str — files/-relative filename", "content": "str"},
    },
    "T": {
        "description": "JSON transform on agent.json: set, remove, or append at dot-path key.",
        "params": {"op": "set|remove|append", "key": "str — dot-path", "value": "any — set/append only"},
    },
    "I": {
        "description": "Ollama inference: send prompt to a named local model, return text.",
        "params": {"model": "str — installed model name", "prompt": "str"},
    },
}
```

---

## Module: agent.py (Flask-stripped)

```python
"""Minimal Spine Agent — runtime (Flask UI stripped)."""
import datetime
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

VERSION = "0.1"
SCHEMA_VERSION = 1
MAX_STEPS = 10
OLLAMA_BASE = "http://localhost:11434"

TOOL_CONTRACTS = { ... }  # see above

_INITIAL_AGENT = {
    "version": VERSION,
    "schema_version": SCHEMA_VERSION,
    "mode": "chat",
    "model": None,
    "tools": TOOL_CONTRACTS,
    "permitted_paths": ["files/"],
}


# ---------------------------------------------------------------------------
# Workspace bootstrap
# ---------------------------------------------------------------------------

def bootstrap_workspace(ws_path, project_root=None) -> Path:
    """Create a fresh workspace directory. Raises FileExistsError if already present."""
    ws = Path(ws_path)
    if ws.exists():
        raise FileExistsError(f"Workspace already exists: {ws}")
    ws.mkdir(parents=True)
    (ws / "files").mkdir()
    data = {**_INITIAL_AGENT}
    if project_root is not None:
        resolved = str(Path(project_root).resolve())
        data["project_root"] = resolved
        data["permitted_paths"] = [resolved]
    (ws / "agent.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (ws / "history.jsonl").write_text("", encoding="utf-8")
    return ws


# ---------------------------------------------------------------------------
# Workspace I/O — bounded reads, atomic verified writes
# ---------------------------------------------------------------------------

def _files_root(ws: Path) -> Path: ...
def _checked_target(base: Path, rel_path: str) -> Path: ...  # path traversal guard
def _atomic_write(target: Path, content: bytes) -> None: ...  # write → verify bytes

def read_file(ws: Path, rel_path: str) -> str: ...
def write_file(ws: Path, rel_path: str, content: str) -> None: ...
def read_agent_json(ws: Path) -> dict: ...
def write_agent_json(ws: Path, data: dict) -> None: ...


# ---------------------------------------------------------------------------
# Ollama adapter
# ---------------------------------------------------------------------------

def ollama_list_models(base_url: str = OLLAMA_BASE) -> list: ...
def ollama_infer(prompt: str, model: str, base_url: str = OLLAMA_BASE) -> str: ...


# ---------------------------------------------------------------------------
# Git projection — blob capture, durable anchor, retrieval
# ---------------------------------------------------------------------------

def init_git_store(store_path) -> Path: ...
def capture_blob(store: Path, source: Path) -> str: ...   # returns 40-char SHA
def anchor_blob(store: Path, sha: str) -> None: ...       # prevents GC
def retrieve_blob(store: Path, sha: str) -> bytes: ...
def blobs_equal(store: Path, sha: str, file_path: Path) -> bool: ...


# ---------------------------------------------------------------------------
# JSON transform — set / remove / append at dot-path key
# ---------------------------------------------------------------------------

def transform_agent_json(ws: Path, op: str, key: str, value=None) -> dict: ...


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def build_context(ws: Path) -> str:
    """Compact self-description from agent.json for model context injection."""


# ---------------------------------------------------------------------------
# Interpreter — ordered R/W/T/I execution with result references
# ---------------------------------------------------------------------------

_REQUIRED_PARAMS = {
    "R": ("path",), "W": ("path", "content"), "T": ("op", "key"), "I": ("prompt", "model"),
}

def run_workflow(ws: Path, steps: list, base_url: str = OLLAMA_BASE) -> list:
    """Execute an ordered R/W/T/I workflow. Returns per-step results list.

    Steps is a JSON array:
        [{"id": "s1", "op": "I", "params": {"model": "llama3", "prompt": "..."}},
         {"id": "s2", "op": "W", "params": {"path": "output.md", "content": "$s1"}}]

    $step_id tokens in param values are substituted longest-first (avoids $s1 vs $s10 collisions).
    Raises ValueError on: unknown op, missing id, duplicate id, forward $ref, missing params.
    MAX_STEPS = 10 hard limit.
    """


# ---------------------------------------------------------------------------
# Controller — proposal → authorization → execution (HITL loop)
# ---------------------------------------------------------------------------

def _parse_response(response: str, max_steps: int = MAX_STEPS) -> dict:
    """Parse model output → {"type": "workflow", "steps": [...]} or {"type": "reply", "text": "..."}"""

def make_proposal(ws: Path, user_message: str, base_url: str = OLLAMA_BASE) -> dict:
    """Build context, call model, return proposal dict WITHOUT executing anything.
    Caller reviews proposal["steps"] before calling execute_proposal()."""

def execute_proposal(ws: Path, proposal: dict, base_url: str = OLLAMA_BASE) -> dict:
    """Execute an approved workflow proposal. Returns {"status": "ok", "results": [...]}"""


# ---------------------------------------------------------------------------
# History — append attributable events to history.jsonl
# ---------------------------------------------------------------------------

def append_history(ws: Path, event: str, **data) -> None:
    """Append timestamped event record: {"ts": "...", "event": "...", ...extra}"""

def read_history(ws: Path) -> list:
    """Return all history records from history.jsonl. Returns [] for fresh workspace."""
```

---

## Swarm Pattern

```
coordinator/
├── ws-agent-1/          ← bootstrap_workspace("ws-agent-1")
│   ├── agent.json       ← state: model, mode, permitted_paths
│   ├── files/           ← write target for W ops
│   └── history.jsonl    ← read by coordinator to track progress
├── ws-agent-2/
│   └── ...
└── coordinator.py       ← spawns workspaces, feeds proposals, reads history
```

Each agent is given a task as a workflow proposal:

```python
ws = bootstrap_workspace("ws-agent-1", project_root="/path/to/project")
transform_agent_json(ws, "set", "model", "llama3")

proposal = make_proposal(ws, "Summarize the diff in files/diff.md and write a finding")
# human (or coordinator) inspects proposal["steps"]
result = execute_proposal(ws, proposal)
append_history(ws, "task_complete", result=result)
```

For task lists: encode the plan as a `steps` array, pass directly to `run_workflow()`,
skip the LLM proposal round-trip when the plan is already known.

---

## Git Store for Immutable Snapshots

```python
store = init_git_store("ws-agent-1/.git-store")
sha = capture_blob(store, Path("ws-agent-1/files/output.md"))
anchor_blob(store, sha)   # survives GC
# later: retrieve_blob(store, sha) to get original bytes
```

Useful for Phase B: capture file state before and after each tranche step,
compare with `blobs_equal()` to verify writes.
