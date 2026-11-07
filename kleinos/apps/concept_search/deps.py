"""Dependency management for concept_search.

Handles detection and optional installation of sentence-transformers.
Exposes is_semantic_available() for both CLI gating and future UI greying.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys


# ---------------------------------------------------------------------------
# Public surface — UI panels query this to decide whether to grey the button
# ---------------------------------------------------------------------------

def is_semantic_available() -> bool:
    """Return True if sentence-transformers is importable right now."""
    return importlib.util.find_spec("sentence_transformers") is not None


# ---------------------------------------------------------------------------
# Install flow
# ---------------------------------------------------------------------------

_PACKAGE = "sentence-transformers"
_SIZE_WARNING = (
    "sentence-transformers requires PyTorch (~1-2 GB on first install).\n"
    "This is a one-time download; subsequent runs are instant."
)


def prompt_install(*, interactive: bool = True) -> bool:
    """Ask the user whether to install sentence-transformers, then do it.

    Returns True if the package is available after the call (either it was
    already there, the user confirmed and install succeeded, or the user
    said no and it was already installed).
    Returns False if the user declined or the install failed.
    """
    if is_semantic_available():
        return True

    print()
    print("Semantic search requires sentence-transformers, which is not installed.")
    print(_SIZE_WARNING)
    print()

    if not interactive:
        print("Run with --install to install it, or install manually:")
        print(f"  pip install {_PACKAGE}")
        return False

    try:
        answer = input("Install now? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        return False

    if answer not in {"y", "yes"}:
        print("Skipped. Falling back to keyword search.")
        return False

    print(f"\nInstalling {_PACKAGE} ...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", _PACKAGE],
        check=False,
    )

    if result.returncode != 0:
        print(f"\nInstall failed (exit {result.returncode}). Falling back to keyword search.")
        return False

    if not is_semantic_available():
        print("\nInstall appeared to succeed but the package is not importable. "
              "Try restarting your session.")
        return False

    print("\nsentence-transformers installed successfully.")
    return True


def ensure_semantic(*, interactive: bool = True) -> bool:
    """Gate for semantic mode. Returns True if ready to use, False otherwise."""
    if is_semantic_available():
        return True
    return prompt_install(interactive=interactive)
