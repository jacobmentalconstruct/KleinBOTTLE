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


# ======================================================================
# Bundled apps
# ======================================================================

class InventoryApp(KleinApp):
    title = "Inventory"

    def __init__(self):
        self._items = ["Ancient Amulet", "Iron Skeleton Key", "Brass Lantern"]
        self._gold = 42

    def commands(self):
        return [
            ("List items",  self._list),
            ("Check gold",  self._gold_check),
            ("Examine bag", self._examine),
        ]

    def _list(self):
        if not self._items:
            return "Your inventory is empty."
        return "You are carrying:\n" + "\n".join(f"  • {i}" for i in self._items)

    def _gold_check(self):
        return f"You have {self._gold} gold coins."

    def _examine(self):
        return (
            "A well-worn leather satchel, its brass clasp tarnished with age.\n"
            "It smells faintly of old wood and candle wax."
        )


class StatusApp(KleinApp):
    title = "Character Status"

    def commands(self):
        return [
            ("Health",   lambda: "HP: 18 / 20   Status: Healthy"),
            ("Location", lambda: "You are in the Study.\nA desk sits against the north wall."),
            ("Quests",   lambda: "Active quest: none.\nTalk to someone to begin an adventure."),
        ]


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
        apps=[InventoryApp(), StatusApp(), NotesApp(), OllamaChat()],
        games=[SpaceInvaders()],
        title="KleinBOTTLE PC",
    )
    pc.show()
    root.mainloop()


if __name__ == "__main__":
    main()
