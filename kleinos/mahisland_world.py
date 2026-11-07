"""
kleinos/mahisland_world.py

MAHisLAND — module-level constants, audio, shape primitives, world generation.
Imported by mahisland.py and all mixin modules.
"""

from __future__ import annotations

import math
import random
import threading
import tkinter as tk
from pathlib import Path

from kleinos.palette import (
    GM_DARK as _DARK, GM_MID as _MID, GM_BRIGHT as _BRIGHT, FG_HUD as _HUD,
    BORDER as _BORDER, CHROME as _CHROME, FG_DIM as _DIM,
)

# ── Save path ─────────────────────────────────────────────────────────
_SAVE_PATH = Path(__file__).resolve().parent.parent / "data" / "mahisland_save.json"

# ── Audio ─────────────────────────────────────────────────────────────
_SFX: dict[str, list[tuple[int, int]]] = {
    "swing":     [(380, 40)],
    "hit_mob":   [(650, 55)],
    "hit_node":  [(220, 55)],
    "damage":    [(160, 90)],
    "eat":       [(880, 70)],
    "place":     [(480, 60)],
    "mob_die":   [(720, 40)],
    "craft":     [(660, 55), (880, 80)],
    "death":     [(350, 90), (260, 90), (180, 130)],
    "aim_click": [(700, 12)],
}

def _sfx(name: str) -> None:
    tones = _SFX.get(name)
    if not tones:
        return
    def _play() -> None:
        try:
            import winsound
            for freq, ms in tones:
                winsound.Beep(freq, ms)
        except Exception:  # SAFE: winsound can fail (non-Windows, device busy)
            pass
    threading.Thread(target=_play, daemon=True).start()


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
SWING_CD        = 0.35       # seconds between swings
SWING_FLASH_TTL = 0.07       # swing animation duration (seconds)
SWING_DMG  = 10         # unarmed / basic
SWING_RANGE = TILE * 2.2

# 8-way direction snap (radians): E, SE, S, SW, W, NW, N, NE
_SNAP_ANGLES = [k * math.pi / 4 for k in range(-4, 4)]

# Player base stats
P_SPEED = 250           # px/s
P_HP_MAX = 100
P_HN_MAX = 100

# Survival ticks
HUNGER_DRAIN = 1.0      # per second
FOOD_RESTORE_HN = 25
FOOD_RESTORE_HP = 15

# ── Structures ────────────────────────────────────────────────────────
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

# Scoring
SCORE_PER_SEC = 2
SCORE_CRITTER = 5
SCORE_RAIDER  = 15
SCORE_STRUCT  = 10
SCORE_CRAFT   = 20

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
