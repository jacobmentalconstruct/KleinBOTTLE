"""
kleinos/mahisland.py

MAHisLAND — survival / territory game for KleinOS.

Controls:  WASD move  |  Mouse aim  |  LClick swing/place  |  RClick/E interact
           I inventory  |  1-9 hotbar  |  ESC exit
"""

from __future__ import annotations

import math
import time
import tkinter as tk
from typing import Callable, Optional

from kleinos.klein_app import KleinGame
from kleinos.palette import (
    BG as _BG,
    GM_DARK as _DARK, GM_MID as _MID, GM_BRIGHT as _BRIGHT, FG_HUD as _HUD,
    BORDER as _BORDER, CHROME as _CHROME, FG_DIM as _DIM,
)
from kleinos.mahisland_world import (
    TILE, W_TILES, H_TILES,
    P_HP_MAX, P_HN_MAX,
    SWING_RANGE, SWING_FLASH_TTL,
    MOB_SIGHT,
    HEARTH_RADIUS,
    _SAVE_PATH,
    _TC, _TC_BORDER, _NODE_COLOR,
    _SHAPES, _shape_player,
    _BUILD_HOTBAR, _STRUCTURES, _GEAR_RECIPES, _STRUCT_COLOR,
    _gen_world,
)
from kleinos.mahisland_persist import _PersistMixin
from kleinos.mahisland_ai import _AIMixin
from kleinos.mahisland_physics import _PhysicsMixin


# =====================================================================
# Game canvas
# =====================================================================

class MAHisLANDPane(tk.Canvas, _PhysicsMixin, _AIMixin, _PersistMixin):

    def __init__(self, parent: tk.Widget, *, on_exit: Optional[Callable] = None):
        super().__init__(parent, bg=_BG, highlightthickness=0)
        self._on_exit = on_exit

        # Viewport size — read after layout
        self.update_idletasks()
        self._vw = self.winfo_width()  or 540
        self._vh = self.winfo_height() or 408
        self.bind("<Configure>", self._on_resize)

        # Scale-derived tile size and physics constants (future: set from scale param)
        self._tile: int = TILE
        self._swing_range: float = SWING_RANGE
        self._mob_sight: float = MOB_SIGHT

        # Input (persists across resets)
        self._keys: set[str] = set()
        self._mx = 0.0
        self._my = 0.0
        self._last_t: Optional[float] = None

        self._reset_world()
        self._state = "start"           # always open to start screen
        self._high_score = self._load_high_score()
        self._has_save   = _SAVE_PATH.exists()

        # Bindings
        self.bind("<KeyPress>",   lambda e: self._keys.add(e.keysym.lower()))
        self.bind("<KeyRelease>", lambda e: self._keys.discard(e.keysym.lower()))
        self.bind("<Motion>",     self._on_mouse)
        self.bind("<Button-1>",   self._on_lclick)
        self.bind("<Button-3>",   self._on_rclick)
        self.bind("<Escape>",     self._on_escape)
        self.bind("<MouseWheel>", self._on_scroll)
        self.bind("<Enter>",      lambda e: self.focus_set())
        self.focus_set()

        self._tick_id: Optional[str] = None
        self._loop()

    # ── World reset (new game / respawn) ─────────────────────────────

    def _reset_world(self) -> None:
        self._grid, self._nodes = _gen_world()
        cx = (W_TILES // 2) * self._tile + self._tile // 2
        cy = (H_TILES // 2) * self._tile + self._tile // 2
        self._px = float(cx)
        self._py = float(cy)
        self._angle = 0.0
        self._prev_snap = 0.0
        self._camx = self._px - getattr(self, "_vw", 540) / 2
        self._camy = self._py - getattr(self, "_vh", 408) / 2
        self._hp = float(P_HP_MAX)
        self._hunger = float(P_HN_MAX)
        self._inv: dict[str, int] = {
            "wood": 0, "stone": 0, "metal": 0, "food": 0, "leather": 0
        }
        self._gear: set[str] = set()
        self._structs: list[dict] = []
        self._hotbar_sel = 0
        self._swing_cd = 0.0
        self._swing_flash: Optional[tuple[float, float, float, float, float]] = None
        self._inv_open = False
        self._build_menu_open = False
        self._build_sel: Optional[str] = None   # blueprint queued for placement
        self._mobs: list[dict] = []
        self._spawn_acc = 0.0
        self._fuel_acc = 0.0
        self._hunger_acc = 0.0
        self._score = 0
        self._score_acc = 0.0
        self._state = "play"
        self._msg = ""
        self._msg_ttl = 0.0

    # ── Resize ───────────────────────────────────────────────────────

    def _on_resize(self, event: tk.Event) -> None:
        self._vw = event.width
        self._vh = event.height

    # ── Loop ─────────────────────────────────────────────────────────

    def _loop(self) -> None:
        now = time.monotonic()
        dt = min(now - self._last_t, 0.1) if self._last_t else 0.016
        self._last_t = now
        self._update(dt)
        self._draw()
        self._tick_id = self.after(16, self._loop)

    def _do_exit(self) -> None:
        if self._tick_id:
            self.after_cancel(self._tick_id)
            self._tick_id = None
        if self._on_exit:
            self._on_exit()

    # ── Input ────────────────────────────────────────────────────────

    def _on_mouse(self, event: tk.Event) -> None:
        self._mx = event.x + self._camx
        self._my = event.y + self._camy

    def _on_escape(self, _event: tk.Event) -> None:
        if self._state == "start":
            self._do_exit()
        elif self._state in ("dead",):
            self._do_exit()
        elif self._state == "confirm_exit":
            self._state = "play"
        elif self._state == "play":
            if self._build_menu_open:
                self._build_menu_open = False
            elif self._inv_open:
                self._inv_open = False
            else:
                self._state = "confirm_exit"

    def _on_scroll(self, event: tk.Event) -> None:
        # Scroll hotbar selection
        if event.delta > 0:
            self._hotbar_sel = (self._hotbar_sel - 1) % 9
        else:
            self._hotbar_sel = (self._hotbar_sel + 1) % 9

    def _on_lclick(self, event: tk.Event) -> None:
        self.focus_set()
        if self._inv_open:
            self._handle_inv_click(event.x, event.y)
            return
        if self._build_menu_open:
            self._handle_build_click(event.x, event.y)
            return
        if self._hotbar_sel == 1:  # HAMMER — place queued blueprint
            if self._build_sel:
                self._do_place(self._build_sel)
                self._build_sel = None
            else:
                self._flash_msg("[R] open build menu to select a blueprint")
        else:  # FIST — swing / attack / harvest
            self._do_swing()

    def _on_rclick(self, _event: tk.Event) -> None:
        if self._build_menu_open:
            self._build_menu_open = False
            return
        # RMB = use/interact with nearest structure
        self._do_interact()

    # ── HUD helpers ──────────────────────────────────────────────────

    def _flash_msg(self, text: str) -> None:
        self._msg = text
        self._msg_ttl = 2.5

    def _inv_drawer_pos(self) -> tuple[int, int]:
        return (self._vw // 2 - 100, self._vh // 2 - 90)

    # ── Draw ─────────────────────────────────────────────────────────

    def _draw(self) -> None:
        self.delete("all")
        if self._state == "start":
            self._draw_start_screen()
            return
        self._draw_world()
        self._draw_player()
        self._draw_hud()
        if self._build_menu_open:
            self._draw_build_menu()
        if self._inv_open:
            self._draw_inventory()
        if self._state == "dead":
            self._draw_dead()
        elif self._state == "confirm_exit":
            self._draw_confirm_exit()

    def _draw_world(self) -> None:
        # Visible self._tile range
        tx0 = max(0, int(self._camx // self._tile))
        ty0 = max(0, int(self._camy // self._tile))
        tx1 = min(W_TILES, tx0 + self._vw // self._tile + 2)
        ty1 = min(H_TILES, ty0 + self._vh // self._tile + 2)

        for ty in range(ty0, ty1):
            for tx in range(tx0, tx1):
                ter = self._grid[ty][tx]
                sx = tx * self._tile - self._camx
                sy = ty * self._tile - self._camy
                cl = self._claimed(tx, ty)
                bg = _TC[ter]
                if cl:
                    # Slightly brighten claimed tiles
                    bg = _TC_BORDER[ter]
                self.create_rectangle(sx, sy, sx + self._tile - 1, sy + self._tile - 1,
                                      fill=bg, outline="")

        # Claim zone border — bright edge on claimed tiles that border unclaimed
        for s in self._structs:
            if s["kind"] != "hearth" or not s.get("claimed"):
                continue
            hx, hy = s["tx"], s["ty"]
            for ty in range(max(1, hy - HEARTH_RADIUS - 1),
                            min(H_TILES - 1, hy + HEARTH_RADIUS + 2)):
                for tx in range(max(1, hx - HEARTH_RADIUS - 1),
                                min(W_TILES - 1, hx + HEARTH_RADIUS + 2)):
                    if not self._in_claim(tx, ty, s):
                        continue
                    # Only draw edge tiles (at least one neighbour unclaimed)
                    is_edge = any(
                        not self._in_claim(tx + ox, ty + oy, s)
                        for ox, oy in ((1,0),(-1,0),(0,1),(0,-1))
                    )
                    if not is_edge:
                        continue
                    ex = tx * self._tile - self._camx
                    ey = ty * self._tile - self._camy
                    if -self._tile < ex < self._vw + self._tile and -self._tile < ey < self._vh + self._tile:
                        self.create_rectangle(ex, ey, ex + self._tile - 1, ey + self._tile - 1,
                                              outline=_MID, fill="", width=1)

        # Nodes
        for node in self._nodes:
            if node["hp"] <= 0:
                continue
            sx = node["tx"] * self._tile - self._camx
            sy = node["ty"] * self._tile - self._camy
            if -self._tile < sx < self._vw + self._tile and -self._tile < sy < self._vh + self._tile:
                col = _NODE_COLOR[node["kind"]]
                hp_frac = node["hp"] / node["max_hp"]
                size = self._tile * (0.85 + 0.15 * hp_frac)
                draw = _SHAPES.get(node["kind"])
                if draw:
                    draw(self, sx + self._tile/2, sy + self._tile/2, size, col)  # type: ignore[call-arg]

        # Structures
        for s in self._structs:
            sx = s["tx"] * self._tile - self._camx
            sy = s["ty"] * self._tile - self._camy
            if -self._tile < sx < self._vw + self._tile and -self._tile < sy < self._vh + self._tile:
                col = _STRUCT_COLOR.get(s["kind"], _MID)
                hp_frac = s["hp"] / s["max_hp"]
                pad = int(self._tile * 0.1 + self._tile * 0.15 * (1 - hp_frac))
                if s["kind"] == "gate" and s.get("open", False):
                    self.create_rectangle(sx + pad, sy + pad,
                                          sx + self._tile - pad - 1, sy + self._tile - pad - 1,
                                          fill="", outline=col, width=2)
                else:
                    self.create_rectangle(sx + pad, sy + pad,
                                          sx + self._tile - pad - 1, sy + self._tile - pad - 1,
                                          fill=col, outline=_BORDER if s["kind"] == "hearth" else "")
                if s["kind"] == "hearth":
                    fuel = s.get("fuel", 0)
                    self.create_text(sx + self._tile // 2, sy + self._tile // 2,
                                     text=str(fuel), fill=_HUD, font=("Consolas", 7))
                elif s["kind"] == "crate":
                    total = sum(s.get("store", {}).values())
                    if total:
                        self.create_text(sx + self._tile // 2, sy + self._tile // 2,
                                         text=str(total), fill=_HUD, font=("Consolas", 7))

        # Mobs
        for mob in self._mobs:
            sx = mob["x"] - self._camx
            sy = mob["y"] - self._camy
            if -self._tile < sx < self._vw + self._tile and -self._tile < sy < self._vh + self._tile:
                col = _MID if mob["kind"] == "critter" else _BRIGHT
                draw = _SHAPES.get(mob["kind"])
                if draw:
                    draw(self, sx, sy, self._tile, col)  # type: ignore[call-arg]
                # HP bar above mob
                bw = int(self._tile * 0.8)
                hp_f = mob["hp"] / mob["max_hp"]
                bar_top = sy - self._tile * 0.55
                self.create_rectangle(sx - bw//2, bar_top - 4,
                                      sx + bw//2, bar_top,
                                      fill=_BG, outline="")
                self.create_rectangle(sx - bw//2, bar_top - 4,
                                      sx - bw//2 + int(bw * hp_f), bar_top,
                                      fill=col, outline="")

        # Swing flash: line from player to tip
        if self._swing_flash:
            ox, oy, ax, ay, ttl = self._swing_flash
            frac = max(0.0, ttl / SWING_FLASH_TTL)
            # interpolate tip towards player as it fades
            tip_x = ox + (ax - ox) * frac
            tip_y = oy + (ay - oy) * frac
            sx_p = ox - self._camx
            sy_p = oy - self._camy
            sx_t = tip_x - self._camx
            sy_t = tip_y - self._camy
            w = max(1, int(3 * frac))
            self.create_line(sx_p, sy_p, sx_t, sy_t, fill=_BRIGHT, width=w)
            r = int(self._tile * 0.25 * frac)
            if r > 0:
                self.create_oval(sx_t - r, sy_t - r, sx_t + r, sy_t + r,
                                 outline=_BRIGHT, fill="", width=1)

    def _draw_player(self) -> None:
        sx = self._px - self._camx
        sy = self._py - self._camy
        col = _BRIGHT if "tunic" in self._gear else _MID
        _shape_player(self, sx, sy, self._tile, col)
        # Direction indicator
        r = self._tile * 0.38
        ex = sx + math.cos(self._angle) * r * 1.7
        ey = sy + math.sin(self._angle) * r * 1.7
        self.create_line(sx, sy, ex, ey, fill=_BRIGHT, width=2)

    def _draw_hud(self) -> None:
        # HP bar
        bw = 100
        self._bar(8, 8, bw, 8, self._hp / P_HP_MAX, _BRIGHT, "HP")
        # Hunger bar
        self._bar(8, 22, bw, 8, self._hunger / P_HN_MAX, _MID, "HN")
        # Claimed indicator
        ptx = int(self._px // self._tile)
        pty = int(self._py // self._tile)
        zone = "CLAIMED" if self._claimed(ptx, pty) else "WILD"
        self.create_text(8, 38, anchor="nw", text=zone, fill=_HUD, font=("Consolas", 7))
        self.create_text(8, 52, anchor="nw",
                         text=f"score {self._score}",
                         fill=_DIM, font=("Consolas", 7))

        # Hotbar — [1] FIST | [2] HAMMER | [3] FOOD (consumable, never selected)
        bsize = 36
        equip_slots = [
            (0, "FIST"),
            (1, "HAMMER"),
        ]
        total_w = (len(equip_slots) + 1) * (bsize + 4)
        hx = self._vw // 2 - total_w // 2
        hy = self._vh - bsize - 8
        for idx, (slot_id, label) in enumerate(equip_slots):
            x = hx + idx * (bsize + 4)
            sel = self._hotbar_sel == slot_id
            # HAMMER: show blueprint name when queued
            disp = (self._build_sel[:6] if self._build_sel else label) if slot_id == 1 else label
            self.create_rectangle(x, hy, x + bsize, hy + bsize,
                                  fill=_CHROME if sel else _BG,
                                  outline=_BRIGHT if sel else _BORDER)
            self.create_text(x + bsize // 2, hy + bsize // 2,
                             text=disp, fill=_BRIGHT if sel else _DIM,
                             font=("Consolas", 6), justify="center")
            self.create_text(x + 3, hy + 3, anchor="nw",
                             text=str(slot_id + 1), fill=_DIM, font=("Consolas", 5))
        # Food slot — consumable style (no selection highlight)
        fx = hx + len(equip_slots) * (bsize + 4)
        food_n = self._inv.get("food", 0)
        self.create_rectangle(fx, hy, fx + bsize, hy + bsize,
                              fill=_BG, outline=_BORDER, dash=(3, 3))
        self.create_text(fx + bsize // 2, hy + bsize // 2,
                         text=f"FOOD\n{food_n}", fill=_MID if food_n else _DIM,
                         font=("Consolas", 6), justify="center")
        self.create_text(fx + 3, hy + 3, anchor="nw",
                         text="3", fill=_DIM, font=("Consolas", 5))

        # Gear indicators
        gear_x = self._vw - 8
        for i, g in enumerate(["gather_tool", "weapon", "tunic"]):
            if g in self._gear:
                label = {"gather_tool": "TOOL", "weapon": "WPN", "tunic": "ARM"}[g]
                self.create_text(gear_x, 8 + i * 12, anchor="ne",
                                 text=label, fill=_BRIGHT, font=("Consolas", 7))

        # Message
        if self._msg_ttl > 0:
            self.create_text(self._vw // 2, 8, anchor="n",
                             text=self._msg, fill=_BRIGHT, font=("Consolas", 9))

        # Controls hint
        self.create_text(self._vw // 2, self._vh - bsize - 20, anchor="s",
                         text="WASD move | 1 fist  2 hammer  3/F eat | LClick use equipped | RClick interact/open | R build menu | I inventory | ESC exit",
                         fill=_DIM, font=("Consolas", 7))

    def _bar(self, x: int, y: int, w: int, h: int, frac: float,
             color: str, label: str) -> None:
        self.create_rectangle(x, y, x + w, y + h, fill=_BG, outline=_BORDER)
        fw = max(0, int(w * frac))
        if fw:
            self.create_rectangle(x, y, x + fw, y + h, fill=color, outline="")
        self.create_text(x + w + 4, y, anchor="nw",
                         text=label, fill=_DIM, font=("Consolas", 7))

    def _draw_build_menu(self) -> None:
        x0, y0 = self._build_menu_pos()
        h = 20 + len(_BUILD_HOTBAR) * 26
        self.create_rectangle(x0, y0, x0 + 200, y0 + h,
                              fill=_BG, outline=_BORDER, width=1)
        self.create_text(x0 + 100, y0 + 8, text="BUILD  [B] close",
                         fill=_BRIGHT, font=("Consolas", 8, "bold"), anchor="n")
        for i, kind in enumerate(_BUILD_HOTBAR):
            recipe, _ = _STRUCTURES[kind]
            by = y0 + 20 + i * 26
            can = all(self._inv.get(r, 0) >= q for r, q in recipe.items())
            col = _BRIGHT if can else _DIM
            sel = self._build_sel == kind
            bg = _CHROME if sel else _BG
            self.create_rectangle(x0 + 4, by, x0 + 196, by + 22,
                                  fill=bg, outline=_BORDER if sel else "")
            cost = " ".join(f"{q}{r[:2]}" for r, q in recipe.items())
            self.create_text(x0 + 10, by + 11, anchor="w",
                             text=f"{kind:<10} {cost}",
                             fill=col, font=("Consolas", 7))

    def _draw_inventory(self) -> None:
        x0, y0 = self._inv_drawer_pos()
        w, h = 200, 220
        self.create_rectangle(x0, y0, x0 + w, y0 + h,
                              fill=_BG, outline=_BORDER, width=1)
        self.create_text(x0 + w // 2, y0 + 8, text="INVENTORY",
                         fill=_BRIGHT, font=("Consolas", 9, "bold"), anchor="n")

        # Resources
        y = y0 + 24
        for res, qty in self._inv.items():
            self.create_text(x0 + 10, y, anchor="nw",
                             text=f"{res:<8} {qty:>4}",
                             fill=_MID, font=("Consolas", 8))
            y += 14

        # Craft buttons
        self.create_text(x0 + 10, y, anchor="nw",
                         text="CRAFT (need Workbench):",
                         fill=_DIM, font=("Consolas", 7))
        y += 16
        for item, recipe in _GEAR_RECIPES.items():
            cost = "  ".join(f"{q}{r[:2]}" for r, q in recipe.items())
            owned = item in self._gear
            col = _DIM if owned else _BRIGHT
            label = f"{'[✓]' if owned else '[ ]'} {item}  ({cost})"
            self.create_rectangle(x0 + 10, y, x0 + 190, y + 20,
                                  fill=_CHROME if not owned else _BG, outline=_BORDER)
            self.create_text(x0 + 14, y + 10, anchor="w",
                             text=label, fill=col, font=("Consolas", 7))
            y += 24

        self.create_text(x0 + w // 2, y0 + h - 8, anchor="s",
                         text="[I] close", fill=_DIM, font=("Consolas", 7))

    def _draw_start_screen(self) -> None:
        cx, cy = self._vw // 2, self._vh // 2
        self.create_text(cx, cy - 90,
                         text="MAHisLAND",
                         fill=_BRIGHT, font=("Consolas", 28, "bold"))
        self.create_text(cx, cy - 58,
                         text="Survive. Build. Claim the land.",
                         fill=_MID, font=("Consolas", 10))
        self.create_text(cx, cy - 28,
                         text=f"High Score:  {self._high_score}",
                         fill=_DIM, font=("Consolas", 9))
        y = cy + 10
        if self._has_save:
            self.create_text(cx, y,
                             text="[C]  Continue",
                             fill=_BRIGHT, font=("Consolas", 12))
            y += 30
        self.create_text(cx, y,
                         text="[N]  New Game",
                         fill=_MID, font=("Consolas", 12))
        self.create_text(cx, cy + 90,
                         text="[ESC]  Exit",
                         fill=_DIM, font=("Consolas", 9))

    def _draw_confirm_exit(self) -> None:
        cx, cy = self._vw // 2, self._vh // 2
        self.create_rectangle(cx - 170, cy - 55, cx + 170, cy + 55,
                              fill=_BG, outline=_BORDER, width=1)
        self.create_text(cx, cy - 28,
                         text="Save and return to menu?",
                         fill=_BRIGHT, font=("Consolas", 10, "bold"))
        self.create_text(cx, cy,
                         text=f"Score so far:  {self._score}",
                         fill=_DIM, font=("Consolas", 8))
        self.create_text(cx, cy + 24,
                         text="[Y] Save & Exit     [N] / [ESC] Stay",
                         fill=_MID, font=("Consolas", 9))

    def _draw_dead(self) -> None:
        cx, cy = self._vw // 2, self._vh // 2
        self.create_rectangle(cx - 150, cy - 70, cx + 150, cy + 70,
                              fill=_BG, outline=_BORDER, width=1)
        self.create_text(cx, cy - 42, text="YOU DIED",
                         fill=_BRIGHT, font=("Consolas", 18, "bold"))
        self.create_text(cx, cy - 10,
                         text=f"Score: {self._score}",
                         fill=_MID, font=("Consolas", 11))
        hi_col = _BRIGHT if self._score >= self._high_score and self._score > 0 else _DIM
        self.create_text(cx, cy + 14,
                         text=f"Best:  {self._high_score}",
                         fill=hi_col, font=("Consolas", 9))
        self.create_text(cx, cy + 44,
                         text="[R] Menu   [ESC] Exit KleinOS",
                         fill=_MID, font=("Consolas", 9))


# =====================================================================
# KleinGame registration
# =====================================================================

class MAHisLAND(KleinGame):
    title       = "MAHisLAND"
    description = "Survive. Build. Claim the land."

    def create(self, parent: tk.Widget, on_exit: Callable) -> tk.Widget:
        pane = MAHisLANDPane(parent, on_exit=on_exit)
        pane.pack(fill="both", expand=True)
        return pane
