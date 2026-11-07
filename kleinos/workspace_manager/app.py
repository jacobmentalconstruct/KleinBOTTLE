"""KleinApp adapter for the Workspace Manager."""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from kleinos.workspace_manager.session_bridge import PMBridge


class WorkspaceManagerApp:
    """KleinOS app — folder picker + ProjectMapper actions via AdapterSession."""

    title = "Project Context"
    description = "Open a project folder and explore it via ProjectMapper."

    def __init__(self, bridge: Optional["PMBridge"] = None) -> None:
        self._bridge = bridge

    def create(self, parent: tk.Widget, on_exit: Callable[[], None]) -> tk.Widget:
        from kleinos.workspace_manager.pane import ProjectContextPane
        from kleinos.workspace_manager.session_bridge import PMBridge
        bridge = self._bridge if self._bridge is not None else PMBridge()
        pane = ProjectContextPane(parent, bridge=bridge, on_exit=on_exit)
        pane.pack(fill="both", expand=True)
        return pane
