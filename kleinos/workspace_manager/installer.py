"""Clone and pip-install .project-mapper into a workspace sidecar."""
from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

_REPO_URL = "https://github.com/jacobmentalconstruct/.project-mapper.git"
_SIDECAR  = ".project-mapper"


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
    """Install the .project-mapper sidecar in a background thread.

    Calls on_done(rev) on success, on_error(msg) on failure.
    Both are called from the worker thread; callers must marshal to the UI thread.
    """

    def _worker() -> None:
        sidecar = workspace_root / _SIDECAR

        # 1. Clone
        on_progress(f"Cloning {_REPO_URL} …")
        rc = _stream(
            ["git", "clone", _REPO_URL, str(sidecar)],
            workspace_root,
            on_progress,
        )
        if rc != 0:
            on_error(f"git clone failed (exit {rc})")
            return

        # 2. Capture revision
        try:
            rev = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(sidecar), text=True,
            ).strip()
        except Exception:
            rev = "unknown"
        on_progress(f"Cloned at revision {rev}")

        # 3. Create virtual environment
        on_progress("Creating virtual environment …")
        rc = _stream(
            [sys.executable, "-m", "venv", str(sidecar / ".venv")],
            workspace_root,
            on_progress,
        )
        if rc != 0:
            on_error(f"venv creation failed (exit {rc})")
            return

        # 4. pip install -e <sidecar>
        venv_py = _venv_python(sidecar)
        on_progress("Installing project-mapper (pip install -e) …")
        rc = _stream(
            [str(venv_py), "-m", "pip", "install", "-e", str(sidecar)],
            workspace_root,
            on_progress,
        )
        if rc != 0:
            on_error(f"pip install failed (exit {rc})")
            return

        # 5. Verify import
        on_progress("Verifying import …")
        result = subprocess.run(
            [str(venv_py), "-c", "import projectmapper"],
            capture_output=True,
        )
        if result.returncode != 0:
            on_error("import projectmapper failed — installation may be incomplete")
            return

        on_done(rev)

    threading.Thread(target=_worker, daemon=True).start()


def launch(
    workspace_root: Path,
    on_error: Callable[[str], None],
) -> "subprocess.Popen | None":
    """Launch project-mapper in its own native window. Returns the Popen or None."""
    sidecar = workspace_root / _SIDECAR
    venv_py = _venv_python(sidecar)
    if not venv_py.exists():
        on_error(f"Sidecar venv not found: {venv_py}")
        return None
    try:
        proc = subprocess.Popen(
            [str(venv_py), "-m", "projectmapper", str(workspace_root)],
            cwd=str(workspace_root),
        )
        return proc
    except Exception as exc:
        on_error(f"Launch failed: {exc}")
        return None
