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

_SPLASH_PATH = _KB_ROOT / "assets" / "logos" / "klein-bottle-logo.jpg"
_SPLASH_W = 540   # max display width for splash
_SPLASH_H = 300   # max display height for splash

try:
    from PIL import Image as _PilImage, ImageTk as _PilImageTk  # type: ignore[import-untyped]
    _NEAREST = getattr(getattr(_PilImage, "Resampling", _PilImage), "NEAREST", 0)
    _PIL_OK = True
except ImportError:
    _PilImage = _PilImageTk = None  # type: ignore[assignment]
    _NEAREST = 0
    _PIL_OK = False


def _make_splash_photo():
    """Load splash.png and return (PhotoImage, w, h). Call after Tk root exists."""
    if not _PIL_OK or not _SPLASH_PATH.exists():
        return None, 0, 0
    try:
        img = _PilImage.open(_SPLASH_PATH)  # type: ignore[union-attr]
        iw, ih = img.size
        scale = min(_SPLASH_W / iw, _SPLASH_H / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img = img.resize((nw, nh), _NEAREST)
        return _PilImageTk.PhotoImage(img), nw, nh  # type: ignore[union-attr]
    except Exception:
        return None, 0, 0


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
        # Load splash lazily here — Tk root already exists at this point
        self._splash_photo, self._splash_nw, self._splash_nh = _make_splash_photo()
        self.bind("<Configure>",  self._redraw)
        self.bind("<Return>",     lambda _: self._start())
        self.bind("<space>",      lambda _: self._start())
        self.bind("<Button-1>",   lambda _: self._start())
        self.focus_set()
        self._blink_id: str = self.after(650, self._blink)

    def _redraw(self, _=None) -> None:
        self.delete("all")
        w = self.winfo_width()  or 960
        h = self.winfo_height() or 680
        cx, cy = w // 2, h // 2

        if self._splash_photo is not None:
            title_y   = cy - 210
            tagline_y = title_y + 55
            img_top   = tagline_y + 25
            prompt_y  = img_top + self._splash_nh + 35
            self.create_text(cx, title_y,
                             text="KleinBOTTLE",
                             fill=_BRIGHT, font=("Consolas", 44, "bold"))
            self.create_text(cx, tagline_y,
                             text="A house.  A computer.  A world inside itself.",
                             fill=_MID, font=("Consolas", 11))
            self.create_image(cx - self._splash_nw // 2, img_top,
                              anchor="nw", image=self._splash_photo)
        else:
            title_y   = cy - 70
            tagline_y = cy - 14
            prompt_y  = cy + 34
            self.create_text(cx, title_y,
                             text="KleinBOTTLE",
                             fill=_BRIGHT, font=("Consolas", 44, "bold"))
            self.create_text(cx, tagline_y,
                             text="A house.  A computer.  A world inside itself.",
                             fill=_MID, font=("Consolas", 11))
        if self._blink_visible:
            self.create_text(cx, prompt_y,
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

    pane.set_computer_callback(open_kleinpc)
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
    root.geometry("960x800")
    root.minsize(860, 680)
    root.configure(bg=_BG)
    _show_title(root)
    root.mainloop()


if __name__ == "__main__":
    main()
