"""
FILE: workflow_tranche_init.py
ROLE: Tranche scaffolding tool for the operationalization project.
WHAT IT DOES:
  - Creates coordination/work-items/{item_id}/ directory
  - Writes STATUS.md (DECLARING state, YAML header)
  - Writes 01-planner-to-builder.md from provided declaration fields
  - Updates coordination/CONTROL.md to reflect new active item
  - Writes a journal entry recording the tranche declaration
  - Optionally initializes coordination/ and _docs/ if not present
HOW TO USE:
  - python src/tools/workflow_tranche_init.py metadata
  - python src/tools/workflow_tranche_init.py run --input-json '{
      "project_root": "C:/path",
      "item_id": "WFLOW-001-phase-c-bundle",
      "phase": "C",
      "goal": "Wire Phase C end-to-end manually",
      "scope": ["Run context_bundle_builder", "Feed bundle to adversarial reviewer", "Record findings"],
      "non_goals": ["Automate the reviewer invocation", "Phase B execution"],
      "stop_conditions": ["Bundle file written and non-empty", "Findings doc written", "User notified"],
      "base_commit": ""
    }'
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import ensure_dir, now_stamp, standard_main, tool_error, tool_result


FILE_METADATA = {
    "tool_name": "workflow_tranche_init",
    "version": "1.0.0",
    "entrypoint": "src/tools/workflow_tranche_init.py",
    "category": "workflow",
    "summary": "Scaffold a new operationalization tranche: work-items dir, STATUS.md, planner file, CONTROL.md update.",
    "mcp_name": "workflow_tranche_init",
    "input_schema": {
        "type": "object",
        "required": ["item_id", "goal"],
        "properties": {
            "project_root": {"type": "string", "default": "."},
            "item_id": {"type": "string"},
            "phase": {"type": "string", "enum": ["A", "B", "C", "D"], "default": "C"},
            "goal": {"type": "string"},
            "scope": {"type": "array", "items": {"type": "string"}, "default": []},
            "non_goals": {"type": "array", "items": {"type": "string"}, "default": []},
            "stop_conditions": {"type": "array", "items": {"type": "string"}, "default": []},
            "base_commit": {"type": "string", "default": ""},
            "context_bundle_path": {"type": "string", "default": ""},
            "mode": {"type": "string", "enum": ["HITL", "AUTO_LOW_RISK"], "default": "HITL"},
        },
        "additionalProperties": False,
    },
}

_STATUS_TEMPLATE = """\
# {item_id} — {goal_short}

```yaml
state: DECLARING
phase: {phase}
effective_mode: {mode}
base_commit: {base_commit}
context_bundle_path: {context_bundle_path}
next_owner: planner
human_decision_needed: approve_tranche_declaration
```

Declaration is in [`01-planner-to-builder.md`](01-planner-to-builder.md).
Awaiting human approval before build begins.
"""

_PLANNER_TEMPLATE = """\
# {item_id} — Planner-to-Builder: {goal_short}

```yaml
work_item: {item_id}
from: planner
to: builder
state: DECLARING
phase: {phase}
mode: {mode}
base_commit: {base_commit}
next_permitted_transition: builder_to_reviewer
```

## Goal

{goal}

## Scope

{scope_list}

## Non-Goals

{non_goals_list}

## Stop Conditions

{stop_conditions_list}

## Required Verification Evidence

- [ ] Each stop condition above checked by a command or observable artifact.
- [ ] No files outside the scope paths were modified.
- [ ] No background process needed by this tranche is still running.

## Known Risks

_None declared at this time._

## Stop Boundary

Stop when all stop conditions are met and verification evidence is recorded.
Hand off only the declared scope. Do not begin the next phase or tranche.
"""

_CONTROL_TEMPLATE = """\
# Coordination control

The human owner may update this file through an explicit instruction.
All roles must read it before acting.

```yaml
default_mode: HITL
active_work_item: {item_id}
phase: {phase}
allowed_next_transition: human_decision
```

## Mode meaning

- `HITL`: a passing review waits for a human owner decision.
- `AUTO_LOW_RISK`: a passing review may return to the Planner for acceptance
  only within the unchanged reviewed packet.
"""


def _bullet_list(items: list[str], prefix: str = "- ") -> str:
    if not items:
        return f"{prefix}_(none declared)_"
    return "\n".join(f"{prefix}{item}" for item in items)


def _checklist(items: list[str]) -> str:
    if not items:
        return "- [ ] _(none declared)_"
    return "\n".join(f"- [ ] {item}" for item in items)


def _goal_short(goal: str) -> str:
    first_sentence = re.split(r"[.!?]", goal)[0].strip()
    return first_sentence[:72] if len(first_sentence) > 72 else first_sentence


def _read_control_active_item(control_path: Path) -> str:
    if not control_path.exists():
        return ""
    text = control_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"active_work_item:\s*(.+)", text)
    return match.group(1).strip() if match else ""


def _write_journal_entry(project_root: Path, item_id: str, phase: str, goal: str) -> dict[str, Any]:
    try:
        from lib.journal_store import write_entry
        entry = write_entry(
            project_root=str(project_root),
            title=f"Tranche declared: {item_id}",
            body=f"Phase {phase} tranche declared.\n\nGoal: {goal}",
            kind="tranche_declaration",
            source="workflow_tranche_init",
            tags=["tranche", f"phase-{phase.lower()}", item_id],
            status="open",
            related_path=f"coordination/work-items/{item_id}/",
        )
        return {"entry_uid": entry.get("entry_uid", ""), "status": "written"}
    except Exception as exc:
        return {"status": "skipped", "reason": str(exc)}


def run(arguments: dict) -> dict:
    project_root = Path(arguments.get("project_root", ".")).resolve()
    if not project_root.is_dir():
        return tool_error(FILE_METADATA["tool_name"], arguments, f"Not a directory: {project_root}")

    item_id = str(arguments.get("item_id", "")).strip()
    if not item_id:
        return tool_error(FILE_METADATA["tool_name"], arguments, "item_id is required.")

    goal = str(arguments.get("goal", "")).strip()
    if not goal:
        return tool_error(FILE_METADATA["tool_name"], arguments, "goal is required.")

    phase = str(arguments.get("phase", "C")).upper()
    mode = str(arguments.get("mode", "HITL"))
    base_commit = str(arguments.get("base_commit", "")).strip() or "(pending)"
    context_bundle_path = str(arguments.get("context_bundle_path", "")).strip()
    scope = [str(s) for s in arguments.get("scope", [])]
    non_goals = [str(s) for s in arguments.get("non_goals", [])]
    stop_conditions = [str(s) for s in arguments.get("stop_conditions", [])]
    goal_short = _goal_short(goal)

    # Paths
    coord_dir = project_root / "coordination"
    items_dir = coord_dir / "work-items"
    item_dir = items_dir / item_id
    control_path = coord_dir / "CONTROL.md"

    created: list[str] = []
    warnings: list[str] = []

    # Guard: item must not already exist
    if item_dir.exists():
        return tool_error(FILE_METADATA["tool_name"], arguments, f"Work item already exists: {item_dir}")

    # Check for currently active item
    current_active = _read_control_active_item(control_path)
    if current_active and current_active != item_id:
        warnings.append(
            f"CONTROL.md shows active item '{current_active}'. "
            "Ensure it is parked or handed off before declaring a new tranche."
        )

    # Create directory structure
    ensure_dir(item_dir)
    created.append(str(item_dir))

    # Write STATUS.md
    status_path = item_dir / "STATUS.md"
    status_path.write_text(
        _STATUS_TEMPLATE.format(
            item_id=item_id,
            goal_short=goal_short,
            phase=phase,
            mode=mode,
            base_commit=base_commit,
            context_bundle_path=context_bundle_path or "(set after context_bundle_builder run)",
        ),
        encoding="utf-8",
    )
    created.append(str(status_path))

    # Write 01-planner-to-builder.md
    planner_path = item_dir / "01-planner-to-builder.md"
    planner_path.write_text(
        _PLANNER_TEMPLATE.format(
            item_id=item_id,
            goal_short=goal_short,
            goal=goal,
            phase=phase,
            mode=mode,
            base_commit=base_commit,
            scope_list=_bullet_list(scope),
            non_goals_list=_bullet_list(non_goals),
            stop_conditions_list=_checklist(stop_conditions),
        ),
        encoding="utf-8",
    )
    created.append(str(planner_path))

    # Write or update CONTROL.md
    control_path.write_text(
        _CONTROL_TEMPLATE.format(item_id=item_id, phase=phase),
        encoding="utf-8",
    )
    created.append(str(control_path))

    # Write journal entry
    journal_result = _write_journal_entry(project_root, item_id, phase, goal)

    return tool_result(FILE_METADATA["tool_name"], arguments, {
        "item_id": item_id,
        "phase": phase,
        "item_dir": str(item_dir),
        "files_created": created,
        "warnings": warnings,
        "journal": journal_result,
        "next_step": (
            f"Review {planner_path.name}, then approve the tranche declaration. "
            f"Update STATUS.md state from DECLARING to READY_FOR_BUILD after approval."
        ),
    })


if __name__ == "__main__":
    raise SystemExit(standard_main(FILE_METADATA, run))
