"""
kleinos/pipeline_client.py

Single point of contact for the image-generation-pipeline package.

The pipeline is installed via pip:
    pip install git+https://github.com/jacobmentalconstruct/image-generation-pipeline.git

It can also be used directly from the git submodule at tools/image-pipeline/
(for local development), which is the fallback when the pip package is absent.

Public API:
    is_present()       -> bool   package importable (pip or submodule)
    ensure_on_path()   -> bool   makes `import pipeline` work; returns is_present()
    convert_available()-> bool   is_present() + torch + numpy importable
    is_configured()    -> bool   user completed the setup gate
    mark_configured()           persist setup_complete = True
    pipeline_root()    -> Path   submodule root (dev/fallback use only)
"""
from __future__ import annotations

import sys
from pathlib import Path

_KB_ROOT   = Path(__file__).resolve().parent.parent
_SUBMODULE = _KB_ROOT / "tools" / "image-pipeline"

# ── Path resolution (submodule / dev fallback) ────────────────────────

def pipeline_root() -> Path:
    """Return the submodule root, preferring any config override."""
    try:
        from kleinos import config as _cfg
        p = _cfg.load().get("image_pipeline", {}).get("path", "")
        if p:
            return Path(p)
    except Exception:
        pass
    return _SUBMODULE


# ── Availability checks ───────────────────────────────────────────────

def is_present() -> bool:
    """
    True if `import pipeline` will succeed.
    Checks pip-installed package first; falls back to the git submodule.
    """
    import importlib.util
    if importlib.util.find_spec("pipeline") is not None:
        return True
    # Submodule fallback (dev mode / not pip-installed)
    return (pipeline_root() / "pipeline" / "__init__.py").exists()


def convert_available() -> bool:
    """True when is_present() AND torch + numpy are importable."""
    if not is_present():
        return False
    try:
        import importlib
        importlib.import_module("torch")
        importlib.import_module("numpy")
        return True
    except ImportError:
        return False


# ── Setup gate ────────────────────────────────────────────────────────

def is_configured() -> bool:
    """
    True when the user has completed the pipeline setup gate at least once.
    Does NOT mean ComfyUI is currently running — only that the user has
    made an explicit choice about how to use the pipeline.
    """
    try:
        from kleinos import config as _cfg
        return bool(_cfg.load().get("image_pipeline", {}).get("setup_complete", False))
    except Exception:
        return False


def mark_configured() -> None:
    """Persist setup_complete = True.  Called by PipelineSetupPane on save."""
    try:
        from kleinos import config as _cfg
        cfg = _cfg.load()
        cfg.setdefault("image_pipeline", {})["setup_complete"] = True
        _cfg.save(cfg)
    except Exception:
        pass


# ── Path setup (submodule fallback only) ─────────────────────────────

def ensure_on_path() -> bool:
    """
    Ensure `import pipeline` will work.

    If the package was pip-installed it is already importable — returns True
    immediately without touching sys.path.  For the submodule fallback, inserts
    the submodule root onto sys.path.  Returns False when neither is available.
    """
    import importlib.util
    if importlib.util.find_spec("pipeline") is not None:
        return True          # pip-installed: nothing to do
    # Submodule fallback
    sub = pipeline_root() / "pipeline" / "__init__.py"
    if not sub.exists():
        return False
    root = str(pipeline_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    return True
