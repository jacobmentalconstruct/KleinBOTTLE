"""
kleinos/__main__.py

KleinBOTTLE — you are sitting at a desk.

    python -m kleinos
"""

from __future__ import annotations

import sys
from pathlib import Path

_KB_ROOT = Path(__file__).resolve().parent.parent
if str(_KB_ROOT) not in sys.path:
    sys.path.insert(0, str(_KB_ROOT))

import tkinter as tk
from kleinos import KleinApp, KleinPC
from kleinos.chat_pane import OllamaChat
from kleinos.game_pane import SpaceInvaders
from kleinos.kb_surfaces import WorldBuilder, TextAdventure, KleinAdventurePane
from kleinos.adventure import TheShack
from kleinos.mahisland import MAHisLAND
from kleinos.palette import BG as _BG, GM_BRIGHT as _BRIGHT, GM_MID as _MID, FG_DIM as _DIM


# ── Apps that live inside the in-game PC ─────────────────────────────

class NotesApp(KleinApp):
    title = "Notes"
    description = "In-game notepad — jot hints, clues, and reminders."

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
        return "\n".join(self._notes) if self._notes else "No notes yet."

    def _clear(self):
        self._notes.clear()
        return "All notes cleared."


# ── Title screen ─────────────────────────────────────────────────────

class TitleScreen(tk.Canvas):
    """Full-window title canvas. ENTER / SPACE / click starts the game."""

    def __init__(self, parent: tk.Widget, *, on_start):
        super().__init__(parent, bg=_BG, highlightthickness=0)
        self._on_start = on_start
        self._blink_visible = True
        self.bind("<Configure>",  self._redraw)
        self.bind("<Return>",     lambda _e: self._start())
        self.bind("<space>",      lambda _e: self._start())
        self.bind("<Button-1>",   lambda _e: self._start())
        self.focus_set()
        self._blink_id: str = self.after(650, self._blink)

    def _redraw(self, _event=None) -> None:
        self.delete("all")
        w = self.winfo_width()  or 960
        h = self.winfo_height() or 680
        cx, cy = w // 2, h // 2
        self.create_text(cx, cy - 70,
                         text="KleinBOTTLE",
                         fill=_BRIGHT, font=("Consolas", 44, "bold"))
        self.create_text(cx, cy - 14,
                         text="A house.  A computer.  A world inside itself.",
                         fill=_MID, font=("Consolas", 11))
        if self._blink_visible:
            self.create_text(cx, cy + 34,
                             text="PRESS  ENTER",
                             fill=_DIM, font=("Consolas", 10))

    def _blink(self) -> None:
        self._blink_visible = not self._blink_visible
        self._redraw()
        self._blink_id = self.after(650, self._blink)

    def _start(self) -> None:
        self.after_cancel(self._blink_id)
        self._on_start()


# ── PC factory + surface patching ────────────────────────────────────

def _make_pc(root: tk.Tk) -> KleinPC:
    return KleinPC(
        root,
        apps=[WorldBuilder(), OllamaChat(), NotesApp()],
        games=[MAHisLAND(), TheShack(), TextAdventure(), SpaceInvaders()],
        title="KleinBOTTLE PC",
    )


def _patch_pc(pane: KleinAdventurePane, root: tk.Tk) -> None:
    """Replace GameSurface._open_computer to launch our full KleinPC."""
    _pc: list[KleinPC] = []

    def open_kleinpc() -> None:
        if _pc:
            try:
                if _pc[0]._window.winfo_exists():
                    _pc[0].show()
                    return
            except tk.TclError:
                pass
            _pc.clear()
        _pc.append(_make_pc(root))
        _pc[0].show()

    for child in pane.winfo_children():
        if hasattr(child, "_open_computer"):
            child._open_computer = open_kleinpc  # type: ignore[attr-defined]
            return


# ── Screen transitions ────────────────────────────────────────────────

def _show_title(root: tk.Tk) -> None:
    for w in root.winfo_children():
        w.destroy()
    TitleScreen(root, on_start=lambda: _show_adventure(root)).pack(fill="both", expand=True)


def _show_adventure(root: tk.Tk) -> None:
    for w in root.winfo_children():
        w.destroy()
    pane = KleinAdventurePane(root, on_exit=lambda: _show_title(root))
    pane.pack(fill="both", expand=True)
    # Defer until GameSurface children are rendered, then patch PC and focus entry
    def _after_render():
        _patch_pc(pane, root)
        for child in pane.winfo_children():
            if hasattr(child, "entry"):
                child.entry.focus_set()  # type: ignore[attr-defined]
                return
    root.after(50, _after_render)


# ── Entry point ───────────────────────────────────────────────────────

def main() -> None:
    root = tk.Tk()
    root.title("KleinBOTTLE")
    root.geometry("960x680")
    root.configure(bg=_BG)
    _show_title(root)
    root.mainloop()


if __name__ == "__main__":
    main()
