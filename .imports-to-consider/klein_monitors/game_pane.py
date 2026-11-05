"""
klein_monitors/game_pane.py

Space Invaders — green phosphor pixel-art game for KleinOS.

Controls: LEFT/RIGHT move, SPACE fire, ESC exit.
Drawn entirely with tk.Canvas rectangles — no text sprites, smooth animation.
"""

from __future__ import annotations

import random
import tkinter as tk
from typing import Callable, Optional

from klein_monitors.klein_app import KleinGame

# ── Palette ──────────────────────────────────────────────────────────
_BG   = "#010a01"
_G    = "#00dd33"   # main green — player, invaders, bullets
_GH   = "#88ff88"   # highlight — explosions, win text
_GD   = "#004d18"   # dim green — grid lines, controls text
_RED  = "#ff3322"   # invader bombs
_HUD  = "#00aa22"   # score / lives

# ── Pixel scale ───────────────────────────────────────────────────────
_S = 3   # 1 sprite-pixel = _S canvas pixels

# ── Sprite definitions (1=filled, 0=empty, row-major) ────────────────
# 8×6 invader, two variants (animate by alternating)
_INV_A = [
    [0,0,1,0,0,0,1,0],
    [0,0,0,1,1,1,0,0],
    [0,1,1,1,1,1,1,0],
    [1,1,0,1,1,0,1,1],
    [1,1,1,1,1,1,1,1],
    [0,1,0,0,0,0,1,0],
]
_INV_B = [
    [0,0,1,0,0,0,1,0],
    [1,0,0,1,1,0,0,1],
    [1,1,1,1,1,1,1,1],
    [1,1,0,1,1,0,1,1],
    [0,1,1,1,1,1,1,0],
    [0,0,1,0,0,1,0,0],
]

# 8×6 player ship
_PLAYER = [
    [0,0,0,1,1,0,0,0],
    [0,0,1,1,1,1,0,0],
    [0,0,1,1,1,1,0,0],
    [1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1],
]

_SPR_W = 8 * _S    # sprite pixel width  = 24
_SPR_H = 6 * _S    # sprite pixel height = 18


def _draw_sprite(canvas: tk.Canvas, pattern, cx: int, cy: int, color: str) -> None:
    """Draw a pixel-art sprite centred at (cx, cy)."""
    ox = cx - _SPR_W // 2
    oy = cy - _SPR_H // 2
    for r, row in enumerate(pattern):
        for c, px in enumerate(row):
            if px:
                x0 = ox + c * _S
                y0 = oy + r * _S
                canvas.create_rectangle(x0, y0, x0 + _S - 1, y0 + _S - 1,
                                        fill=color, outline="")


# =====================================================================
# Game canvas
# =====================================================================

class SpaceInvadersPane(tk.Canvas):
    # Content area dimensions (matches widescreen rect minus sidebar)
    W: int = 539
    H: int = 408

    COLS: int = 10
    ROWS: int = 4
    H_GAP: int = 44    # horizontal cell size
    V_GAP: int = 36    # vertical cell size

    def __init__(self, parent: tk.Widget, *, on_exit: Optional[Callable] = None):
        super().__init__(
            parent,
            width=self.W, height=self.H,
            bg=_BG, highlightthickness=0,
        )
        self._on_exit = on_exit
        self._reset()
        self.focus_set()
        self.bind("<KeyPress>",   lambda e: self._keys.add(e.keysym))
        self.bind("<KeyRelease>", lambda e: self._keys.discard(e.keysym))
        self.bind("<Escape>",     lambda e: self._quit())
        self._tick_id: Optional[str] = None
        self._loop()

    # ── Setup ────────────────────────────────────────────────────────

    def _reset(self) -> None:
        self._px = self.W // 2       # player x
        self._py = self.H - 36       # player y (fixed)
        self._score = 0
        self._lives = 3
        self._frame = 0              # used to alternate invader sprites

        # Invader grid: list of [col, row, alive]
        self._invaders: list[list] = [
            [c, r, True] for r in range(self.ROWS) for c in range(self.COLS)
        ]
        self._gx = (self.W - self.COLS * self.H_GAP) // 2  # grid left edge
        self._gy = 48                                        # grid top edge
        self._gdx = 1                                        # grid x direction
        self._step_down = False
        self._inv_timer = 0

        self._bullets: list[list[float]] = []   # player bullets [x, y]
        self._bombs: list[list[float]] = []     # invader bombs [x, y]
        self._explosions: list[list] = []       # [x, y, ttl]

        self._fire_cd = 0
        self._keys: set[str] = set()
        self._state = "play"   # play | dead | won

    # ── Main loop ────────────────────────────────────────────────────

    def _loop(self) -> None:
        self._update()
        self._draw()
        self._tick_id = self.after(40, self._loop)   # ~25 fps

    def _quit(self) -> None:
        if self._tick_id:
            self.after_cancel(self._tick_id)
            self._tick_id = None
        if self._on_exit:
            self._on_exit()

    # ── Update ───────────────────────────────────────────────────────

    def _update(self) -> None:
        self._frame += 1
        if self._state != "play":
            return

        # Player movement
        if "Left" in self._keys:
            self._px = max(16, self._px - 5)
        if "Right" in self._keys:
            self._px = min(self.W - 16, self._px + 5)

        # Fire
        if self._fire_cd > 0:
            self._fire_cd -= 1
        if "space" in self._keys and self._fire_cd == 0:
            self._bullets.append([float(self._px), float(self._py - 20)])
            self._fire_cd = 15

        # Move player bullets
        self._bullets = [[x, y - 11] for x, y in self._bullets if y > 0]

        # Move invader bombs
        self._bombs = [[x, y + 5] for x, y in self._bombs if y < self.H]

        # Tick explosions
        self._explosions = [[x, y, t - 1] for x, y, t in self._explosions if t > 1]

        # Move invader grid
        alive = [inv for inv in self._invaders if inv[2]]
        if not alive:
            self._state = "won"
            return

        speed = max(2, 18 - len(alive) // 3)
        self._inv_timer += 1
        if self._inv_timer >= speed:
            self._inv_timer = 0
            if self._step_down:
                self._gy += self.V_GAP // 2
                self._step_down = False
                self._gdx *= -1
            else:
                self._gx += self._gdx * 10
                cols_alive = [inv[0] for inv in alive]
                left  = self._gx + min(cols_alive) * self.H_GAP
                right = self._gx + max(cols_alive) * self.H_GAP + _SPR_W
                if right >= self.W - 4 or left <= 4:
                    self._step_down = True

            # Random invader bomb
            if random.random() < 0.18:
                shooter = random.choice(alive)
                bx = self._gx + shooter[0] * self.H_GAP + self.H_GAP // 2
                by = self._gy + shooter[1] * self.V_GAP + _SPR_H
                self._bombs.append([float(bx), float(by)])

        # Bullet ↔ invader collision
        for bullet in self._bullets[:]:
            bx, by = bullet
            for inv in self._invaders:
                if not inv[2]:
                    continue
                ix = self._gx + inv[0] * self.H_GAP + self.H_GAP // 2
                iy = self._gy + inv[1] * self.V_GAP + self.V_GAP // 2
                if abs(bx - ix) < _SPR_W // 2 and abs(by - iy) < _SPR_H // 2:
                    inv[2] = False
                    if bullet in self._bullets:
                        self._bullets.remove(bullet)
                    self._score += 10
                    self._explosions.append([ix, iy, 8])
                    break

        # Bomb ↔ player collision
        for bomb in self._bombs[:]:
            bx, by = bomb
            if abs(bx - self._px) < 14 and abs(by - self._py) < 14:
                self._bombs.remove(bomb)
                self._lives -= 1
                self._explosions.append([self._px, self._py, 12])
                if self._lives <= 0:
                    self._state = "dead"

        # Invaders reach the player
        for inv in self._invaders:
            if inv[2]:
                iy = self._gy + inv[1] * self.V_GAP + _SPR_H
                if iy >= self._py - 10:
                    self._state = "dead"

    # ── Draw ─────────────────────────────────────────────────────────

    def _draw(self) -> None:
        self.delete("all")

        # Scanline texture (subtle)
        for y in range(0, self.H, 4):
            self.create_line(0, y, self.W, y, fill="#020e02")

        # HUD
        self.create_text(8, 8, anchor="nw",
                         text=f"SCORE  {self._score:05d}",
                         fill=_HUD, font=("Consolas", 9))
        hearts = "▮" * self._lives + "▯" * (3 - self._lives)
        self.create_text(self.W - 8, 8, anchor="ne",
                         text=f"LIVES  {hearts}",
                         fill=_HUD, font=("Consolas", 9))
        self.create_line(0, 24, self.W, 24, fill=_GD)
        self.create_line(0, self.H - 22, self.W, self.H - 22, fill=_GD)

        # Controls
        self.create_text(self.W // 2, self.H - 11, anchor="center",
                         text="[←][→] MOVE    [SPACE] FIRE    [ESC] EXIT",
                         fill=_GD, font=("Consolas", 8))

        # Invaders
        anim = _INV_A if (self._frame // 6) % 2 == 0 else _INV_B
        for inv in self._invaders:
            if not inv[2]:
                continue
            ix = self._gx + inv[0] * self.H_GAP + self.H_GAP // 2
            iy = self._gy + inv[1] * self.V_GAP + self.V_GAP // 2
            _draw_sprite(self, anim, ix, iy, _G)

        # Player bullets
        for bx, by in self._bullets:
            self.create_rectangle(bx - 1, by - 6, bx + 1, by + 6,
                                  fill=_GH, outline="")

        # Invader bombs
        for bx, by in self._bombs:
            self.create_rectangle(bx - 1, by - 5, bx + 1, by + 5,
                                  fill=_RED, outline="")

        # Player
        if self._state != "dead" or self._frame % 6 < 4:
            _draw_sprite(self, _PLAYER, int(self._px), int(self._py), _GH)

        # Explosions
        for ex, ey, t in self._explosions:
            r = (_S * 4) - t * 1
            color = _GH if t > 5 else _G
            for _ in range(6):
                a = random.uniform(0, 6.28)
                d = random.uniform(0, r)
                px = ex + d * (0.5 - random.random()) * 2
                py = ey + d * (0.5 - random.random()) * 2
                self.create_rectangle(px - 2, py - 2, px + 2, py + 2,
                                      fill=color, outline="")

        # Overlay: game over / win
        if self._state == "dead":
            self._overlay("GAME OVER", f"SCORE  {self._score:05d}", "#ff3322")
        elif self._state == "won":
            self._overlay("  YOU WIN  ", f"SCORE  {self._score:05d}", _GH)

    def _overlay(self, title: str, sub: str, color: str) -> None:
        cx, cy = self.W // 2, self.H // 2
        self.create_rectangle(cx - 120, cy - 50, cx + 120, cy + 60,
                              fill="#010a01", outline=_G, width=2)
        self.create_text(cx, cy - 20, text=title,
                         fill=color, font=("Consolas", 18, "bold"))
        self.create_text(cx, cy + 10, text=sub,
                         fill=_G, font=("Consolas", 11))
        self.create_text(cx, cy + 36, text="[ESC] EXIT",
                         fill=_GD, font=("Consolas", 9))


# =====================================================================
# KleinGame registration
# =====================================================================

class SpaceInvaders(KleinGame):
    title = "Space Invaders"

    def create(self, parent: tk.Widget, on_exit: Callable) -> tk.Widget:
        return SpaceInvadersPane(parent, on_exit=on_exit)
