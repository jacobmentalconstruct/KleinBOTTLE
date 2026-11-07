"""PMBridge: wraps AdapterSession for use from the pane and the terminal."""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

from kleinos.workspace_manager.installer import has_sidecar, sidecar_path


class PMBridge:
    """Single-session bridge to ProjectMapper's AdapterSession.

    Shared between the ProjectContext pane and the KleinOS terminal executor.
    Thread-safe: only one .call() runs at a time via an internal lock.
    """

    def __init__(self) -> None:
        self._session = None
        self._root: Optional[Path] = None
        self._lock = threading.Lock()

    # ── Lifecycle ──────────────────────────────────────────────────────

    def open(self, root: Path) -> None:
        """Open a session on root; closes any previous session first."""
        self.close()
        sidecar = sidecar_path(root)
        src = str(sidecar / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from projectmapper.adapters.session import AdapterSession  # type: ignore[import]
        with self._lock:
            self._session = AdapterSession(root=root, origin="kleinpc")
            self._root = root

    def close(self) -> None:
        with self._lock:
            if self._session is not None:
                try:
                    self._session.close()
                except Exception:
                    pass
                self._session = None
                self._root = None

    @property
    def root(self) -> Optional[Path]:
        return self._root

    @property
    def is_open(self) -> bool:
        return self._session is not None

    # ── Actions ────────────────────────────────────────────────────────

    def call(self, action: str, payload: Optional[dict] = None) -> dict:
        """Call a ProjectMapper action. Returns the outcome dict."""
        with self._lock:
            if self._session is None:
                return {
                    "status": "failed",
                    "data": {},
                    "error": {
                        "code": "no_session",
                        "message": "No project open. Use 'pm root <path>' or the pane.",
                    },
                }
            return self._session.call(action, payload or {})

    # ── Terminal command router ────────────────────────────────────────

    def handle_terminal_command(self, args: str) -> str:
        """Handle the argument string from 'pm <args>'. Returns formatted output."""
        parts = args.strip().split(None, 1)
        sub  = parts[0].lower() if parts else "help"
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub in ("help", ""):
            return (
                "pm commands:\n"
                "  pm help                   — this list\n"
                "  pm root <path>            — open a project folder\n"
                "  pm root                   — show current root\n"
                "  pm status                 — show project state\n"
                "  pm scan                   — scan project tree\n"
                "  pm compile                — compile SQLite snapshot\n"
                "  pm export <projection>    — export snapshot\n"
                "                              projections: tree  filedump  combined  manifest\n"
            )

        if sub == "root":
            if not rest:
                current = str(self._root) if self._root else "(none)"
                return f"current root: {current}"
            path = Path(rest)
            if not path.is_dir():
                return f"[error] not a directory: {rest}"
            if not has_sidecar(path):
                return f"[error] no .project-mapper sidecar found in {path}"
            try:
                self.open(path)
                return f"[ok] opened {path}"
            except Exception as exc:
                return f"[error] {exc}"

        if sub == "status":
            return _format_outcome(self.call("state.get"))

        if sub == "scan":
            return _format_scan(self.call("project.scan"))

        if sub == "compile":
            return _format_outcome(self.call("snapshot.compile"))

        if sub == "export":
            proj = rest or "combined"
            valid = ("tree", "filedump", "combined", "manifest")
            if proj not in valid:
                return f"[error] unknown projection '{proj}'. Choose: {' '.join(valid)}"
            return _format_outcome(self.call("snapshot.export", {"projection": proj}))

        return f"[error] unknown pm command '{sub}'. Type 'pm help'."


# ── Formatters ─────────────────────────────────────────────────────────

def _format_outcome(outcome: dict) -> str:
    if outcome.get("status") == "failed":
        err = outcome.get("error") or {}
        return f"[error] {err.get('code', 'failed')}: {err.get('message', '')}"
    data = outcome.get("data") or {}
    lines: list[str] = []
    if "path" in data:
        lines.append(f"path:     {data['path']}")
    if "file_count" in data:
        lines.append(f"files:    {data['file_count']}")
    if "scan_revision" in data:
        lines.append(f"revision: {data['scan_revision']}")
    if not lines:
        snippet = json.dumps(data, indent=2)
        lines.append(snippet[:800] + ("…" if len(snippet) > 800 else ""))
    return "\n".join(lines)


def _format_scan(outcome: dict) -> str:
    if outcome.get("status") == "failed":
        err = outcome.get("error") or {}
        return f"[error] {err.get('code')}: {err.get('message')}"
    data = outcome.get("data") or {}
    rows = data.get("rows", [])
    if not rows:
        return "(no files found)"
    lines = [f"{len(rows)} files:"]
    for row in rows[:200]:
        rel = row.get("relative_path") or row.get("path") or str(row)
        lines.append(f"  {rel}")
    if len(rows) > 200:
        lines.append(f"  … and {len(rows) - 200} more")
    return "\n".join(lines)


# ── Terminal executor factory ──────────────────────────────────────────

def make_pm_executor(bridge: PMBridge) -> Callable[[str], str]:
    """Return a terminal executor that handles 'pm' commands and the standard built-ins."""

    def executor(text: str) -> str:
        parts = text.split(None, 1)
        if not parts:
            return ""
        cmd  = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if cmd == "pm":
            return bridge.handle_terminal_command(rest)
        if cmd == "help":
            return (
                "Built-in commands:\n"
                "  help          — this list\n"
                "  echo <text>   — repeat text\n"
                "  about         — version info\n"
                "  pm <cmd>      — Project Mapper  (pm help for commands)\n"
            )
        if cmd == "echo":
            return rest
        if cmd == "about":
            return "KleinOS Terminal  v1.0  — KleinBOTTLE"
        return f"'{cmd}' is not recognised.  Type 'help' for commands."

    return executor
