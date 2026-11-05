"""
DEPRECATED — entry point moved to kleinos/__main__.py.

Run the game with:
    py -m kleinos        (Windows)
    python3 -m kleinos   (Unix)

This file is kept only for git history. Do not use it.
"""
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from .game import GameSession
from .world_builder import WorldBuilder
from .world_store import WorldStore
from .surfaces.builder import BuilderSurface
from .surfaces.game import GameSurface
from .ui_theme import apply_theme


def main() -> None:
    root = tk.Tk()
    apply_theme(root)
    root.title("Adventure — World Builder & Play")
    root.geometry("1160x760")
    world_file = Path(__file__).resolve().parents[1] / "data" / "world.json"
    store = WorldStore(world_file)
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)
    builder = BuilderSurface(notebook, WorldBuilder(store))
    game = GameSurface(notebook, GameSession(store))
    notebook.add(builder, text="World Builder")
    notebook.add(game, text="Play")
    # Re-entering Play reloads saved editor data, not unsaved form changes.
    # Runtime state is intentionally temporary in this proof of concept.
    def on_switch(_event=None) -> None:
        if notebook.select() == str(game):
            game.reload_world()
    notebook.bind("<<NotebookTabChanged>>", on_switch)
    root.mainloop()


if __name__ == "__main__":
    main()
