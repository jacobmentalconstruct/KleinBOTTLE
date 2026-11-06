"""
kleinos/mahisland.py

MAHisLAND — survival / territory game for KleinOS.

Controls:  WASD move  |  Mouse aim  |  LClick swing/place  |  RClick/E interact
           I inventory  |  1-9 hotbar  |  ESC exit
"""

from __future__ import annotations

import math
import random
import tkinter as tk
from typing import Callable, Optional

from kleinos.klein_app import KleinGame
from kleinos.palette import (
    BG as _BG,
    GM_DARK as _DARK, GM_MID as _MID, GM_BRIGHT as _BRIGHT, FG_HUD as _HUD,
    BORDER as _BORDER, CHROME as _CHROME, FG_DIM as _DIM,
)

# ── World constants ───────────────────────────────────────────────────
TILE      = 20          # px per tile
W_TILES   = 80
H_TILES   = 50

# Terrain ids
T_GRASS  = 0
T_BARREN = 1
T_WATER  = 2
T_WALL   = 3   # impassable perimeter

# Tile colours (palette-mapped monochrome shades)
_TC = {
    T_GRASS:  "#041008",
    T_BARREN: "#080808",
    T_WATER:  "#020812",
    T_WALL:   "#000000",
}
_TC_BORDER = {
    T_GRASS:  "#081a08",
    T_BARREN: "#141414",
    T_WATER:  "#041020",
    T_WALL:   "#000000",
}

# Node types
N_TREE   = "tree"
N_STONE  = "stone"
N_ORE    = "ore"
N_BUSH   = "bush"

_NODE_HP   = {N_TREE: 50, N_STONE: 80,  N_ORE: 120, N_BUSH: 20}
_NODE_DROP = {N_TREE: ("wood",  5), N_STONE: ("stone", 5),
              N_ORE:  ("metal", 3), N_BUSH:  ("food",  3)}
_NODE_RESPAWN = {N_TREE: 30, N_STONE: 45, N_ORE: 90, N_BUSH: 20}  # seconds
_NODE_COLOR   = {N_TREE: _MID, N_STONE: _DIM, N_ORE: _BRIGHT, N_BUSH: _MID}

# Swing constants
SWING_CD   = 1.0        # seconds
SWING_DMG  = 10         # unarmed / basic
SWING_RANGE = TILE * 2.2

# Player base stats
P_SPEED = 250           # px/s
P_HP_MAX = 100
P_HN_MAX = 100

# Survival ticks
HUNGER_DRAIN = 1.0      # per second
FOOD_RESTORE_HN = 25
FOOD_RESTORE_HP = 15

# ── Structures ────────────────────────────────────────────────────────
# (id, label, recipe {res: qty}, hp, fn)
_STRUCTURES = {
    "hearth":   ({"wood": 15, "stone": 10}, 200),
    "path":     ({"stone": 2},               50),
    "wall":     ({"wood": 5,  "stone": 2},  150),
    "gate":     ({"wood": 8,  "leather": 2},120),
    "spike":    ({"wood": 5,  "stone": 3},   80),
    "bench":    ({"wood": 10, "stone": 5},  100),
    "crate":    ({"wood": 12, "leather": 2},100),
}

_STRUCT_COLOR = {
    "hearth": _BRIGHT, "path": _DARK,  "wall": _MID,
    "gate":   _MID,    "spike": _DIM,  "bench": _MID, "crate": _MID,
}

_BUILD_HOTBAR = ["wall", "path", "hearth", "spike", "bench", "crate", "gate"]

# Hearth claim radius (tiles)
HEARTH_RADIUS = 10
# Fuel burn: 1 wood / 5 sec + 1 wood / 5 sec per 10 path tiles
HEARTH_FUEL_TICK = 5.0  # seconds

# Mob constants
MOB_SIGHT      = TILE * 8     # px
MOB_WANDER_SPD = 45           # px/s
MOB_FLEE_SPD   = 155          # critter flee — slower than player (250), catchable
MOB_CHASE_SPD  = 115          # raider chase — easy to outrun in open, dangerous when cornered
MOB_LOST_TIME  = 3.5          # seconds before mob gives up without LOS
MOB_WANDER_DUR = 3.0          # seconds moving
MOB_PAUSE_DUR  = 1.0          # seconds paused
RAIDER_CONTACT_DMG = 10       # per second to player
RAIDER_WALL_DMG    = 8        # per second to wall

MOB_CRITTER_HP = 30
MOB_RAIDER_HP  = 60
MOB_CAP_CRITTER = 15
MOB_CAP_RAIDER  = 10
MOB_SPAWN_INTERVAL = 5.0      # seconds between spawn attempts

# ── Gear ─────────────────────────────────────────────────────────────
_GEAR_RECIPES = {
    "gather_tool": {"wood": 5,  "stone": 5,  "leather": 2},
    "weapon":      {"wood": 5,  "metal": 5,  "leather": 3},
    "tunic":       {"leather": 6},
}


# =====================================================================
# Shape primitives  — (canvas, cx, cy, size, color) -> None
# =====================================================================

def _shape_tree(cv: tk.Canvas, cx: float, cy: float, s: float, col: str) -> None:
    h = s * 0.9
    # Crown: triangle
    pts = [cx, cy - h * 0.55,
           cx - s * 0.45, cy + h * 0.2,
           cx + s * 0.45, cy + h * 0.2]
    cv.create_polygon(pts, fill=col, outline="")
    # Trunk
    tw = s * 0.12
    cv.create_rectangle(cx - tw, cy + h * 0.2, cx + tw, cy + h * 0.5,
                        fill=col, outline="")

def _shape_stone(cv: tk.Canvas, cx: float, cy: float, s: float, col: str) -> None:
    r = s * 0.42
    # Lumpy 7-point polygon, slightly wider than tall
    pts = [
        cx,         cy - r * 0.9,
        cx + r,     cy - r * 0.4,
        cx + r*0.9, cy + r * 0.3,
        cx + r*0.3, cy + r * 0.8,
        cx - r*0.4, cy + r * 0.8,
        cx - r,     cy + r * 0.2,
        cx - r*0.8, cy - r * 0.5,
    ]
    cv.create_polygon(pts, fill=col, outline="")

def _shape_bush(cv: tk.Canvas, cx: float, cy: float, s: float, col: str) -> None:
    r = s * 0.22
    offsets = [(-s*0.22, s*0.1), (s*0.22, s*0.1), (0, -s*0.1)]
    for ox, oy in offsets:
        cv.create_oval(cx+ox-r, cy+oy-r, cx+ox+r, cy+oy+r, fill=col, outline="")

def _shape_ore(cv: tk.Canvas, cx: float, cy: float, s: float, col: str) -> None:
    r = s * 0.4
    # Hexagon
    pts = []
    for i in range(6):
        a = math.pi / 6 + i * math.pi / 3
        pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    cv.create_polygon(pts, fill=col, outline="")

def _shape_critter(cv: tk.Canvas, cx: float, cy: float, s: float, col: str) -> None:
    r = s * 0.28
    # Oval body
    cv.create_oval(cx - r*1.4, cy - r, cx + r*1.4, cy + r, fill=col, outline="")
    # Ear nubs
    cv.create_oval(cx - r*1.1, cy - r*1.5, cx - r*0.5, cy - r*0.9, fill=col, outline="")
    cv.create_oval(cx + r*0.5,  cy - r*1.5, cx + r*1.1,  cy - r*0.9, fill=col, outline="")

def _shape_raider(cv: tk.Canvas, cx: float, cy: float, s: float, col: str) -> None:
    r = s * 0.42
    # Diamond body
    pts = [cx, cy - r, cx + r*0.7, cy, cx, cy + r, cx - r*0.7, cy]
    cv.create_polygon(pts, fill=col, outline="")
    # Horn lines
    cv.create_line(cx - r*0.2, cy - r, cx - r*0.4, cy - r*1.4, fill=col, width=2)
    cv.create_line(cx + r*0.2, cy - r, cx + r*0.4, cy - r*1.4, fill=col, width=2)

def _shape_player(cv: tk.Canvas, cx: float, cy: float, s: float, col: str) -> None:
    r = s * 0.38
    cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=col, outline="")


_SHAPES: dict[str, object] = {
    N_TREE:    _shape_tree,
    N_STONE:   _shape_stone,
    N_ORE:     _shape_ore,
    N_BUSH:    _shape_bush,
    "critter": _shape_critter,
    "raider":  _shape_raider,
    "player":  _shape_player,
}


# =====================================================================
# World generation
# =====================================================================

def _gen_world() -> tuple[list[list[int]], list[dict]]:
    """Return (tile_grid, node_list)."""
    grid: list[list[int]] = []
    for ty in range(H_TILES):
        row = []
        for tx in range(W_TILES):
            if tx == 0 or tx == W_TILES - 1 or ty == 0 or ty == H_TILES - 1:
                row.append(T_WALL)
            else:
                # Simple noise: water patches, barren strips
                v = random.random()
                if v < 0.08:
                    row.append(T_WATER)
                elif v < 0.22:
                    row.append(T_BARREN)
                else:
                    row.append(T_GRASS)
        grid.append(row)

    # Scatter nodes
    nodes: list[dict] = []
    for _ in range(80):
        tx = random.randint(1, W_TILES - 2)
        ty = random.randint(1, H_TILES - 2)
        ter = grid[ty][tx]
        if ter == T_GRASS:
            kind = random.choice([N_TREE, N_TREE, N_BUSH])
        elif ter == T_BARREN:
            kind = random.choice([N_STONE, N_STONE, N_ORE])
        else:
            continue
        nodes.append({
            "tx": tx, "ty": ty, "kind": kind,
            "hp": _NODE_HP[kind], "max_hp": _NODE_HP[kind],
            "respawn": 0.0,  # >0 means dead, counts down
        })

    return grid, nodes


# =====================================================================
# Game canvas
# =====================================================================

class MAHisLANDPane(tk.Canvas):

    def __init__(self, parent: tk.Widget, *, on_exit: Optional[Callable] = None):
        super().__init__(parent, bg=_BG, highlightthickness=0)
        self._on_exit = on_exit

        # Viewport size — read after layout
        self.update_idletasks()
        self._vw = self.winfo_width()  or 540
        self._vh = self.winfo_height() or 408
        self.bind("<Configure>", self._on_resize)

        # Input (persists across resets)
        self._keys: set[str] = set()
        self._mx = 0.0
        self._my = 0.0
        self._last_t: Optional[float] = None

        self._reset_world()

        # Bindings
        self.bind("<KeyPress>",   lambda e: self._keys.add(e.keysym.lower()))
        self.bind("<KeyRelease>", lambda e: self._keys.discard(e.keysym.lower()))
        self.bind("<Motion>",     self._on_mouse)
        self.bind("<Button-1>",   self._on_lclick)
        self.bind("<Button-3>",   self._on_rclick)
        self.bind("<Escape>",     lambda _e: self._do_exit())
        self.bind("<MouseWheel>", self._on_scroll)
        self.focus_set()

        self._tick_id: Optional[str] = None
        self._loop()

    # ── World reset (new game / respawn) ─────────────────────────────

    def _reset_world(self) -> None:
        self._grid, self._nodes = _gen_world()
        cx = (W_TILES // 2) * TILE + TILE // 2
        cy = (H_TILES // 2) * TILE + TILE // 2
        self._px = float(cx)
        self._py = float(cy)
        self._angle = 0.0
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
        self._state = "play"
        self._msg = ""
        self._msg_ttl = 0.0

    # ── Resize ───────────────────────────────────────────────────────

    def _on_resize(self, event: tk.Event) -> None:
        self._vw = event.width
        self._vh = event.height

    # ── Loop ─────────────────────────────────────────────────────────

    def _loop(self) -> None:
        import time
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

    def _on_scroll(self, event: tk.Event) -> None:
        # Scroll hotbar selection
        if event.delta > 0:
            self._hotbar_sel = (self._hotbar_sel - 1) % 9
        else:
            self._hotbar_sel = (self._hotbar_sel + 1) % 9

    def _on_lclick(self, event: tk.Event) -> None:
        if self._inv_open:
            self._handle_inv_click(event.x, event.y)
            return
        if self._build_menu_open:
            self._handle_build_click(event.x, event.y)
            return
        # Slot 1 = FOOD — click eats
        if self._hotbar_sel == 1:
            self._eat_food()
            return
        # Slot 0 = FIST (and default) — swing / attack / harvest
        self._do_swing()

    def _on_rclick(self, _event: tk.Event) -> None:
        if self._build_menu_open:
            self._build_menu_open = False
            return
        if self._build_sel:
            # Place queued blueprint in facing tile
            self._do_place(self._build_sel)
            self._build_sel = None
            return
        # Near a structure → interact; otherwise nothing
        self._do_interact()

    # ── Update ───────────────────────────────────────────────────────

    def _update(self, dt: float) -> None:
        if self._state == "dead":
            if "r" in self._keys:
                self._keys.discard("r")
                self._reset_world()
            return

        k = self._keys

        # Toggle inventory / build menu
        if "i" in k:
            k.discard("i")
            self._inv_open = not self._inv_open
            self._build_menu_open = False
        if "b" in k:
            k.discard("b")
            self._build_menu_open = not self._build_menu_open
            self._inv_open = False

        # Hotbar number keys
        for n in range(1, 10):
            if str(n) in k:
                k.discard(str(n))
                self._hotbar_sel = n - 1

        # Player facing
        dx = self._mx - self._px
        dy = self._my - self._py
        if abs(dx) + abs(dy) > 2:
            self._angle = math.atan2(dy, dx)

        # Movement
        mx = my = 0.0
        spd = P_SPEED
        ter = self._tile_at(self._px, self._py)
        if ter == T_WATER:
            spd *= 0.5

        if "w" in k or "up" in k:    my -= 1
        if "s" in k or "down" in k:  my += 1
        if "a" in k or "left" in k:  mx -= 1
        if "d" in k or "right" in k: mx += 1

        if mx != 0 and my != 0:
            mx *= 0.707
            my *= 0.707

        nx = self._px + mx * spd * dt
        ny = self._py + my * spd * dt

        # Collide with walls/impassable
        if self._passable(nx, self._py):
            self._px = nx
        if self._passable(self._px, ny):
            self._py = ny

        # Camera follows player
        self._camx = self._px - self._vw / 2
        self._camy = self._py - self._vh / 2

        # Swing cooldown
        if self._swing_cd > 0:
            self._swing_cd -= dt
        if self._swing_flash:
            ox, oy, ax, ay, ttl = self._swing_flash
            if ttl > 0:
                self._swing_flash = (ox, oy, ax, ay, ttl - dt)
            else:
                self._swing_flash = None

        # Swing via key (spacebar fallback)
        if "space" in k and self._swing_cd <= 0:
            self._do_swing()

        # Eat food
        if "f" in k:
            k.discard("f")
            self._eat_food()

        # Hunger tick
        self._hunger_acc += dt
        if self._hunger_acc >= 1.0:
            self._hunger_acc -= 1.0
            self._hunger = max(0, self._hunger - HUNGER_DRAIN)
            if self._hunger == 0:
                self._hp = max(0, self._hp - 2)
                if self._hp <= 0:
                    self._state = "dead"

        # Hearth fuel/upkeep tick
        self._fuel_acc += dt
        if self._fuel_acc >= HEARTH_FUEL_TICK:
            self._fuel_acc -= HEARTH_FUEL_TICK
            self._burn_hearths()

        # Mob spawn + update
        self._spawn_acc += dt
        if self._spawn_acc >= MOB_SPAWN_INTERVAL:
            self._spawn_acc -= MOB_SPAWN_INTERVAL
            self._try_spawn_mob()
        self._update_mobs(dt)

        # Node respawn
        for node in self._nodes:
            if node["respawn"] > 0:
                node["respawn"] -= dt
                if node["respawn"] <= 0:
                    node["respawn"] = 0.0
                    node["hp"] = node["max_hp"]

        # Message timeout
        if self._msg_ttl > 0:
            self._msg_ttl -= dt

    def _passable(self, wx: float, wy: float) -> bool:
        r = TILE * 0.35
        for ox, oy in [(-r, -r), (r, -r), (-r, r), (r, r)]:
            t = self._tile_at(wx + ox, wy + oy)
            if t == T_WALL:
                return False
            tx = int((wx + ox) // TILE)
            ty = int((wy + oy) // TILE)
            # Solid structures
            for s in self._structs:
                if s["tx"] == tx and s["ty"] == ty and s["kind"] in ("wall", "spike", "hearth", "bench", "crate"):
                    return False
            # Alive resource nodes
            for node in self._nodes:
                if node["hp"] > 0 and node["tx"] == tx and node["ty"] == ty:
                    return False
        return True

    def _tile_at(self, wx: float, wy: float) -> int:
        tx = int(wx // TILE)
        ty = int(wy // TILE)
        if tx < 0 or ty < 0 or tx >= W_TILES or ty >= H_TILES:
            return T_WALL
        return self._grid[ty][tx]

    # ── Actions ──────────────────────────────────────────────────────

    def _do_swing(self) -> None:
        if self._swing_cd > 0:
            return
        self._swing_cd = SWING_CD
        dmg = 25 if "gather_tool" in self._gear else SWING_DMG

        # Swing visual: line from player to reach point
        ax = self._px + math.cos(self._angle) * SWING_RANGE
        ay = self._py + math.sin(self._angle) * SWING_RANGE
        self._swing_flash = (self._px, self._py, ax, ay, 0.18)

        # Hit detection: node within range AND within ~70° of aim direction
        best_dist = SWING_RANGE + 1
        best_node = None
        for node in self._nodes:
            if node["hp"] <= 0:
                continue
            nx = node["tx"] * TILE + TILE / 2
            ny = node["ty"] * TILE + TILE / 2
            dist = math.hypot(nx - self._px, ny - self._py)
            if dist > SWING_RANGE:
                continue
            node_angle = math.atan2(ny - self._py, nx - self._px)
            diff = abs(math.atan2(math.sin(node_angle - self._angle),
                                  math.cos(node_angle - self._angle)))
            if diff > math.pi * 0.45:   # ~80° arc
                continue
            if dist < best_dist:
                best_dist = dist
                best_node = node

        # Hit mobs in arc (checked before nodes — same unified hitbox)
        combat_dmg = 30 if "weapon" in self._gear else SWING_DMG
        for mob in self._mobs:
            mdist = math.hypot(mob["x"] - self._px, mob["y"] - self._py)
            if mdist > SWING_RANGE:
                continue
            mob_angle = math.atan2(mob["y"] - self._py, mob["x"] - self._px)
            diff = abs(math.atan2(math.sin(mob_angle - self._angle),
                                  math.cos(mob_angle - self._angle)))
            if diff > math.pi * 0.45:
                continue
            mob["hp"] -= combat_dmg
            self._flash_msg(f"Hit {mob['kind']}  {max(0,mob['hp'])}/{mob['max_hp']}")
            return

        if best_node is not None:
            best_node["hp"] -= dmg
            if best_node["hp"] <= 0:
                res, qty = _NODE_DROP[best_node["kind"]]
                if "gather_tool" in self._gear:
                    qty *= 2
                self._inv[res] = self._inv.get(res, 0) + qty
                best_node["respawn"] = float(_NODE_RESPAWN[best_node["kind"]])
                self._flash_msg(f"+{qty} {res}")
            else:
                self._flash_msg(f"{best_node['kind']}  {best_node['hp']}/{best_node['max_hp']}")

    def _do_interact(self) -> None:
        # Find nearby structure to interact with
        for s in self._structs:
            sx = s["tx"] * TILE + TILE / 2
            sy = s["ty"] * TILE + TILE / 2
            if math.hypot(sx - self._px, sy - self._py) < TILE * 2:
                if s["kind"] == "hearth":
                    wood = self._inv.get("wood", 0)
                    if wood > 0:
                        deposit = min(wood, 20)
                        s["fuel"] = s.get("fuel", 0) + deposit
                        self._inv["wood"] -= deposit
                        self._flash_msg(f"Hearth +{deposit} wood (fuel: {s['fuel']})")
                    else:
                        self._flash_msg("No wood to deposit")
                    return
                elif s["kind"] == "crate":
                    # Deposit all carried resources into crate
                    store = s.setdefault("store", {})
                    deposited = []
                    for res in list(self._inv):
                        qty = self._inv.get(res, 0)
                        if qty > 0:
                            store[res] = store.get(res, 0) + qty
                            self._inv[res] = 0
                            deposited.append(f"{qty} {res}")
                    if deposited:
                        self._flash_msg("Stored: " + ", ".join(deposited))
                    else:
                        # Withdraw everything from crate
                        withdrawn = []
                        for res, qty in list(store.items()):
                            if qty > 0:
                                self._inv[res] = self._inv.get(res, 0) + qty
                                withdrawn.append(f"{qty} {res}")
                        store.clear()
                        if withdrawn:
                            self._flash_msg("Retrieved: " + ", ".join(withdrawn))
                        else:
                            self._flash_msg("Crate is empty")
                    return

    def _do_place(self, kind: str) -> None:
        # Place at the tile the player is facing
        tx = int((self._px + math.cos(self._angle) * TILE * 1.5) // TILE)
        ty = int((self._py + math.sin(self._angle) * TILE * 1.5) // TILE)

        if tx <= 0 or ty <= 0 or tx >= W_TILES - 1 or ty >= H_TILES - 1:
            self._flash_msg("Can't place there")
            return

        ter = self._grid[ty][tx]
        if ter == T_WALL:
            self._flash_msg("Can't place on wall")
            return
        if kind != "path" and ter == T_WATER:
            self._flash_msg("Only paths go on water")
            return

        # Check occupied
        for s in self._structs:
            if s["tx"] == tx and s["ty"] == ty:
                self._flash_msg("Tile occupied")
                return

        recipe, hp = _STRUCTURES[kind]
        for res, qty in recipe.items():
            if self._inv.get(res, 0) < qty:
                self._flash_msg(f"Need {qty} {res}")
                return

        for res, qty in recipe.items():
            self._inv[res] -= qty

        s = {"tx": tx, "ty": ty, "kind": kind, "hp": hp, "max_hp": hp}
        if kind == "hearth":
            s["fuel"] = 0
            s["claimed"] = False
        self._structs.append(s)
        self._flash_msg(f"Placed {kind}")

    def _do_craft(self, item: str) -> None:
        if item in _GEAR_RECIPES:
            # Need workbench nearby?
            need_bench = True
            for s in self._structs:
                if s["kind"] == "bench":
                    sx = s["tx"] * TILE + TILE / 2
                    sy = s["ty"] * TILE + TILE / 2
                    if math.hypot(sx - self._px, sy - self._py) < TILE * 3:
                        need_bench = False
                        break
            if need_bench:
                self._flash_msg("Need a Workbench nearby")
                return
            recipe = _GEAR_RECIPES[item]
        else:
            return

        for res, qty in recipe.items():
            if self._inv.get(res, 0) < qty:
                self._flash_msg(f"Need {qty} {res} for {item}")
                return
        for res, qty in recipe.items():
            self._inv[res] -= qty
        self._gear.add(item)
        self._flash_msg(f"Crafted {item}!")

    def _handle_build_click(self, cx: int, cy: int) -> None:
        x0, y0 = self._build_menu_pos()
        for i, kind in enumerate(_BUILD_HOTBAR):
            by = y0 + 10 + i * 26
            if x0 + 4 <= cx <= x0 + 196 and by <= cy <= by + 22:
                recipe, _ = _STRUCTURES[kind]
                can_afford = all(self._inv.get(r, 0) >= q for r, q in recipe.items())
                if can_afford:
                    self._build_sel = kind
                    self._build_menu_open = False
                    cost_str = " ".join(f"{q}{r[:2]}" for r, q in recipe.items())
                    self._flash_msg(f"[{kind}] selected — RClick to place  ({cost_str})")
                else:
                    self._flash_msg(f"Can't afford {kind}")
                return

    def _build_menu_pos(self) -> tuple[int, int]:
        return (self._vw - 210, 50)

    def _handle_inv_click(self, cx: int, cy: int) -> None:
        # Gear craft buttons in drawer
        x0, y0 = self._inv_drawer_pos()
        bx = x0 + 10
        for i, (item, _) in enumerate(_GEAR_RECIPES.items()):
            by = y0 + 100 + i * 24
            if bx <= cx <= bx + 160 and by <= cy <= by + 20:
                self._do_craft(item)
                return

    def _burn_hearths(self) -> None:
        for s in self._structs:
            if s["kind"] != "hearth":
                continue
            paths = sum(1 for p in self._structs if p["kind"] == "path"
                        and self._in_claim(p["tx"], p["ty"], s))
            cost = 1 + paths // 10
            if s.get("fuel", 0) >= cost:
                s["fuel"] -= cost
                s["claimed"] = True
            else:
                s["claimed"] = False
                # Decay connected structures
                for st in self._structs:
                    if st["kind"] in ("wall", "gate", "spike") and self._in_claim(st["tx"], st["ty"], s):
                        st["hp"] -= 5
                self._structs = [st for st in self._structs if st["hp"] > 0]

    def _in_claim(self, tx: int, ty: int, hearth: dict) -> bool:
        hx = hearth["tx"]
        hy = hearth["ty"]
        return math.hypot(tx - hx, ty - hy) <= HEARTH_RADIUS

    def _claimed(self, tx: int, ty: int) -> bool:
        for s in self._structs:
            if s["kind"] == "hearth" and s.get("claimed"):
                if self._in_claim(tx, ty, s):
                    return True
        return False

    def _has_los(self, x1: float, y1: float, x2: float, y2: float) -> bool:
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy)
        if dist == 0:
            return True
        steps = max(2, int(dist / (TILE * 0.6)))
        for i in range(1, steps):
            t = i / steps
            cx = int((x1 + dx * t) // TILE)
            cy = int((y1 + dy * t) // TILE)
            if cx < 0 or cy < 0 or cx >= W_TILES or cy >= H_TILES:
                return False
            if self._grid[cy][cx] == T_WALL:
                return False
            for node in self._nodes:
                if node["hp"] > 0 and node["tx"] == cx and node["ty"] == cy:
                    return False
        return True

    def _eat_food(self) -> None:
        if self._inv.get("food", 0) <= 0:
            self._flash_msg("No food")
            return
        self._inv["food"] -= 1
        self._hunger = min(P_HN_MAX, self._hunger + FOOD_RESTORE_HN)
        self._hp     = min(P_HP_MAX, self._hp     + FOOD_RESTORE_HP)
        self._flash_msg(f"Ate food  HP:{int(self._hp)}  HN:{int(self._hunger)}")

    # ── Mob AI ───────────────────────────────────────────────────────

    def _try_spawn_mob(self) -> None:
        critters = sum(1 for m in self._mobs if m["kind"] == "critter")
        raiders  = sum(1 for m in self._mobs if m["kind"] == "raider")
        kind = None
        if critters < MOB_CAP_CRITTER and raiders < MOB_CAP_RAIDER:
            kind = random.choice(["critter", "critter", "raider"])
        elif critters < MOB_CAP_CRITTER:
            kind = "critter"
        elif raiders < MOB_CAP_RAIDER:
            kind = "raider"
        if kind is None:
            return

        # Pick a random unclaimed tile away from player
        for _ in range(30):
            tx = random.randint(1, W_TILES - 2)
            ty = random.randint(1, H_TILES - 2)
            if self._grid[ty][tx] == T_WALL:
                continue
            wx = tx * TILE + TILE / 2
            wy = ty * TILE + TILE / 2
            if math.hypot(wx - self._px, wy - self._py) < TILE * 12:
                continue
            if self._claimed(tx, ty):
                continue
            hp = MOB_CRITTER_HP if kind == "critter" else MOB_RAIDER_HP
            self._mobs.append({
                "kind": kind, "x": wx, "y": wy,
                "hp": hp, "max_hp": hp,
                "state": "wander", "state_t": MOB_WANDER_DUR,
                "vx": 0.0, "vy": 0.0,
                "dmg_cd": 0.0, "lost_t": 0.0,
            })
            return

    def _update_mobs(self, dt: float) -> None:
        dead = []
        for mob in self._mobs:
            self._update_one_mob(mob, dt)
            if mob["hp"] <= 0:
                dead.append(mob)
        for mob in dead:
            self._mobs.remove(mob)
            self._drop_mob(mob)

    def _update_one_mob(self, mob: dict, dt: float) -> None:
        dx = self._px - mob["x"]
        dy = self._py - mob["y"]
        dist = math.hypot(dx, dy)

        can_see = dist < MOB_SIGHT and self._has_los(mob["x"], mob["y"], self._px, self._py)

        if mob["kind"] == "critter":
            if can_see:
                mob["state"] = "flee"
                mob["lost_t"] = MOB_LOST_TIME
            elif mob["state"] == "flee":
                mob["lost_t"] -= dt
                if mob["lost_t"] <= 0:
                    mob["state"] = "wander"
                    mob["state_t"] = MOB_WANDER_DUR
                    mob["vx"] = mob["vy"] = 0.0

            if mob["state"] == "flee":
                if dist > 0:
                    spd = MOB_FLEE_SPD * max(0.3, mob["lost_t"] / MOB_LOST_TIME)
                    mob["vx"] = -(dx / dist) * spd
                    mob["vy"] = -(dy / dist) * spd
            else:
                self._wander_tick(mob, dt)

        else:  # raider
            if can_see:
                mob["state"] = "chase"
                mob["lost_t"] = MOB_LOST_TIME
            elif mob["state"] == "chase":
                mob["lost_t"] -= dt
                if mob["lost_t"] <= 0:
                    mob["state"] = "wander"
                    mob["state_t"] = MOB_WANDER_DUR
                    mob["vx"] = mob["vy"] = 0.0

            if mob["state"] == "chase":
                if dist > 0:
                    mob["vx"] = (dx / dist) * MOB_CHASE_SPD
                    mob["vy"] = (dy / dist) * MOB_CHASE_SPD
            else:
                self._wander_tick(mob, dt)

            # Contact damage to player
            if dist < TILE * 1.2:
                if mob["dmg_cd"] <= 0:
                    dmg = RAIDER_CONTACT_DMG
                    if "tunic" in self._gear:
                        dmg = dmg // 2
                    self._hp = max(0, self._hp - dmg)
                    mob["dmg_cd"] = 1.0
                    if self._hp <= 0:
                        self._state = "dead"
                else:
                    mob["dmg_cd"] -= dt

            # Attack adjacent walls/structures
            for s in self._structs:
                if s["kind"] not in ("wall", "gate", "spike"):
                    continue
                sx = s["tx"] * TILE + TILE / 2
                sy = s["ty"] * TILE + TILE / 2
                if math.hypot(sx - mob["x"], sy - mob["y"]) < TILE * 1.4:
                    s["hp"] -= RAIDER_WALL_DMG * dt
            self._structs = [s for s in self._structs if s["hp"] > 0]

        # Move mob
        nx = mob["x"] + mob["vx"] * dt
        ny = mob["y"] + mob["vy"] * dt
        if self._passable(nx, mob["y"]):
            mob["x"] = nx
        else:
            mob["vx"] *= -1
        if self._passable(mob["x"], ny):
            mob["y"] = ny
        else:
            mob["vy"] *= -1

        # Clamp to world
        mob["x"] = max(TILE, min(mob["x"], (W_TILES - 1) * TILE))
        mob["y"] = max(TILE, min(mob["y"], (H_TILES - 1) * TILE))

    def _wander_tick(self, mob: dict, dt: float) -> None:
        mob["state_t"] -= dt
        if mob["state_t"] <= 0:
            if mob["state"] == "wander":
                mob["state"] = "pause"
                mob["state_t"] = MOB_PAUSE_DUR
                mob["vx"] = mob["vy"] = 0.0
            else:
                mob["state"] = "wander"
                mob["state_t"] = MOB_WANDER_DUR
                angle = random.uniform(0, math.pi * 2)
                mob["vx"] = math.cos(angle) * MOB_WANDER_SPD
                mob["vy"] = math.sin(angle) * MOB_WANDER_SPD

    def _drop_mob(self, mob: dict) -> None:
        if mob["kind"] == "critter":
            self._inv["food"]    = self._inv.get("food",    0) + 2
            self._inv["leather"] = self._inv.get("leather", 0) + 1
            self._flash_msg("+2 food  +1 leather")
        else:
            self._inv["leather"] = self._inv.get("leather", 0) + 2
            self._flash_msg("+2 leather")

    # ── HUD helpers ──────────────────────────────────────────────────

    def _flash_msg(self, text: str) -> None:
        self._msg = text
        self._msg_ttl = 2.5

    def _inv_drawer_pos(self) -> tuple[int, int]:
        return (self._vw // 2 - 100, self._vh // 2 - 90)

    # ── Draw ─────────────────────────────────────────────────────────

    def _draw(self) -> None:
        self.delete("all")
        self._draw_world()
        self._draw_player()
        self._draw_hud()
        if self._build_menu_open:
            self._draw_build_menu()
        if self._inv_open:
            self._draw_inventory()
        if self._state == "dead":
            self._draw_dead()

    def _draw_world(self) -> None:
        # Visible tile range
        tx0 = max(0, int(self._camx // TILE))
        ty0 = max(0, int(self._camy // TILE))
        tx1 = min(W_TILES, tx0 + self._vw // TILE + 2)
        ty1 = min(H_TILES, ty0 + self._vh // TILE + 2)

        for ty in range(ty0, ty1):
            for tx in range(tx0, tx1):
                ter = self._grid[ty][tx]
                sx = tx * TILE - self._camx
                sy = ty * TILE - self._camy
                cl = self._claimed(tx, ty)
                bg = _TC[ter]
                if cl:
                    # Slightly brighten claimed tiles
                    bg = _TC_BORDER[ter]
                self.create_rectangle(sx, sy, sx + TILE - 1, sy + TILE - 1,
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
                    ex = tx * TILE - self._camx
                    ey = ty * TILE - self._camy
                    if -TILE < ex < self._vw + TILE and -TILE < ey < self._vh + TILE:
                        self.create_rectangle(ex, ey, ex + TILE - 1, ey + TILE - 1,
                                              outline=_MID, fill="", width=1)

        # Nodes
        for node in self._nodes:
            if node["hp"] <= 0:
                continue
            sx = node["tx"] * TILE - self._camx
            sy = node["ty"] * TILE - self._camy
            if -TILE < sx < self._vw + TILE and -TILE < sy < self._vh + TILE:
                col = _NODE_COLOR[node["kind"]]
                hp_frac = node["hp"] / node["max_hp"]
                size = TILE * (0.85 + 0.15 * hp_frac)
                draw = _SHAPES.get(node["kind"])
                if draw:
                    draw(self, sx + TILE/2, sy + TILE/2, size, col)  # type: ignore[call-arg]

        # Structures
        for s in self._structs:
            sx = s["tx"] * TILE - self._camx
            sy = s["ty"] * TILE - self._camy
            if -TILE < sx < self._vw + TILE and -TILE < sy < self._vh + TILE:
                col = _STRUCT_COLOR.get(s["kind"], _MID)
                hp_frac = s["hp"] / s["max_hp"]
                pad = int(TILE * 0.1 + TILE * 0.15 * (1 - hp_frac))
                self.create_rectangle(sx + pad, sy + pad,
                                      sx + TILE - pad - 1, sy + TILE - pad - 1,
                                      fill=col, outline=_BORDER if s["kind"] == "hearth" else "")
                if s["kind"] == "hearth":
                    fuel = s.get("fuel", 0)
                    self.create_text(sx + TILE // 2, sy + TILE // 2,
                                     text=str(fuel), fill=_HUD, font=("Consolas", 7))
                elif s["kind"] == "crate":
                    total = sum(s.get("store", {}).values())
                    if total:
                        self.create_text(sx + TILE // 2, sy + TILE // 2,
                                         text=str(total), fill=_HUD, font=("Consolas", 7))

        # Mobs
        for mob in self._mobs:
            sx = mob["x"] - self._camx
            sy = mob["y"] - self._camy
            if -TILE < sx < self._vw + TILE and -TILE < sy < self._vh + TILE:
                col = _MID if mob["kind"] == "critter" else _BRIGHT
                draw = _SHAPES.get(mob["kind"])
                if draw:
                    draw(self, sx, sy, TILE, col)  # type: ignore[call-arg]
                # HP bar above mob
                bw = int(TILE * 0.8)
                hp_f = mob["hp"] / mob["max_hp"]
                bar_top = sy - TILE * 0.55
                self.create_rectangle(sx - bw//2, bar_top - 4,
                                      sx + bw//2, bar_top,
                                      fill=_BG, outline="")
                self.create_rectangle(sx - bw//2, bar_top - 4,
                                      sx - bw//2 + int(bw * hp_f), bar_top,
                                      fill=col, outline="")

        # Swing flash: line from player to tip
        if self._swing_flash:
            ox, oy, ax, ay, ttl = self._swing_flash
            frac = max(0.0, ttl / 0.18)
            # interpolate tip towards player as it fades
            tip_x = ox + (ax - ox) * frac
            tip_y = oy + (ay - oy) * frac
            sx_p = ox - self._camx
            sy_p = oy - self._camy
            sx_t = tip_x - self._camx
            sy_t = tip_y - self._camy
            w = max(1, int(3 * frac))
            self.create_line(sx_p, sy_p, sx_t, sy_t, fill=_BRIGHT, width=w)
            r = int(TILE * 0.25 * frac)
            if r > 0:
                self.create_oval(sx_t - r, sy_t - r, sx_t + r, sy_t + r,
                                 outline=_BRIGHT, fill="", width=1)

    def _draw_player(self) -> None:
        sx = self._px - self._camx
        sy = self._py - self._camy
        col = _BRIGHT if "tunic" in self._gear else _MID
        _shape_player(self, sx, sy, TILE, col)
        # Direction indicator
        r = TILE * 0.38
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
        ptx = int(self._px // TILE)
        pty = int(self._py // TILE)
        zone = "CLAIMED" if self._claimed(ptx, pty) else "WILD"
        self.create_text(8, 38, anchor="nw", text=zone, fill=_HUD, font=("Consolas", 7))

        # Hotbar — fist | food count | build indicator
        bsize = 36
        slots_data = [
            ("FIST",  _BRIGHT),
            (f"EAT [F]\n{self._inv.get('food', 0)} food", _MID),
        ]
        total_w = len(slots_data) * (bsize + 4)
        hx = self._vw // 2 - total_w // 2
        hy = self._vh - bsize - 8
        for i, (label, col) in enumerate(slots_data):
            x = hx + i * (bsize + 4)
            sel = i == self._hotbar_sel
            self.create_rectangle(x, hy, x + bsize, hy + bsize,
                                  fill=_CHROME if sel else _BG,
                                  outline=_BRIGHT if sel else _BORDER)
            self.create_text(x + bsize // 2, hy + bsize // 2,
                             text=label, fill=col if sel else _DIM,
                             font=("Consolas", 6), justify="center")
        # Blueprint indicator
        if self._build_sel:
            bx = hx + len(slots_data) * (bsize + 4) + 8
            self.create_rectangle(bx, hy, bx + 60, hy + bsize,
                                  fill=_CHROME, outline=_BRIGHT)
            self.create_text(bx + 30, hy + bsize // 2,
                             text=self._build_sel[:7], fill=_BRIGHT,
                             font=("Consolas", 6), justify="center")

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
                         text="WASD move | LClick swing | F eat | B build menu | RClick place/interact | I inventory | ESC exit",
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

    def _draw_dead(self) -> None:
        cx, cy = self._vw // 2, self._vh // 2
        self.create_rectangle(cx - 120, cy - 50, cx + 120, cy + 50,
                              fill=_BG, outline=_BORDER, width=1)
        self.create_text(cx, cy - 20, text="YOU DIED",
                         fill=_BRIGHT, font=("Consolas", 18, "bold"))
        self.create_text(cx, cy + 10, text="[R] New world   [ESC] Exit",
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
