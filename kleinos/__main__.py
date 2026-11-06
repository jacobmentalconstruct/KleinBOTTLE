"""
kleinos/__main__.py

KleinOS — the KleinBOTTLE in-game computer.

    python -m kleinos
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add KleinBOTTLE root to sys.path so "from src.X" imports work.
_KB_ROOT = Path(__file__).resolve().parent.parent
if str(_KB_ROOT) not in sys.path:
    sys.path.insert(0, str(_KB_ROOT))

import tkinter as tk
from kleinos import KleinApp, KleinPC
from kleinos.chat_pane import OllamaChat
from kleinos.game_pane import SpaceInvaders
from kleinos.kb_surfaces import WorldBuilder, TextAdventure


class NotesApp(KleinApp):
    title = "Notes"
    description = "In-game notepad — jot hints, clues, and reminders."

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


def main():
    root = tk.Tk()
    root.withdraw()

    pc = KleinPC(
        root,
        apps=[WorldBuilder(), OllamaChat(), NotesApp()],
        games=[TextAdventure(), SpaceInvaders()],
        title="KleinBOTTLE PC",
    )
    pc.show()
    root.mainloop()


if __name__ == "__main__":
    main()
