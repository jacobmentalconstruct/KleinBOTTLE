"""Code Audit — KleinApp wrapper for the duplicate_finder + blocking_scanner apps.

Exposes four commands inside the KleinOS AppPane chrome:
  Scan Duplicates   duplicate + similar function detection
  Dead Code         unused functions, classes, imports
  Complexity        cyclomatic complexity + nesting scores
  Blocking Calls    calls that can freeze a UI or async thread

Each command opens a folder picker, runs the analysis, and returns a Markdown
report string for the AppPane output area.
"""
from __future__ import annotations

import sys
from pathlib import Path
from tkinter import filedialog

# stdlib path
_APPS = Path(__file__).resolve().parent
_KB_ROOT = _APPS.parents[1]
sys.path.insert(0, str(_KB_ROOT))
sys.path.insert(0, str(_APPS))

from kleinos.klein_app import KleinApp
from duplicate_finder import duplicates, dead_code, complexity, render as dup_render
from blocking_scanner import scanner, render as blk_render


def _pick_dir(title: str) -> str | None:
    path = filedialog.askdirectory(title=title)
    return path or None


class CodeAuditApp(KleinApp):
    title = "Code Audit"
    description = "Scan a directory for duplicates, dead code, complexity, and blocking calls."

    def commands(self):
        return [
            ("Scan Project",    self._scan_project),
            ("Scan Duplicates", self._duplicates),
            ("Dead Code",       self._dead_code),
            ("Complexity",      self._complexity),
            ("Blocking Calls",  self._blocking),
        ]

    def _scan_project(self) -> str:
        """Full audit of the kleinos/ source tree — no folder picker needed."""
        path = str(_KB_ROOT / "kleinos")
        sections = [
            f"# KleinOS Self-Audit\n\nTarget: `{path}`\n",
            dup_render.render_duplicates_markdown(duplicates.build_report(path)),
            dup_render.render_dead_code_markdown(dead_code.build_report(path)),
            dup_render.render_complexity_markdown(complexity.build_report(path)),
            blk_render.render_markdown(scanner.build_report(path)),
        ]
        return "\n\n---\n\n".join(sections)

    def _duplicates(self) -> str:
        path = _pick_dir("Select directory — Duplicate Scan")
        if not path:
            return "Cancelled."
        return dup_render.render_duplicates_markdown(
            duplicates.build_report(path)
        )

    def _dead_code(self) -> str:
        path = _pick_dir("Select directory — Dead Code Scan")
        if not path:
            return "Cancelled."
        return dup_render.render_dead_code_markdown(
            dead_code.build_report(path)
        )

    def _complexity(self) -> str:
        path = _pick_dir("Select directory — Complexity Scan")
        if not path:
            return "Cancelled."
        return dup_render.render_complexity_markdown(
            complexity.build_report(path)
        )

    def _blocking(self) -> str:
        path = _pick_dir("Select directory — Blocking Call Scan")
        if not path:
            return "Cancelled."
        return blk_render.render_markdown(
            scanner.build_report(path)
        )
