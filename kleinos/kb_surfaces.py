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

_BTN_ROW_BG  = "#010a01"
_BTN_FG      = "#005500"
_BTN_FG_ON   = "#00cc33"
_BTN_ACT_BG  = "#001a00"
_BTN_FONT    = ("Consolas", 9)


class KleinAdventurePane(tk.Frame):
    """
    Hosts GameSurface inside a green-themed tk.Frame.
    Left panel: RoomImagePanel (320 px, generated per room).
    Right panel: GameSurface (fills remaining space).
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
        self._computer_cb: Optional[Callable] = None
        self._last_room_id: Optional[str] = None
        try:
            _apply_theme(self)
            GameSurface, GameSession, WorldStore = _import_game()
            session = GameSession(WorldStore(world_path))
            self._session = session

            from kleinos.room_panel import RoomImagePanel

            # Vertical layout: title+image banner → action buttons → game surface
            self._room_panel = RoomImagePanel(self)
            self._room_panel.pack(fill="x")

            self._btn_row = tk.Frame(self, bg=_BTN_ROW_BG)
            self._btn_row.pack(fill="x", padx=4, pady=(0, 2))

            self._btn_power = tk.Button(
                self._btn_row, text="[ ⏻ Power ]",
                bg=_BTN_ROW_BG, fg=_BTN_FG,
                activebackground=_BTN_ACT_BG, activeforeground=_BTN_FG_ON,
                relief="flat", font=_BTN_FONT,
                command=self._toggle_computer,
            )
            self._btn_pet = tk.Button(
                self._btn_row, text="[ Pet ]",
                bg=_BTN_ROW_BG, fg=_BTN_FG,
                activebackground=_BTN_ACT_BG, activeforeground=_BTN_FG_ON,
                relief="flat", font=_BTN_FONT,
                command=self._pet_cat,
            )
            # Buttons are shown/hidden per room in _poll_room
            self._has_terminal = False
            self._has_cat      = False

            surface = GameSurface(self, session)
            surface.pack(fill="both", expand=True)
            self._surface = surface

            self._poll_room()
        except Exception as exc:
            self._error(str(exc))

    def set_computer_callback(self, cb: Callable) -> None:
        self._computer_cb = cb

    def _toggle_computer(self) -> None:
        if self._computer_cb:
            self._computer_cb()
        elif self._surface is not None:
            self._surface.run("use computer")

    def _pet_cat(self) -> None:
        if self._surface is not None:
            self._surface.run("pet cat")

    def _update_btn_row(self, room: dict) -> None:
        kinds = {str(o.get("kind", "")).casefold()
                 for o in room.get("objects", [])
                 if not o.get("hidden", False)}
        has_terminal = "terminal" in kinds
        has_cat      = "cat" in kinds

        if has_terminal != self._has_terminal:
            self._has_terminal = has_terminal
            if has_terminal:
                self._btn_power.pack(side="left", padx=(0, 4))
            else:
                self._btn_power.pack_forget()

        if has_cat != self._has_cat:
            self._has_cat = has_cat
            if has_cat:
                self._btn_pet.pack(side="left", padx=(0, 4))
            else:
                self._btn_pet.pack_forget()

    def _poll_room(self) -> None:
        try:
            s = self._session
            if s is not None:
                rid = s.room_id
                if rid != self._last_room_id:
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
                        self._update_btn_row(room)
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
        return KleinAdventurePane(parent, world_path=self._world_path, on_exit=on_exit)
