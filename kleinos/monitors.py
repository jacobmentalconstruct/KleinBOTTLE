"""
klein_monitors/monitors.py

KleinMonitors — dual retro-monitor display for KleinBOTTLE.

Creates a tk.Toplevel with two side-by-side RetroMonitorFrames:
  - Left  (amber): AppPane showing a KleinApp
  - Right (green): TerminalPane wired to an optional command executor

Usage:
    from kleinos import KleinMonitors, KleinApp

    class InventoryApp(KleinApp):
        title = "Inventory"
        def commands(self):
            return [("List items", lambda: "Amulet, brass lantern")]

    monitors = KleinMonitors(root, app=InventoryApp())
    monitors.set_executor(my_backend.execute)
    monitors.show()
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from kleinos.app_pane import AppPane
from kleinos.klein_app import KleinApp
from kleinos.retro_monitor_frame import RetroMonitorFrame
from kleinos.terminal_pane import TerminalPane

_BG = "#050508"


class KleinMonitors:
    """
    Dual-monitor display.

    Parameters
    ----------
    root        : Tkinter root or Toplevel to own the window
    app         : initial KleinApp for the left monitor
    executor    : callable(text: str) -> str for the right terminal;
                  defaults to built-in mini-shell if None
    title       : window title
    """

    def __init__(
        self,
        root: tk.Misc,
        *,
        app: Optional[KleinApp] = None,
        executor: Optional[Callable[[str], str]] = None,
        title: str = "KleinBOTTLE PC",
    ):
        self._window = tk.Toplevel(root)
        self._window.title(title)
        self._window.configure(bg=_BG)
        self._window.resizable(False, False)

        outer = tk.Frame(self._window, bg=_BG)
        outer.pack(padx=16, pady=16)

        # Left monitor — amber, app pane
        self._left_mon = RetroMonitorFrame(outer, bezel="amber")
        self._left_mon.pack(side="left", padx=(0, 12))

        _app = app or _DefaultApp()
        self._app_pane = AppPane(self._left_mon.screen, app=_app)
        self._app_pane.pack(fill="both", expand=True)

        # Right monitor — green, terminal or swappable app
        self._right_mon = RetroMonitorFrame(outer, bezel="green")
        self._right_mon.pack(side="left")

        self._executor = executor
        self._terminal = TerminalPane(self._right_mon.screen, executor=executor)
        self._terminal.pack(fill="both", expand=True)

        # Hide until show() is called
        self._window.withdraw()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Make the window visible."""
        self._window.deiconify()
        self._window.lift()

    def hide(self) -> None:
        self._window.withdraw()

    def load_app(self, app: KleinApp) -> None:
        """Swap the left-monitor app at runtime."""
        self._app_pane.load_app(app)

    def set_executor(self, executor: Callable[[str], str]) -> None:
        """Replace the terminal's command executor."""
        self._terminal._executor = executor

    def write_terminal(self, text: str) -> None:
        """Push text into the right terminal from external code."""
        self._terminal.write(text)

    def swap_right_app(self, app: KleinApp) -> None:
        """Replace the right monitor contents with an AppPane for app."""
        for w in self._right_mon.screen.winfo_children():
            w.destroy()
        pane = AppPane(self._right_mon.screen, app=app)
        pane.pack(fill="both", expand=True)

    def swap_right_terminal(self) -> None:
        """Restore the right monitor to a TerminalPane."""
        for w in self._right_mon.screen.winfo_children():
            w.destroy()
        self._terminal = TerminalPane(
            self._right_mon.screen, executor=self._executor
        )
        self._terminal.pack(fill="both", expand=True)

    @property
    def window(self) -> tk.Toplevel:
        return self._window


# ------------------------------------------------------------------
# Placeholder shown before an app is loaded
# ------------------------------------------------------------------

class _DefaultApp(KleinApp):
    title = "No App Loaded"

    def commands(self):
        return [("Status", lambda: "No app is currently loaded.")]
