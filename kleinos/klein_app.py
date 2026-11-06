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
    description: str = ""

    def commands(self) -> list[tuple[str, Callable[[], str]]]:
        """Return a list of (label, callable) pairs."""
        return []


class KleinGame:
    """
    Base class for canvas-based games in the Games sidebar section.

        class MyGame(KleinGame):
            title = "My Game"

            def create(self, parent, on_exit):
                return MyGameCanvas(parent, on_exit=on_exit)

    create() must return a tk.Widget that fills the content area.
    Call on_exit() when the player quits (e.g. ESC key).
    """
    title: str = "Game"
    description: str = ""

    def create(self, parent: "tk.Widget", on_exit: "Callable[[], None]") -> "tk.Widget":
        raise NotImplementedError


class KleinChat:
    """
    Base class for chat panels in the Chat sidebar section.

        class MyChat(KleinChat):
            title = "My Chat"

            def create(self, parent, on_exit):
                return MyChatPane(parent, on_exit=on_exit)

    create() must return a tk.Widget that fills the content area.
    """
    title: str = "Chat"
    description: str = ""

    def create(self, parent: "tk.Widget", on_exit: "Callable[[], None]") -> "tk.Widget":
        raise NotImplementedError
