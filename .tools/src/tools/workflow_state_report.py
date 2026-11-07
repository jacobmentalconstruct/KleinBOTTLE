"""
FILE: workflow_state_report.py
ROLE: Current-state report for the operationalization project.
WHAT IT DOES:
  - Reads CONTROL.md files across all coordination directories
  - Reads all STATUS.md work-item files
  - Reads recent journal entries if journal is initialized
  - Returns a single structured report: phase, active item, all item states
HOW TO USE:
  - python src/tools/workflow_state_report.py metadata
  - python src/tools/workflow_state_report.py run --input-json '{"project_root":"C:/path"}'
  - python src/tools/workflow_state_report.py run --input-json '{"project_root":"C:/path","journal_limit":10}'
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import now_stamp, standard_main, tool_error, tool_result


FILE_METADATA = {
    "tool_name": "workflow_state_report",
    "version": "1.0.0",
    "entrypoint": "src/tools/workflow_state_report.py",
    "category": "workflow",
    "summary": "Report current operationalization state: active tranche, all item states, recent journal.",
    "mcp_name": "workflow_state_report",
    "input_schema": {
        "type": "object",
        "properties": {
            "project_root": {"type": "string", "default": "."},
            "journal_limit": {"type": "integer", "default": 5},
        },
        "additionalProperties": False,
    },
}

# Coordination dirs to scan, relative to project_root, in priority order
_COORD_DIRS = [
    "coordination",
    "tools/git-walker/coordination",
]


def _parse_yaml_block(text: str) -> dict[str, str]:
    """Extract first ```yaml block from markdown and parse key: value pairs."""
    match = re.search(r"```ya?ml\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if not match:
        return {}
    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip()
    return result


def _read_control(coord_dir: Path) -> dict[str, Any] | None:
    path = coord_dir / "CONTROL.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    parsed = _parse_yaml_block(text)
    return {"path": str(path), **parsed}


def _read_status_files(coord_dir: Path) -> list[dict[str, Any]]:
    items_dir = coord_dir / "work-items"
    if not items_dir.is_dir():
        return []
    results = []
    for status_file in sorted(items_dir.glob("*/STATUS.md")):
        text = status_file.read_text(encoding="utf-8", errors="replace")
        parsed = _parse_yaml_block(text)
        # Extract item id from directory name
        item_id = status_file.parent.name
        # Extract title from first heading
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else item_id
        results.append({
            "item_id": item_id,
            "title": title,
            "path": str(status_file),
            **parsed,
        })
    return results


def _read_journal(project_root: Path, limit: int) -> list[dict[str, Any]]:
    try:
        from lib.journal_store import query_entries
        result = query_entries(project_root=str(project_root), limit=limit)
        return [
            {
                "entry_uid": e["entry_uid"],
                "created_at": e["created_at"],
                "kind": e["kind"],
                "status": e["status"],
                "title": e["title"],
                "tags": e["tags"],
            }
            for e in result.get("entries", [])
        ]
    except Exception:
        return []


def run(arguments: dict) -> dict:
    project_root = Path(arguments.get("project_root", ".")).resolve()
    if not project_root.is_dir():
        return tool_error(FILE_METADATA["tool_name"], arguments, f"Not a directory: {project_root}")

    journal_limit = max(0, int(arguments.get("journal_limit", 5)))

    controls: list[dict] = []
    all_items: list[dict] = []

    for rel in _COORD_DIRS:
        coord_dir = project_root / rel
        if not coord_dir.is_dir():
            continue
        ctrl = _read_control(coord_dir)
        if ctrl:
            ctrl["coordination_dir"] = rel
            controls.append(ctrl)
        items = _read_status_files(coord_dir)
        for item in items:
            item["coordination_dir"] = rel
        all_items.extend(items)

    # Derive active item and phase from primary control
    active_item = None
    current_phase = None
    for ctrl in controls:
        if ctrl.get("active_work_item"):
            active_item = ctrl["active_work_item"]
        if ctrl.get("phase"):
            current_phase = ctrl["phase"]

    # Bucket items by state
    by_state: dict[str, list] = {}
    for item in all_items:
        state = item.get("state", "unknown")
        by_state.setdefault(state, []).append(item)

    waiting = by_state.get("WAITING_FOR_HUMAN", [])
    in_progress = by_state.get("READY_FOR_BUILD", []) + by_state.get("READY_FOR_REVIEW", []) + by_state.get("DECLARING", [])
    parked = by_state.get("INTEGRATED", []) + by_state.get("PARKED", [])

    journal_entries = _read_journal(project_root, journal_limit)

    # Build summary line
    if not all_items:
        summary = "No work items found. Coordination structure not yet initialized."
    elif waiting:
        item = waiting[0]
        decision = item.get("human_decision_needed", "review required")
        summary = f"WAITING: {item['item_id']} — human decision needed: {decision}"
    elif in_progress:
        item = in_progress[0]
        summary = f"IN PROGRESS: {item['item_id']} (state: {item.get('state', '?')})"
    else:
        summary = f"{len(parked)} item(s) parked. Ready to declare next tranche."

    return tool_result(FILE_METADATA["tool_name"], arguments, {
        "generated_at": now_stamp(),
        "project_root": str(project_root),
        "summary": summary,
        "current_phase": current_phase,
        "active_item": active_item,
        "controls": controls,
        "items": {
            "waiting_for_human": waiting,
            "in_progress": in_progress,
            "parked": parked,
            "all": all_items,
        },
        "journal": journal_entries,
        "coordination_dirs_scanned": [
            rel for rel in _COORD_DIRS
            if (project_root / rel).is_dir()
        ],
    })


if __name__ == "__main__":
    raise SystemExit(standard_main(FILE_METADATA, run))
