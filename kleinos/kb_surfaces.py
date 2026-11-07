"""
kleinos/kb_surfaces.py

Wrappers that host KleinBOTTLE's BuilderSurface and GameSurface inside
the KleinOS monitor, re-themed with the green phosphor palette.

Both wrappers follow the KleinChat pattern: create(parent, on_exit) -> tk.Widget
and live under the Apps section of the KleinPC sidebar.

Default world file: <KleinBOTTLE>/data/world.json
The builder writes there; the game reads from there — so builds are immediately
playable by switching to the Play app.
"""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

# ── Resolve KleinBOTTLE project root ─────────────────────────────────
# This file: kleinos/kb_surfaces.py
# KleinBOTTLE root: ..  (one level up)
_KB_ROOT = Path(__file__).resolve().parent.parent
_KB_SRC  = str(_KB_ROOT)          # add to sys.path so "from src.X import Y" works

_DEFAULT_WORLD = _KB_ROOT / "data" / "world.json"


def _ensure_path() -> None:
    if _KB_SRC not in sys.path:
        sys.path.insert(0, _KB_SRC)


# ── Lazy imports (only when a surface is first created) ───────────────

def _import_builder():
    _ensure_path()
    from src.surfaces.builder import BuilderSurface   # type: ignore[import]
    from src.world_builder import WorldBuilder         # type: ignore[import]
    from src.world_store import WorldStore             # type: ignore[import]
    return BuilderSurface, WorldBuilder, WorldStore


def _import_game():
    _ensure_path()
    from src.surfaces.game import GameSurface   # type: ignore[import]
    from src.game import GameSession             # type: ignore[import]
    from src.world_store import WorldStore       # type: ignore[import]
    return GameSurface, GameSession, WorldStore


# ── Shared green-theme helper ─────────────────────────────────────────

def _patch_ui_theme() -> None:
    """
    Replace KleinBOTTLE's ui_theme colour constants with our green palette
    so that style_text() calls inside BuilderSurface/GameSurface use the
    right colours.  Called once per process.
    """
    _ensure_path()
    try:
        import src.ui_theme as _ui   # type: ignore[import]
        from kleinos import klein_theme as _kt
        _ui.BACKGROUND = _kt.BG
        _ui.INSET      = _kt.INSET
        _ui.SURFACE    = _kt.SURFACE
        _ui.ACCENT     = _kt.ACCENT
        _ui.TEXT       = _kt.TEXT
        _ui.MUTED      = _kt.MUTED
        _ui.BORDER     = _kt.BORDER
        _ui.FONT_UI    = _kt.FONT_UI
        _ui.FONT_HEADING = _kt.FONT_HEADING
        _ui.FONT_STORY = _kt.FONT_STORY
    except ImportError:
        pass


_ui_patched = False


def _apply_theme(root: tk.Misc) -> None:
    global _ui_patched
    from kleinos import klein_theme
    klein_theme.apply(root)
    if not _ui_patched:
        _patch_ui_theme()
        _ui_patched = True


# ── KleinBuilderPane ──────────────────────────────────────────────────

class KleinBuilderPane(tk.Frame):
    """
    Hosts BuilderSurface inside a green-themed tk.Frame.
    world_path defaults to KleinBOTTLE/data/world.json.
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        world_path: Path = _DEFAULT_WORLD,
        on_exit: Optional[Callable] = None,
    ):
        super().__init__(parent, bg="#010a01", bd=0, highlightthickness=0)
        self._on_exit = on_exit
        try:
            _apply_theme(self)
            BuilderSurface, WorldBuilder, WorldStore = _import_builder()
            builder = WorldBuilder(WorldStore(world_path))
            surface = BuilderSurface(self, builder)
            surface.pack(fill="both", expand=True)
        except Exception as exc:
            self._error(str(exc))

    def _error(self, msg: str) -> None:
        tk.Label(
            self, text=f"World Builder unavailable:\n{msg}",
            bg="#010a01", fg="#00dd33", font=("Consolas", 9),
            justify="left", wraplength=400,
        ).pack(padx=16, pady=16, anchor="nw")


# ── KleinAdventurePane ────────────────────────────────────────────────

class KleinAdventurePane(tk.Frame):
    """
    Hosts GameSurface inside a green-themed tk.Frame.
    Injects a RoomImagePanel above the scrollable content sections.
    world_path defaults to KleinBOTTLE/data/world.json.
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        world_path: Path = _DEFAULT_WORLD,
        on_exit: Optional[Callable] = None,
    ):
        super().__init__(parent, bg="#010a01", bd=0, highlightthickness=0)
        self._on_exit = on_exit
        self._session = None
        self._surface = None
        self._last_room_id: Optional[str] = None
        try:
            _apply_theme(self)
            GameSurface, GameSession, WorldStore = _import_game()
            session = GameSession(WorldStore(world_path))
            self._session = session

            from kleinos.room_panel import RoomImagePanel

            surface = GameSurface(self, session)
            surface.pack(fill="both", expand=True)
            self._surface = surface

            # Inject room image panel into the left column, above the
            # scrollable sections (_story_frame).
            left   = surface._main_col       # type: ignore[attr-defined]
            anchor = surface._story_frame    # type: ignore[attr-defined]

            self._room_panel = RoomImagePanel(left)
            self._room_panel.pack(fill="x", before=anchor)

            self._poll_room()
        except Exception as exc:
            self._error(str(exc))

    def set_computer_callback(self, cb: Callable) -> None:
        """Delegate computer-open callback to the hosted GameSurface."""
        if self._surface is not None:
            self._surface.set_computer_callback(cb)  # type: ignore[attr-defined]

    def _poll_room(self) -> None:
        """Update the room image panel whenever the player moves to a new room."""
        try:
            s = self._session
            if s is not None:
                rid = s.room_id
                if rid is not None and rid != self._last_room_id:
                    self._last_room_id = rid
                    room = next(
                        (r for r in s.world["rooms"] if r["id"] == rid), None
                    )
                    if room:
                        self._room_panel.update_room(
                            rid,
                            room["name"],
                            room["description"],
                            room.get("area", ""),
                        )
        except Exception:
            pass
        self.after(400, self._poll_room)

    def _error(self, msg: str) -> None:
        tk.Label(
            self, text=f"Text Adventure unavailable:\n{msg}",
            bg="#010a01", fg="#00dd33", font=("Consolas", 9),
            justify="left", wraplength=400,
        ).pack(padx=16, pady=16, anchor="nw")


# ── KleinChat registrations ───────────────────────────────────────────

from kleinos.klein_app import KleinChat  # noqa: E402


class WorldBuilder(KleinChat):
    title = "World Builder"
    description = "Design and edit rooms, items, and connections for the game world."

    def __init__(self, world_path: Path = _DEFAULT_WORLD):
        self._world_path = world_path

    def create(self, parent: tk.Widget, on_exit: Callable) -> tk.Widget:
        return KleinBuilderPane(parent, world_path=self._world_path, on_exit=on_exit)


class TextAdventure(KleinChat):
    title = "KleinBOTTLE"
    description = "Play the KleinBOTTLE text adventure."

    def __init__(self, world_path: Path = _DEFAULT_WORLD):
        self._world_path = world_path

    def create(self, parent: tk.Widget, on_exit: Callable) -> tk.Widget:
        return _KleinBOTTLETitleScreen(parent, world_path=self._world_path, on_exit=on_exit)


class _KleinBOTTLETitleScreen(tk.Canvas):
    """Title screen for the in-PC KleinBOTTLE game. Click/Enter starts the adventure."""

    _BG     = "#010a01"
    _BRIGHT = "#00ff55"
    _MID    = "#00aa33"
    _DIM    = "#004d1a"

    def __init__(self, parent: tk.Widget, *, world_path: Path, on_exit: Callable):
        super().__init__(parent, bg=self._BG, highlightthickness=0)
        self._parent     = parent
        self._world_path = world_path
        self._on_exit    = on_exit
        self._blink_visible = True
        self._blink_id: str = ""
        self.bind("<Configure>", self._redraw)
        self.bind("<Return>",   lambda _: self._start())
        self.bind("<space>",    lambda _: self._start())
        self.bind("<Button-1>", lambda _: self._start())
        self.focus_set()
        self._blink_id = self.after(650, self._blink)

    def _redraw(self, _=None) -> None:
        self.delete("all")
        w = self.winfo_width()  or 600
        h = self.winfo_height() or 400
        cx, cy = w // 2, h // 2

        self.create_text(cx, cy - 60,
                         text="KleinBOTTLE",
                         fill=self._BRIGHT, font=("Consolas", 32, "bold"))
        self.create_text(cx, cy - 10,
                         text="A house.  A computer.  A world inside itself.",
                         fill=self._MID, font=("Consolas", 9))
        if self._blink_visible:
            self.create_text(cx, cy + 30,
                             text="PRESS  ENTER",
                             fill=self._DIM, font=("Consolas", 9))

    def _blink(self) -> None:
        self._blink_visible = not self._blink_visible
        self._redraw()
        self._blink_id = self.after(650, self._blink)

    def _start(self) -> None:
        if self._blink_id:
            self.after_cancel(self._blink_id)
        self.destroy()
        pane = KleinAdventurePane(self._parent, world_path=self._world_path, on_exit=self._on_exit)
        pane.pack(fill="both", expand=True)
