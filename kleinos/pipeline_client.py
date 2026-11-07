"""
kleinos/pipeline_client.py

Single point of contact for the image-generation-pipeline submodule.

Consumers import from here rather than duplicating path logic or doing
ad-hoc sys.path manipulation themselves:

    from kleinos.pipeline_client import ensure_on_path, is_present, convert_available

The pipeline is a git submodule at tools/image-pipeline/ and is *optional* —
all callers must degrade gracefully when it is absent or its ML dependencies
are not installed.
"""
from __future__ import annotations

import sys
from pathlib import Path

_KB_ROOT   = Path(__file__).resolve().parent.parent
_SUBMODULE = _KB_ROOT / "tools" / "image-pipeline"


# ── Path resolution ───────────────────────────────────────────────────

def pipeline_root() -> Path:
    """Return the pipeline root, preferring any override set in config."""
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
    """True when the pipeline package directory exists and is non-empty."""
    pkg = pipeline_root() / "pipeline" / "__init__.py"
    return pkg.exists()


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


# ── Path setup ────────────────────────────────────────────────────────

def ensure_on_path() -> bool:
    """
    Insert the pipeline root onto sys.path so ``import pipeline`` works.
    Returns True if the pipeline is present, False otherwise (caller should
    degrade gracefully).
    """
    if not is_present():
        return False
    root = str(pipeline_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    return True
