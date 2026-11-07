"""Workspace definitions, path validation, and event-log persistence."""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_MANAGED_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "workspaces"
_STORE_FILE   = _MANAGED_ROOT / "workspaces.json"
_EVENT_LOG    = _MANAGED_ROOT / "events.jsonl"
_NAME_RE      = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$')


@dataclass
class WorkspaceDef:
    workspace_id: str
    name: str
    root: str           # absolute path string
    sidecar_rev: Optional[str] = None
    installed: bool = False


class WorkspaceStore:
    def __init__(self) -> None:
        _MANAGED_ROOT.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> list[WorkspaceDef]:
        try:
            data = json.loads(_STORE_FILE.read_text(encoding="utf-8"))
            return [WorkspaceDef(**d) for d in data]
        except Exception:
            return []

    def save_all(self, workspaces: list[WorkspaceDef]) -> None:
        _MANAGED_ROOT.mkdir(parents=True, exist_ok=True)
        _STORE_FILE.write_text(
            json.dumps([asdict(w) for w in workspaces], indent=2),
            encoding="utf-8",
        )

    def add(self, ws: WorkspaceDef) -> None:
        all_ws = self.load_all()
        all_ws.append(ws)
        self.save_all(all_ws)

    def update(self, ws: WorkspaceDef) -> None:
        all_ws = self.load_all()
        for i, w in enumerate(all_ws):
            if w.workspace_id == ws.workspace_id:
                all_ws[i] = ws
                break
        self.save_all(all_ws)


def log_event(event_type: str, **fields) -> None:
    """Append one event record to the append-only JSONL event log."""
    _MANAGED_ROOT.mkdir(parents=True, exist_ok=True)
    record = {
        "event": event_type,
        "ts": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    with _EVENT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def validate_name(name: str) -> Optional[str]:
    """Return an error string, or None when the name is acceptable."""
    if not name:
        return "Name cannot be empty."
    if not _NAME_RE.match(name):
        return (
            "Name must start with a letter or digit and "
            "contain only A-Z, a-z, 0-9, _, -"
        )
    return None


def validate_new_workspace(name: str, parent: Path) -> Optional[str]:
    """Return an error string, or None when (name, parent) can be used."""
    err = validate_name(name)
    if err:
        return err
    target = parent / name
    if target.exists() and any(target.iterdir()):
        return f"Directory already exists and is not empty: {target}"
    return None


def default_parent() -> Path:
    return _MANAGED_ROOT


def new_workspace(name: str, parent: Path) -> WorkspaceDef:
    """Create the workspace directory and return an un-persisted WorkspaceDef."""
    root = parent / name
    root.mkdir(parents=True, exist_ok=True)
    return WorkspaceDef(
        workspace_id=uuid.uuid4().hex,
        name=name,
        root=str(root.resolve()),
    )
