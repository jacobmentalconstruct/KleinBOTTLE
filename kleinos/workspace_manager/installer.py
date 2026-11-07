"""Sidecar detection, installation, and in-process launch for .project-mapper."""
from __future__ import annotations

import importlib
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    import tkinter as tk

_REPO_URL = "https://github.com/jacobmentalconstruct/.project-mapper.git"
_SIDECAR  = ".project-mapper"


# ── Detection ──────────────────────────────────────────────────────────

def sidecar_path(workspace_root: Path) -> Path:
    return workspace_root / _SIDECAR


def has_sidecar(workspace_root: Path) -> bool:
    """True when .project-mapper/src/projectmapper/ is present."""
    return (sidecar_path(workspace_root) / "src" / "projectmapper").is_dir()


def sidecar_rev(workspace_root: Path) -> Optional[str]:
    """Return the sidecar's git short-rev, or None if unavailable."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(sidecar_path(workspace_root)),
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


# ── Installation ───────────────────────────────────────────────────────

def _venv_python(sidecar: Path) -> Path:
    scripts = "Scripts" if sys.platform == "win32" else "bin"
    exe     = "python.exe" if sys.platform == "win32" else "python"
    return sidecar / ".venv" / scripts / exe


def _stream(cmd: list, cwd: Path, on_line: Callable[[str], None]) -> int:
    """Run a subprocess, forwarding stdout+stderr lines to on_line. Returns exit code."""
    proc = subprocess.Popen(
        cmd, cwd=str(cwd),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        on_line(line.rstrip())
    proc.wait()
    return proc.returncode


def install(
    workspace_root: Path,
    on_progress: Callable[[str], None],
    on_done: Callable[[str], None],
    on_error: Callable[[str], None],
) -> None:
    """Clone and pip-install .project-mapper in a background thread.

    on_done(rev) is called on success; on_error(msg) on failure.
    Both fire from the worker thread — marshal to the UI thread with after().
    """

    def _worker() -> None:
        sidecar = sidecar_path(workspace_root)

        on_progress(f"Cloning {_REPO_URL} …")
        rc = _stream(
            ["git", "clone", _REPO_URL, str(sidecar)],
            workspace_root, on_progress,
        )
        if rc != 0:
            on_error(f"git clone failed (exit {rc})")
            return

        rev = sidecar_rev(workspace_root) or "unknown"
        on_progress(f"Cloned at revision {rev}")

        on_progress("Creating virtual environment …")
        rc = _stream(
            [sys.executable, "-m", "venv", str(sidecar / ".venv")],
            workspace_root, on_progress,
        )
        if rc != 0:
            on_error(f"venv creation failed (exit {rc})")
            return

        venv_py = _venv_python(sidecar)
        on_progress("Installing (pip install -e) …")
        rc = _stream(
            [str(venv_py), "-m", "pip", "install", "-e", str(sidecar)],
            workspace_root, on_progress,
        )
        if rc != 0:
            on_error(f"pip install failed (exit {rc})")
            return

        # Verify: projectmapper has no third-party deps so we can import from src/
        on_progress("Verifying …")
        src = str(sidecar / "src")
        try:
            if src not in sys.path:
                sys.path.insert(0, src)
            importlib.import_module("projectmapper")
            on_done(rev)
        except Exception as exc:
            on_error(f"import projectmapper failed: {exc}")

    threading.Thread(target=_worker, daemon=True).start()


# ── In-process launch ──────────────────────────────────────────────────

def launch_in_process(
    workspace_root: Path,
    on_close: Callable[[], None],
) -> "tk.Toplevel | None":
    """Import ProjectMapperApp from the sidecar and open it on a Toplevel.

    Uses KleinBOTTLE's existing Tk mainloop — no subprocess needed.
    ProjectMapperApp builds its UI directly onto a Toplevel (not a Frame),
    so it opens as a companion window rather than being drawn inside the CRT bezel.

    Returns the Toplevel on success, None on import failure.
    """
    import tkinter as tk

    sidecar = sidecar_path(workspace_root)
    src = str(sidecar / "src")
    if src not in sys.path:
        sys.path.insert(0, src)

    try:
        mod = importlib.import_module("projectmapper.app")
        ProjectMapperApp = getattr(mod, "ProjectMapperApp")
    except Exception as exc:
        raise RuntimeError(f"Cannot import ProjectMapperApp: {exc}") from exc

    top = tk.Toplevel()
    top.title(f"ProjectMapper — {workspace_root.name}")

    def _on_wm_delete():
        on_close()
        top.destroy()

    top.protocol("WM_DELETE_WINDOW", _on_wm_delete)
    ProjectMapperApp(top, workspace_root)
    return top
