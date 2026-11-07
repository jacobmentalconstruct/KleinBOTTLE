"""
kleinos/kb_surfaces.py

Wrappers that host KleinBOTTLE's BuilderSurface and GameSurface inside
the KleinOS monitor, re-themed with the green phosphor palette.

Task 1 — World Isolation:
  WorldBuilder edits data/world_wip.json only; data/world.json is Main.
  Save Snapshot copies WIP to data/world_library/.

Task 2 — World Selection:
  TextAdventure opens _WorldSelectScreen first so the player can choose
  Main, Test WIP, or any library snapshot.

Task 3 — Promotion:
  _WorldSelectScreen has a Promote button for each non-Main world.

Task 4 — Room Assistant:
  KleinBuilderPane splits builder left / RoomAssistPane right.
"""
from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog
from typing import Callable, Optional

# ── KleinBOTTLE project root ──────────────────────────────────────────
_KB_ROOT = Path(__file__).resolve().parent.parent
_KB_SRC  = str(_KB_ROOT)
if _KB_SRC not in sys.path:
    sys.path.insert(0, _KB_SRC)

from kleinos.world_library import (  # noqa: E402
    MAIN_WORLD, WIP_WORLD,
    ensure_wip, list_library, promote_to_main, save_snapshot,
)
from kleinos.palette import (  # noqa: E402
    BG as _BG, BORDER as _BORDER, FG_ON as _FG, FG_DIM as _DIM,
    HEAD as _HDR_BG, FG_PROMPT as _BRIGHT, FG_HUD as _WARN,
)


def _ensure_path() -> None:
    if _KB_SRC not in sys.path:
        sys.path.insert(0, _KB_SRC)


def _apply_green_theme(root: tk.Misc) -> None:
    """Activate green phosphor palette via the ui_theme Palette protocol, then
    apply full ttk styles.  Replaces the former _patch_ui_theme monkey-patch."""
    _ensure_path()
    from kleinos import klein_theme as _kt
    from src.ui_theme import Palette, activate as _activate_ui  # type: ignore[import]
    _activate_ui(Palette(
        background=_kt.BG,  inset=_kt.INSET,  surface=_kt.SURFACE,
        accent=_kt.ACCENT,  text=_kt.TEXT,    muted=_kt.MUTED,
        font_heading=_kt.FONT_HEADING,         font_story=_kt.FONT_STORY,
    ))
    _kt.apply(root)


# ── Lazy imports ──────────────────────────────────────────────────────

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


# ── KleinBuilderPane (Tasks 1 + 4) ───────────────────────────────────

class KleinBuilderPane(tk.Frame):
    """
    Hosts BuilderSurface (left) + RoomAssistPane (right) inside a
    green-themed frame.  World Builder edits WIP only.
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        world_path: Path = WIP_WORLD,
        on_exit: Optional[Callable] = None,
    ):
        super().__init__(parent, bg=_BG, bd=0, highlightthickness=0)
        self._on_exit = on_exit
        try:
            ensure_wip()
            _apply_green_theme(self)
            BuilderSurface, WorldBuilder, WorldStore = _import_builder()
            builder = WorldBuilder(WorldStore(world_path))

            # ── Top action bar (Save Snapshot) ────────────────────────
            bar = tk.Frame(self, bg=_HDR_BG)
            bar.pack(fill="x")
            tk.Label(bar, text=" WORLD BUILDER — WIP ", bg=_HDR_BG, fg=_FG,
                     font=("Consolas", 9, "bold")).pack(side="left", padx=8, pady=5)
            tk.Button(
                bar, text="Save Snapshot…",
                bg=_HDR_BG, fg=_DIM,
                activebackground=_BG, activeforeground=_FG,
                relief="flat", font=("Consolas", 8), cursor="hand2",
                command=self._save_snapshot,
            ).pack(side="right", padx=6)

            # ── Split: builder left, assistant right ──────────────────
            paned = tk.PanedWindow(self, orient="horizontal",
                                   bg=_BORDER, sashwidth=4,
                                   sashrelief="flat", handlesize=0)
            paned.pack(fill="both", expand=True)

            left  = tk.Frame(paned, bg=_BG)
            right = tk.Frame(paned, bg=_BG)
            paned.add(left,  minsize=380)
            paned.add(right, minsize=260)

            surface = BuilderSurface(left, builder)
            surface.pack(fill="both", expand=True)

            from kleinos.room_assist import RoomAssistPane
            assist = RoomAssistPane(
                right,
                get_snapshot=surface.get_form_snapshot,
                apply_updates=surface.apply_ai_updates,
                area_rooms=surface.area_rooms,
                all_rooms=surface.all_rooms,
            )
            assist.pack(fill="both", expand=True)

            # Wire room-switch reset + AI field generation
            surface.on_room_changed      = assist.reset_chat
            surface.generate_btn_callback = assist.generate_field
            surface.generate_all_callback = assist.generate_all_fields

        except Exception as exc:
            self._error(str(exc))

    def _save_snapshot(self) -> None:
        name = simpledialog.askstring(
            "Save Snapshot",
            "Name for this snapshot:",
            parent=self,
        )
        if not name or not name.strip():
            return
        try:
            dest = save_snapshot(name.strip(), source=WIP_WORLD)
            messagebox.showinfo(
                "Snapshot saved",
                f"Saved to:\n{dest.name}",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror("Snapshot failed", str(exc), parent=self)

    def _error(self, msg: str) -> None:
        tk.Label(
            self, text=f"World Builder unavailable:\n{msg}",
            bg=_BG, fg=_FG, font=("Consolas", 9),
            justify="left", wraplength=400,
        ).pack(padx=16, pady=16, anchor="nw")


# ── KleinAdventurePane ────────────────────────────────────────────────

class KleinAdventurePane(tk.Frame):
    """
    Hosts GameSurface inside a green-themed tk.Frame.
    world_path defaults to Main (data/world.json).
    Never modifies the source world (GameSession deepcopies on load).
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        world_path: Path = MAIN_WORLD,
        on_exit: Optional[Callable] = None,
    ):
        super().__init__(parent, bg=_BG, bd=0, highlightthickness=0)
        self._on_exit = on_exit
        self._session = None
        self._surface = None
        self._last_room_id: Optional[str] = None
        self._poll_id: Optional[str] = None
        self.bind("<Destroy>", self._on_destroy)
        try:
            _apply_green_theme(self)
            GameSurface, GameSession, WorldStore = _import_game()
            session = GameSession(WorldStore(world_path))
            self._session = session

            from kleinos.room_panel import RoomImagePanel

            surface = GameSurface(self, session)
            surface.pack(fill="both", expand=True)
            self._surface = surface

            left   = surface._main_col     # type: ignore[attr-defined]
            anchor = surface._story_frame  # type: ignore[attr-defined]

            self._room_panel = RoomImagePanel(left)
            self._room_panel.pack(fill="x", before=anchor)

            self._poll_room()
        except Exception as exc:
            self._error(str(exc))

    def set_computer_callback(self, cb: Callable) -> None:
        if self._surface is not None:
            self._surface.set_computer_callback(cb)  # type: ignore[attr-defined]

    def _on_destroy(self, _event: tk.Event) -> None:
        if self._poll_id is not None:
            self.after_cancel(self._poll_id)
            self._poll_id = None

    def _poll_room(self) -> None:
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
        except Exception as exc:
            import sys
            print(f"[kb_surfaces] _poll_room error: {exc}", file=sys.stderr)
        self._poll_id = self.after(400, self._poll_room)

    def _error(self, msg: str) -> None:
        tk.Label(
            self, text=f"Text Adventure unavailable:\n{msg}",
            bg=_BG, fg=_FG, font=("Consolas", 9),
            justify="left", wraplength=400,
        ).pack(padx=16, pady=16, anchor="nw")


# ── World select screen (Task 2 + 3) ─────────────────────────────────

class _WorldSelectScreen(tk.Frame):
    """
    Scrollable list of worlds to play:  Main, Test WIP, library snapshots.
    Each entry has a Play button; non-Main entries also have Promote.
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_select: Callable[[Path], None],
        on_exit: Optional[Callable] = None,
    ):
        super().__init__(parent, bg=_BG)
        self._on_select = on_select
        self._on_exit   = on_exit
        self._build()

    def _build(self) -> None:
        # Header
        hdr = tk.Frame(self, bg=_HDR_BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text="  SELECT WORLD ", bg=_HDR_BG, fg=_FG,
                 font=("Consolas", 11, "bold")).pack(side="left", padx=10, pady=8)
        if self._on_exit:
            tk.Button(hdr, text="✕", bg=_HDR_BG, fg=_DIM,
                      activebackground=_BG, activeforeground=_FG,
                      relief="flat", font=("Consolas", 10), cursor="hand2",
                      command=self._on_exit).pack(side="right", padx=8)

        # Scrollable body
        canvas = tk.Canvas(self, bg=_BG, highlightthickness=0)
        sb = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=_BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _scroll(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")

        canvas.bind("<MouseWheel>", _scroll)
        inner.bind("<MouseWheel>", _scroll)

        def _resize(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(win_id, width=event.width)

        inner.bind("<Configure>", _resize)
        canvas.bind("<Configure>", _resize)

        self._populate(inner)

    def _populate(self, inner: tk.Frame) -> None:
        self._add_section(inner, "MAIN WORLD")
        if MAIN_WORLD.exists():
            self._add_row(inner, MAIN_WORLD, is_main=True)
        else:
            tk.Label(inner, text="  (no world.json yet)", bg=_BG, fg=_DIM,
                     font=("Consolas", 9)).pack(anchor="w", padx=16, pady=4)

        self._add_section(inner, "TEST WIP")
        if WIP_WORLD.exists():
            self._add_row(inner, WIP_WORLD, is_main=False, label="Test WIP")
        else:
            tk.Label(inner, text="  (no WIP yet — open World Builder first)",
                     bg=_BG, fg=_DIM, font=("Consolas", 9)).pack(anchor="w", padx=16, pady=4)

        library = list_library()
        if library:
            self._add_section(inner, "LIBRARY SNAPSHOTS")
            for entry in library:
                self._add_row(inner, entry["path"], is_main=False,
                              label=entry["name"])

    def _add_section(self, parent: tk.Frame, title: str) -> None:
        tk.Frame(parent, bg=_BORDER, height=1).pack(fill="x", padx=8, pady=(10, 2))
        tk.Label(parent, text=f"  {title}", bg=_BG, fg=_DIM,
                 font=("Consolas", 8, "bold")).pack(anchor="w", padx=8)

    def _add_row(self, parent: tk.Frame, path: Path, *,
                 is_main: bool, label: str = "") -> None:
        row = tk.Frame(parent, bg=_BG)
        row.pack(fill="x", padx=8, pady=2)
        try:
            world_name = json.loads(path.read_text(encoding="utf-8")).get("name") or label or path.stem
        except Exception:
            world_name = label or path.stem

        tk.Label(row, text=f"  {world_name}",
                 bg=_BG, fg=_FG, font=("Consolas", 9),
                 anchor="w").pack(side="left", fill="x", expand=True)

        if not is_main:
            tk.Button(
                row, text="Promote to Main",
                bg=_BG, fg=_WARN,
                activebackground=_HDR_BG, activeforeground=_FG,
                relief="flat", font=("Consolas", 8), cursor="hand2",
                command=lambda p=path: self._promote(p),
            ).pack(side="right", padx=(0, 4))

        tk.Button(
            row, text="▶ Play",
            bg=_BG, fg=_BRIGHT,
            activebackground=_HDR_BG, activeforeground=_FG,
            relief="flat", font=("Consolas", 8, "bold"), cursor="hand2",
            command=lambda p=path: self._on_select(p),
        ).pack(side="right", padx=(0, 4))

    def _promote(self, path: Path) -> None:
        try:
            promote_to_main(path)
            messagebox.showinfo(
                "Promoted",
                "World promoted to Main.\n"
                "The previous Main was saved to the library as a backup.",
                parent=self,
            )
            # Refresh the list
            for w in self.winfo_children():
                w.destroy()
            self._build()
        except Exception as exc:
            messagebox.showerror("Cannot promote", str(exc), parent=self)


# ── Title screen for in-PC game ───────────────────────────────────────

class _KleinBOTTLETitleScreen(tk.Canvas):
    from kleinos.palette import (  # noqa: E402
        BG as _BG, FG_PROMPT as _BRIGHT, FG_HUD as _MID, GM_DARK as _DIM
    )

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
        pane = KleinAdventurePane(self._parent, world_path=self._world_path,
                                  on_exit=self._on_exit)
        pane.pack(fill="both", expand=True)


# ── KleinChat registrations ───────────────────────────────────────────

from kleinos.klein_app import KleinChat  # noqa: E402


class WorldBuilder(KleinChat):
    title = "World Builder"
    description = "Design and edit rooms, items, and connections for the game world."

    def __init__(self, world_path: Path = WIP_WORLD):
        self._world_path = world_path

    def create(self, parent: tk.Widget, on_exit: Callable) -> tk.Widget:
        return KleinBuilderPane(parent, world_path=self._world_path, on_exit=on_exit)


class TextAdventure(KleinChat):
    title = "KleinBOTTLE"
    description = "Play the KleinBOTTLE text adventure."

    def __init__(self, world_path: Optional[Path] = None):
        self._world_path = world_path  # None means show world selector

    def create(self, parent: tk.Widget, on_exit: Callable) -> tk.Widget:
        if self._world_path is not None:
            return _KleinBOTTLETitleScreen(parent, world_path=self._world_path,
                                           on_exit=on_exit)
        return _WorldSelectScreen(
            parent,
            on_select=lambda path, p=parent, e=on_exit: self._launch(p, path, e),
            on_exit=on_exit,
        )

    def _launch(self, parent: tk.Widget, world_path: Path,
                on_exit: Callable) -> None:
        for w in parent.winfo_children():
            w.destroy()
        screen = _KleinBOTTLETitleScreen(parent, world_path=world_path,
                                          on_exit=on_exit)
        screen.pack(fill="both", expand=True)
