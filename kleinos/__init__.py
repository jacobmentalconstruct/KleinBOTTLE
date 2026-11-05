"""
kleinos — KleinOS in-game computer UI for KleinBOTTLE.

Quick start:

    from kleinos import KleinApp, KleinPC

    class MyApp(KleinApp):
        title = "My App"
        def commands(self):
            return [("Hello", lambda: "Hello, KleinOS!")]

    pc = KleinPC(root, apps=[MyApp()])
    pc.show()
"""

from kleinos.klein_app import KleinApp, KleinChat, KleinGame
from kleinos.klein_pc import KleinPC
from kleinos.monitors import KleinMonitors

__all__ = ["KleinApp", "KleinChat", "KleinGame", "KleinPC", "KleinMonitors"]
