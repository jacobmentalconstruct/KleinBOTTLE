"""KleinApp adapter for the Workspace Manager."""
from __future__ import annotations

import tkinter as tk
from typing import Callable


class WorkspaceManagerApp:
    """Registers as a KleinChat-style app (has create(), not commands())."""

    title = "Workspace Manager"
    description = "Create workspaces and install ProjectMapper sidecars."

    def create(self, parent: tk.Widget, on_exit: Callable[[], None]) -> tk.Widget:
        from kleinos.workspace_manager.pane import WorkspacePane
        pane = WorkspacePane(parent, on_exit=on_exit)
        pane.pack(fill="both", expand=True)
        return pane
