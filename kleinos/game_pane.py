"""
klein_monitors/game_pane.py

Space Invaders — green phosphor pixel-art game for KleinOS.

Controls: LEFT/RIGHT move, SPACE fire, ESC exit.
Drawn entirely with tk.Canvas rectangles — no text sprites, smooth animation.
"""

from __future__ import annotations

import json
import random
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

from kleinos.klein_app import KleinGame

_SAVE_PATH = Path(__file__).parent / "assets" / "highscore.json"

# ── Palette ──────────────────────────────────────────────────────────
_BG   = "#010a01"
_G    = "#00dd33"   # main green — player, invaders, bullets
_GH   = "#88ff88"   # highlight — explosions, win text
_GD   = "#004d18"   # dim green — grid lines, controls text
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
        self._high_score = self._load_high_score()
        self._reset()
        self.focus_set()
        self.bind("<KeyPress>",   lambda e: self._keys.add(e.keysym))
        self.bind("<KeyRelease>", lambda e: self._keys.discard(e.keysym))
        self.bind("<Escape>",     lambda e: self._on_escape())
        self._tick_id: Optional[str] = None
        self._loop()

    # ── Setup ────────────────────────────────────────────────────────

    def _reset(self, base_speed: int = 18, bomb_chance: float = 0.18) -> None:
        self._px = self.W // 2
        self._py = self.H - 36
        self._score = 0
        self._lives = 3
        self._frame = 0

        self._base_speed = base_speed
        self._bomb_chance = bomb_chance
        # bullet speed scales inversely with difficulty: harder = faster bullets
        self._bullet_speed = max(11, 40 - base_speed)

        self._invaders: list[list] = [
            [c, r, True] for r in range(self.ROWS) for c in range(self.COLS)
        ]
        self._gx = (self.W - self.COLS * self.H_GAP) // 2
        self._gy = 48
        self._gdx = 1
        self._step_down = False
        self._inv_timer = 0

        self._bullets: list[list[float]] = []
        self._bombs: list[list[float]] = []
        self._explosions: list[list] = []

        self._fire_cd = 0
        self._invincible = 0
        self._new_high_score = False
        self._keys: set[str] = set()
        self._state = "start"    # start | play | quit_confirm | dead | won

    # ── Main loop ────────────────────────────────────────────────────

    def _loop(self) -> None:
        self._update()
        self._draw()
        self._tick_id = self.after(40, self._loop)   # ~25 fps

    def _on_escape(self) -> None:
        if self._state == "start":
            self._quit()
        elif self._state == "play":
            self._state = "quit_confirm"
        elif self._state == "quit_confirm":
            self._state = "play"           # ESC again = No, resume
        elif self._state in ("dead", "won"):
            self._quit()

    def _quit(self) -> None:
        if self._tick_id:
            self.after_cancel(self._tick_id)
            self._tick_id = None
        if self._on_exit:
            self._on_exit()

    def _check_high_score(self) -> None:
        if self._score > self._high_score:
            self._high_score = self._score
            self._new_high_score = True
            self._save_high_score(self._score)

    def _load_high_score(self) -> int:
        try:
            return int(json.loads(_SAVE_PATH.read_text(encoding="utf-8"))["high_score"])
        except Exception:
            return 0

    def _save_high_score(self, score: int) -> None:
        try:
            _SAVE_PATH.write_text(
                json.dumps({"high_score": score}, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    # ── Update ───────────────────────────────────────────────────────

    def _update(self) -> None:
        self._frame += 1

        # Difficulty select
        if self._state == "start":
            if "1" in self._keys:
                self._keys.discard("1")
                self._reset(base_speed=25, bomb_chance=0.10)
                self._state = "play"
            elif "2" in self._keys:
                self._keys.discard("2")
                self._reset(base_speed=18, bomb_chance=0.18)
                self._state = "play"
            elif "3" in self._keys:
                self._keys.discard("3")
                self._reset(base_speed=11, bomb_chance=0.28)
                self._state = "play"
            return

        # Quit confirmation popup
        if self._state == "quit_confirm":
            if "y" in self._keys or "Y" in self._keys:
                self._keys.discard("y")
                self._reset()           # back to start/difficulty screen
            elif "n" in self._keys or "N" in self._keys:
                self._keys.discard("n")
                self._state = "play"
            return

        # Restart after game over / win
        if self._state in ("dead", "won"):
            if "r" in self._keys:
                self._keys.discard("r")
                self._reset()
                self._state = "start"
            return

        if self._invincible > 0:
            self._invincible -= 1

        # Player movement  (WASD mirrors arrow keys)
        if "Left" in self._keys or "a" in self._keys:
            self._px = max(16, self._px - 5)
        if "Right" in self._keys or "d" in self._keys:
            self._px = min(self.W - 16, self._px + 5)

        # Fire
        if self._fire_cd > 0:
            self._fire_cd -= 1
        if "space" in self._keys and self._fire_cd == 0:
            self._bullets.append([float(self._px), float(self._py - 20)])
            self._fire_cd = 15

        # Move player bullets
        self._bullets = [[x, y - self._bullet_speed] for x, y in self._bullets if y > 0]

        # Move invader bombs
        self._bombs = [[x, y + 5] for x, y in self._bombs if y < self.H]

        # Tick explosions
        self._explosions = [[x, y, t - 1] for x, y, t in self._explosions if t > 1]

        # Move invader grid
        alive = [inv for inv in self._invaders if inv[2]]
        if not alive:
            self._state = "won"
            self._check_high_score()
            return

        speed = max(2, self._base_speed - len(alive) // 3)
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
            if random.random() < self._bomb_chance:
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
            if self._invincible == 0 and abs(bx - self._px) < 14 and abs(by - self._py) < 14:
                self._bombs.remove(bomb)
                self._lives -= 1
                self._explosions.append([self._px, self._py, 12])
                self._px = self.W // 2
                self._bullets.clear()
                if self._lives <= 0:
                    self._state = "dead"
                    self._check_high_score()
                else:
                    self._invincible = 60

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
                         text="[←/A][→/D] MOVE    [SPACE] FIRE    [ESC] EXIT",
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
                                  fill=_GD, outline="")

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

        # Invincibility blink — flash player outline
        if self._invincible > 0 and (self._frame // 3) % 2 == 0:
            cx, cy = int(self._px), int(self._py)
            self.create_rectangle(cx - 14, cy - 14, cx + 14, cy + 14,
                                  outline=_GH, fill="", width=1)

        # Overlays
        if self._state == "start":
            self._start_screen()
        elif self._state == "quit_confirm":
            self._quit_confirm_overlay()
        elif self._state == "dead":
            self._overlay("GAME OVER", f"SCORE  {self._score:05d}", _G)
        elif self._state == "won":
            self._overlay("  YOU WIN  ", f"SCORE  {self._score:05d}", _GH)

    def _start_screen(self) -> None:
        cx, cy = self.W // 2, self.H // 2
        self.create_rectangle(cx - 150, cy - 90, cx + 150, cy + 90,
                              fill="#010a01", outline=_G, width=2)
        self.create_text(cx, cy - 65, text="SPACE INVADERS",
                         fill=_GH, font=("Consolas", 15, "bold"))
        hs_label = f"HI  {self._high_score:05d}" if self._high_score else "HI  -----"
        self.create_text(cx, cy - 44, text=hs_label,
                         fill=_GD, font=("Consolas", 9))
        self.create_line(cx - 120, cy - 30, cx + 120, cy - 30, fill=_GD)
        for i, (label, key) in enumerate([
            ("EASY",   "[1]"),
            ("MEDIUM", "[2]"),
            ("HARD",   "[3]"),
        ]):
            y = cy - 10 + i * 26
            self.create_text(cx - 30, y, text=key,   fill=_G,  font=("Consolas", 11, "bold"), anchor="e")
            self.create_text(cx - 20, y, text=label,  fill=_GH, font=("Consolas", 11), anchor="w")
        self.create_text(cx, cy + 70, text="[ESC] EXIT",
                         fill=_GD, font=("Consolas", 8))

    def _quit_confirm_overlay(self) -> None:
        cx, cy = self.W // 2, self.H // 2
        self.create_rectangle(cx - 160, cy - 50, cx + 160, cy + 50,
                              fill="#010a01", outline=_G, width=2)
        self.create_text(cx, cy - 20, text="Are you really a quitter?",
                         fill=_GH, font=("Consolas", 12, "bold"))
        self.create_text(cx - 30, cy + 16, text="[Y]",  fill=_G,  font=("Consolas", 11, "bold"), anchor="e")
        self.create_text(cx - 20, cy + 16, text="Yes",  fill=_GH, font=("Consolas", 11), anchor="w")
        self.create_text(cx + 30, cy + 16, text="[N]",  fill=_G,  font=("Consolas", 11, "bold"), anchor="e")
        self.create_text(cx + 40, cy + 16, text="No",   fill=_GH, font=("Consolas", 11), anchor="w")

    def _overlay(self, title: str, sub: str, color: str) -> None:
        cx, cy = self.W // 2, self.H // 2
        self.create_rectangle(cx - 130, cy - 60, cx + 130, cy + 70,
                              fill="#010a01", outline=_G, width=2)
        self.create_text(cx, cy - 32, text=title,
                         fill=color, font=("Consolas", 18, "bold"))
        self.create_text(cx, cy - 4, text=sub,
                         fill=_G, font=("Consolas", 11))
        if self._new_high_score:
            self.create_text(cx, cy + 16, text="** NEW HIGH SCORE **",
                             fill=_GH, font=("Consolas", 9, "bold"))
        else:
            hs_label = f"HI  {self._high_score:05d}" if self._high_score else ""
            if hs_label:
                self.create_text(cx, cy + 16, text=hs_label,
                                 fill=_GD, font=("Consolas", 9))
        self.create_text(cx, cy + 36, text="[R] PLAY AGAIN",
                         fill=_G, font=("Consolas", 9))
        self.create_text(cx, cy + 52, text="[ESC] EXIT",
                         fill=_GD, font=("Consolas", 9))


# =====================================================================
# KleinGame registration
# =====================================================================

class SpaceInvaders(KleinGame):
    title = "Space Invaders"
    description = "Classic arcade shoot-'em-up. Blast the invaders before they land."

    def create(self, parent: tk.Widget, on_exit: Callable) -> tk.Widget:
        return SpaceInvadersPane(parent, on_exit=on_exit)
