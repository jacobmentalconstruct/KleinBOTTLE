"""
klein_monitors — dual retro-monitor display for KleinBOTTLE.

Quick start:

    from klein_monitors import KleinMonitors, KleinApp

    class InventoryApp(KleinApp):
        title = "Inventory"
        def commands(self):
            return [("List items", lambda: "Amulet, brass lantern, iron key")]

    monitors = KleinMonitors(root, app=InventoryApp())
    monitors.show()
"""

from klein_monitors.klein_app import KleinApp
from klein_monitors.klein_pc import KleinPC
from klein_monitors.monitors import KleinMonitors

__all__ = ["KleinApp", "KleinPC", "KleinMonitors"]
