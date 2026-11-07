"""
FILE: project_orientation.py
ROLE: Single-document project orientation for fresh agents and humans.
WHAT IT DOES:
  - Scans .tools/src/tools/*.py via AST for FILE_METADATA (tool inventory)
  - Calls local_agent_bootstrap (env + constraints + journal)
  - Calls workflow_state_report (coordination state)
  - Merges into one flat JSON document
HOW TO USE:
  - python src/tools/project_orientation.py run --input-json '{"project_root":"."}'
  - python src/tools/project_orientation.py run --input-json '{"project_root":".","output_file":"_docs/orientation.json"}'
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import now_stamp, standard_main, tool_error, tool_result


FILE_METADATA = {
    "tool_name": "project_orientation",
    "version": "1.0.0",
    "entrypoint": "src/tools/project_orientation.py",
    "category": "workflow",
    "summary": "Single orientation document: env + tool inventory + coordination state + constraints, merged into one JSON.",
    "mcp_name": "project_orientation",
    "input_schema": {
        "type": "object",
        "properties": {
            "project_root": {"type": "string", "default": "."},
            "journal_limit": {"type": "integer", "default": 5},
            "output_file": {"type": "string", "default": ""},
        },
        "additionalProperties": False,
    },
}

_TOOLS_SRC_DIR = Path(__file__).resolve().parent
_TOOLS_ROOT = _TOOLS_SRC_DIR.parent  # .tools/src/


def _run_tool(tool_name: str, input_dict: dict[str, Any]) -> dict[str, Any]:
    """Call a sibling tool via subprocess, return parsed JSON result."""
    tool_path = _TOOLS_SRC_DIR / f"{tool_name}.py"
    if not tool_path.exists():
        return {"error": f"Tool not found: {tool_path}"}
    try:
        result = subprocess.run(
            [sys.executable, str(tool_path), "run", "--input-json", json.dumps(input_dict)],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
        return {"error": result.stderr.strip() or result.stdout.strip() or "empty output"}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except Exception as exc:
        return {"error": str(exc)}


def _extract_file_metadata(py_path: Path) -> dict[str, Any] | None:
    """Extract FILE_METADATA dict from a tool .py via AST — no import, no side effects."""
    try:
        source = py_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "FILE_METADATA":
                    try:
                        return ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        return None
    return None


def _scan_tool_inventory(tools_dir: Path) -> list[dict[str, Any]]:
    """Return sorted list of {tool_name, version, category, summary, entrypoint}."""
    inventory: list[dict[str, Any]] = []
    if not tools_dir.is_dir():
        return inventory
    for py_file in sorted(tools_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        meta = _extract_file_metadata(py_file)
        if meta and "tool_name" in meta:
            inventory.append(
                {
                    "tool_name": meta.get("tool_name", ""),
                    "version": meta.get("version", ""),
                    "category": meta.get("category", ""),
                    "summary": meta.get("summary", ""),
                    "entrypoint": meta.get("entrypoint", py_file.name),
                }
            )
    return inventory


def _safe_result(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract the inner result from a tool_result envelope, or return as-is."""
    if "result" in raw:
        return raw["result"]
    return raw


def run(arguments: dict) -> dict:
    project_root = Path(arguments.get("project_root", ".")).resolve()
    if not project_root.is_dir():
        return tool_error(FILE_METADATA["tool_name"], arguments, f"Not a directory: {project_root}")

    journal_limit = max(1, int(arguments.get("journal_limit", 5)))
    output_file = str(arguments.get("output_file", "")).strip()

    # 1. Tool inventory — AST scan of .tools/src/tools/
    tool_inventory = _scan_tool_inventory(_TOOLS_SRC_DIR)

    # 2. Environment + journal + constraints — local_agent_bootstrap
    bootstrap_raw = _run_tool(
        "local_agent_bootstrap",
        {"project_root": str(project_root), "format": "json", "journal_limit": journal_limit},
    )
    packet = _safe_result(bootstrap_raw).get("packet", _safe_result(bootstrap_raw))

    # 3. Coordination state — workflow_state_report
    state_raw = _run_tool("workflow_state_report", {"project_root": str(project_root)})
    coord_state = _safe_result(state_raw)

    # 4. Merge into single document
    host_result = packet.get("host", {}).get("result", {})
    workspace_result = packet.get("workspace", {}).get("result", {})

    document: dict[str, Any] = {
        "generated_at": now_stamp(),
        "project_root": str(project_root),
        # -- Identity --
        "project_identity": {
            "name": project_root.name,
            "goal": "Operationalize WORKFLOW.md — build a system that runs the 15-step tranche cycle with minimal ritual tax.",
            "workflow_spec": "docs/WORKFLOW.md",
            "phases": {
                "A": "Strategy Gate — abstract intent → tranche spec → HITL approve",
                "B": "Coding Gate — guardrailed execution, one step at a time, state logged",
                "C": "Review Gate — context bundle (tree + diff) → adversarial inference → findings",
                "D": "Park Gate — STATUS.md update, docs, human merge approval",
            },
            "critical_path": "Phase C first — adversarial review loop working end-to-end.",
            "structure_pattern": "Pattern 2: scaffold owns root; app isolated in workflow-ops/",
            "app_dir": str(project_root / "workflow-ops"),
            "scaffold_dirs": ["coordination/", "_docs/", "_projectmapper/", "tools/", ".tools/", ".dev-tools/"],
        },
        # -- Current coordination state --
        "current_state": {
            "summary": coord_state.get("summary", "(workflow_state_report unavailable)"),
            "current_phase": coord_state.get("current_phase"),
            "active_item": coord_state.get("active_item"),
            "controls": coord_state.get("controls", {}),
            "items": coord_state.get("items", {}),
            "coordination_dirs_scanned": coord_state.get("coordination_dirs_scanned", []),
            "error": coord_state.get("error"),
        },
        # -- Tool inventory --
        "tool_inventory": {
            "count": len(tool_inventory),
            "tools_src": str(_TOOLS_SRC_DIR),
            "tools": tool_inventory,
        },
        # -- Environment --
        "environment": {
            "platform": host_result.get("host", {}),
            "shell": host_result.get("shell", {}),
            "commands_available": host_result.get("summary", {}),
            "workspace": {
                "safe_write_boundary": workspace_result.get("safe_write_boundary"),
                "git": workspace_result.get("git", {}),
                "sidecar_present": workspace_result.get("sidecar_present"),
                "runtime_paths": workspace_result.get("runtime_paths", []),
                "footprint": workspace_result.get("footprint", {}),
                "warnings": workspace_result.get("warnings", []),
            },
            "dependencies": packet.get("dependency_check", {}).get("result", {}).get("summary", {}),
        },
        # -- Journal --
        "journal": {
            "db_path": str(project_root / "_docs" / "_journalDB" / "app_journal.sqlite3"),
            "recent_entries": packet.get("journal", {}).get("result", {}).get("entries", []),
        },
        # -- Constraints --
        "constraints": packet.get("constraints", []),
        "operating_envelope": packet.get("operating_envelope", []),
    }

    # 5. Optionally write to file
    written_to: str | None = None
    if output_file:
        out_path = (
            Path(output_file)
            if Path(output_file).is_absolute()
            else project_root / output_file
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(document, indent=2, default=str), encoding="utf-8")
        written_to = str(out_path)

    return tool_result(
        FILE_METADATA["tool_name"],
        arguments,
        {
            "document": document,
            "tool_inventory_count": len(tool_inventory),
            "sections": list(document.keys()),
            "written_to": written_to,
        },
    )


if __name__ == "__main__":
    raise SystemExit(standard_main(FILE_METADATA, run))
