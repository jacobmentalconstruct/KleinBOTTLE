"""Concept Search — KleinApp wrapper for the concept_search app.

Exposes two commands inside the KleinOS AppPane chrome:
  Find by Concept (keyword)   always available, no extra deps
  Find by Concept (semantic)  requires sentence-transformers; shows install
                               instructions if missing

Each command opens a concept input dialog then a folder picker, runs the
search, and returns a Markdown report string for the AppPane output area.
"""
from __future__ import annotations

import sys
from pathlib import Path
from tkinter import filedialog, simpledialog

_APPS = Path(__file__).resolve().parent
_KB_ROOT = _APPS.parents[1]
sys.path.insert(0, str(_KB_ROOT))
sys.path.insert(0, str(_APPS))

from kleinos.klein_app import KleinApp
from concept_search import deps, searcher, render as cs_render

_INSTALL_MSG = """\
Semantic search requires sentence-transformers (not installed).

To enable it, run this once from your terminal:

    pip install sentence-transformers

Then restart KleinOS. The keyword mode works now without any extra install.
"""


def _ask_concept() -> str | None:
    return simpledialog.askstring("Concept Search", "Describe what you want to build:") or None


def _pick_dir(title: str) -> str | None:
    return filedialog.askdirectory(title=title) or None


class ConceptSearchApp(KleinApp):
    title = "Concept Search"
    description = "Find existing functions that match a plain-language concept."

    def commands(self):
        sem_label = (
            "Find (semantic)"
            if deps.is_semantic_available()
            else "Find (semantic) [needs install]"
        )
        return [
            ("Find (keyword)",  self._keyword),
            (sem_label,         self._semantic),
        ]

    def _keyword(self) -> str:
        concept = _ask_concept()
        if not concept:
            return "Cancelled."
        path = _pick_dir("Select directory — Concept Search")
        if not path:
            return "Cancelled."
        return cs_render.render_markdown(
            searcher.build_report(concept, path, mode="keyword")
        )

    def _semantic(self) -> str:
        if not deps.is_semantic_available():
            return _INSTALL_MSG
        concept = _ask_concept()
        if not concept:
            return "Cancelled."
        path = _pick_dir("Select directory — Concept Search")
        if not path:
            return "Cancelled."
        return cs_render.render_markdown(
            searcher.build_report(concept, path, mode="combined")
        )
