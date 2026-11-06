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

# ── Gear ─────────────────────────────────────────────────────────────
_GEAR_RECIPES = {
    "gather_tool": {"wood": 5,  "stone": 5,  "leather": 2},
    "weapon":      {"wood": 5,  "metal": 5,  "leather": 3},
    "tunic":       {"leather": 6},
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

        # World
        self._grid, self._nodes = _gen_world()

        # Player (world px coords)
        cx = (W_TILES // 2) * TILE + TILE // 2
        cy = (H_TILES // 2) * TILE + TILE // 2
        self._px = float(cx)
        self._py = float(cy)
        self._angle = 0.0          # radians, facing direction

        # Camera (top-left world px)
        self._camx = self._px - self._vw / 2
        self._camy = self._py - self._vh / 2

        # Input
        self._keys: set[str] = set()
        self._mx = 0.0   # mouse world x
        self._my = 0.0   # mouse world y

        # Player stats
        self._hp = float(P_HP_MAX)
        self._hunger = float(P_HN_MAX)

        # Inventory {resource: qty}
        self._inv: dict[str, int] = {
            "wood": 0, "stone": 0, "metal": 0, "food": 0, "leather": 0
        }
        # Gear slots
        self._gear: set[str] = set()   # "gather_tool", "weapon", "tunic"

        # Structures placed: list of {tx, ty, kind, hp, max_hp, fuel(hearths)}
        self._structs: list[dict] = []

        # Hotbar: 9 slots, mix of items and build blueprints
        # slot 0 = swing/fist  slots 1-6 = build blueprints  7-8 = consumable
        self._hotbar_sel = 0

        # Swing cooldown
        self._swing_cd = 0.0
        self._swing_flash: Optional[tuple[float, float, float, float, float]] = None  # ox,oy,ax,ay,ttl

        # Inventory drawer open
        self._inv_open = False

        # Hearth fuel/claim tick accumulator
        self._fuel_acc = 0.0

        # Hunger/health tick
        self._hunger_acc = 0.0

        # Node respawn accumulator (uses delta time per node via node["respawn"])

        # State
        self._state = "play"   # play | dead

        # Msg overlay (top-centre status line)
        self._msg = ""
        self._msg_ttl = 0.0

        # Time tracking
        self._last_t: Optional[float] = None

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
        # Inventory drawer: click recipe
        if self._inv_open:
            self._handle_inv_click(event.x, event.y)
            return
        self._do_swing()

    def _on_rclick(self, _event: tk.Event) -> None:
        # Interact: deposit fuel into Hearth, eat food, etc.
        self._do_interact()

    # ── Update ───────────────────────────────────────────────────────

    def _update(self, dt: float) -> None:
        if self._state == "dead":
            return

        k = self._keys

        # Toggle inventory
        if "i" in k:
            k.discard("i")
            self._inv_open = not self._inv_open

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
        # Check 4-corner radius
        r = TILE * 0.35
        for ox, oy in [(-r, -r), (r, -r), (-r, r), (r, r)]:
            t = self._tile_at(wx + ox, wy + oy)
            if t == T_WALL:
                return False
            # Structures that block
            tx = int((wx + ox) // TILE)
            ty = int((wy + oy) // TILE)
            for s in self._structs:
                if s["tx"] == tx and s["ty"] == ty and s["kind"] in ("wall", "spike"):
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
                    self._flash_msg("Crate: storage (coming soon)")
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

        # Nodes
        for node in self._nodes:
            if node["hp"] <= 0:
                continue
            sx = node["tx"] * TILE - self._camx
            sy = node["ty"] * TILE - self._camy
            if -TILE < sx < self._vw + TILE and -TILE < sy < self._vh + TILE:
                col = _NODE_COLOR[node["kind"]]
                hp_frac = node["hp"] / node["max_hp"]
                pad = int(TILE * 0.05 + TILE * 0.1 * (1 - hp_frac))
                self.create_rectangle(sx + pad, sy + pad,
                                      sx + TILE - pad - 1, sy + TILE - pad - 1,
                                      fill=col, outline="")

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
        r = TILE * 0.4
        # Body
        col = _BRIGHT if "tunic" in self._gear else _MID
        self.create_oval(sx - r, sy - r, sx + r, sy + r, fill=col, outline="")
        # Direction indicator
        ex = sx + math.cos(self._angle) * r * 1.6
        ey = sy + math.sin(self._angle) * r * 1.6
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

        # Hotbar (bottom centre)
        slots = ["[fist]"] + [_BUILD_HOTBAR[i] if i < len(_BUILD_HOTBAR) else "---"
                               for i in range(8)]
        bsize = 32
        total = 9 * (bsize + 2)
        hx = self._vw // 2 - total // 2
        hy = self._vh - bsize - 8
        for i, label in enumerate(slots):
            x = hx + i * (bsize + 2)
            sel = i == self._hotbar_sel
            bg = _CHROME if sel else _BG
            self.create_rectangle(x, hy, x + bsize, hy + bsize,
                                  fill=bg, outline=_BRIGHT if sel else _BORDER)
            short = label[:5]
            self.create_text(x + bsize // 2, hy + bsize // 2,
                             text=short, fill=_BRIGHT if sel else _DIM,
                             font=("Consolas", 6))

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
                         text="WASD move | LClick swing | RClick interact | I inventory | ESC exit",
                         fill=_DIM, font=("Consolas", 7))

    def _bar(self, x: int, y: int, w: int, h: int, frac: float,
             color: str, label: str) -> None:
        self.create_rectangle(x, y, x + w, y + h, fill=_BG, outline=_BORDER)
        fw = max(0, int(w * frac))
        if fw:
            self.create_rectangle(x, y, x + fw, y + h, fill=color, outline="")
        self.create_text(x + w + 4, y, anchor="nw",
                         text=label, fill=_DIM, font=("Consolas", 7))

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
        self.create_text(cx, cy + 10, text="[ESC] Exit to KleinOS",
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
