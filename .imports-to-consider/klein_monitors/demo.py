"""
klein_monitors/demo.py

KleinOS demo — the in-game computer as a single unified window.

Left sidebar : Terminal | Apps (expandable) | Settings
Right panel  : active content inside a green CRT bezel

    python .imports-to-consider/klein_monitors/demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_PKG_PARENT = Path(__file__).resolve().parent.parent
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

import tkinter as tk
from klein_monitors import KleinApp, KleinPC
from klein_monitors.chat_pane import OllamaChat
from klein_monitors.game_pane import SpaceInvaders
from klein_monitors.kb_surfaces import WorldBuilder, TextAdventure


# ======================================================================
# Bundled apps
# ======================================================================


class NotesApp(KleinApp):
    title = "Notes"

    def __init__(self):
        self._notes: list[str] = []
        self._counter = 0

    def commands(self):
        return [
            ("Add note",   self._add),
            ("List notes", self._list),
            ("Clear all",  self._clear),
        ]

    def _add(self):
        self._counter += 1
        note = f"[{self._counter}] Remember to check the locked drawer."
        self._notes.append(note)
        return f"Added: {note}"

    def _list(self):
        if not self._notes:
            return "No notes yet."
        return "\n".join(self._notes)

    def _clear(self):
        self._notes.clear()
        return "All notes cleared."


# ======================================================================
# Entry point
# ======================================================================

def main():
    root = tk.Tk()
    root.withdraw()

    pc = KleinPC(
        root,
        apps=[WorldBuilder(), TextAdventure(), OllamaChat(), NotesApp()],
        games=[SpaceInvaders()],
        title="KleinBOTTLE PC",
    )
    pc.show()
    root.mainloop()


if __name__ == "__main__":
    main()
