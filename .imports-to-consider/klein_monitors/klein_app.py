"""
klein_monitors/klein_app.py

Base class for KleinApps — pure Python, no Tkinter required.

An app is just a title and a list of commands.  Each command is a
(label, callable) pair where the callable returns a string to display.

    class InventoryApp(KleinApp):
        title = "Inventory"

        def commands(self):
            return [
                ("List items", self.list_items),
                ("Check gold", lambda: "You have 42 gold coins."),
            ]

        def list_items(self):
            return "Amulet, iron key, brass lantern"
"""

from __future__ import annotations
from typing import Callable


class KleinApp:
    """
    Minimal base class.  Subclass and override title + commands().
    """
    title: str = "App"

    def commands(self) -> list[tuple[str, Callable[[], str]]]:
        """Return a list of (label, callable) pairs."""
        return []
