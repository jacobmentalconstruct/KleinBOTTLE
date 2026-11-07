"""kleinos.workspace_manager — Project Context app for KleinPC."""
from kleinos.workspace_manager.app import WorkspaceManagerApp
from kleinos.workspace_manager.session_bridge import PMBridge, make_pm_executor

__all__ = ["WorkspaceManagerApp", "PMBridge", "make_pm_executor"]
