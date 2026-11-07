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
from kleinos import audio

_SAVE_PATH = Path(__file__).parent / "assets" / "highscore.json"

from kleinos.palette import (
    BG as _BG, GM_MID as _G, GM_BRIGHT as _GH, GM_DARK as _GD, FG_HUD as _HUD,
)

# ── Sprite definitions (1=filled, 0=empty, row-major) ────────────────
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

_PLAYER = [
    [0,0,0,1,1,0,0,0],
    [0,0,1,1,1,1,0,0],
    [0,0,1,1,1,1,0,0],
    [1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1],
]

# =====================================================================
# Game canvas
# =====================================================================

class SpaceInvadersPane(tk.Canvas):
    # Base (scale=1) dimensions — overridden as instance attrs when scale != 1
    W: int = 539
    H: int = 408

    COLS: int = 10
    ROWS: int = 4
    H_GAP: int = 44
    V_GAP: int = 36

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_exit: Optional[Callable] = None,
        scale: float = 1.0,
    ):
        s = max(0.1, float(scale))
        self._scale   = s
        self._s       = max(1, int(3 * s))       # sprite pixel size
        self._spr_w   = 8 * self._s
        self._spr_h   = 6 * self._s
        self.W        = int(539 * s)
        self.H        = int(408 * s)
        self.H_GAP    = int(44 * s)
        self.V_GAP    = int(36 * s)
        # Speeds (px/tick)
        self._player_spd  = max(2, int(5 * s))
        self._bomb_spd    = max(2, int(5 * s))
        self._hit_margin  = max(8, int(14 * s))
        self._inv_step    = max(2, int(10 * s))
        # Fonts
        self._font_hud    = ("Consolas", max(7, int(9  * s)))
        self._font_sm     = ("Consolas", max(6, int(8  * s)))
        self._font_mid    = ("Consolas", max(9, int(11 * s)))
        self._font_mid_b  = ("Consolas", max(9, int(11 * s)), "bold")
        self._font_title  = ("Consolas", max(14, int(24 * s)), "bold")
        self._font_diff   = ("Consolas", max(9,  int(13 * s)), "bold")
        self._font_over   = ("Consolas", max(12, int(18 * s)), "bold")

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
        self.bind("<Escape>",     lambda _: self._on_escape())
        self.bind("<Button-1>",   self._on_click)
        self._tick_id: Optional[str] = None
        self._loop()

    # ── Sprite drawing ───────────────────────────────────────────────

    def _draw_sprite(self, pattern, cx: int, cy: int, color: str) -> None:
        """Draw a pixel-art sprite centred at (cx, cy) using this pane's scale."""
        ox = cx - self._spr_w // 2
        oy = cy - self._spr_h // 2
        for r, row in enumerate(pattern):
            for c, px in enumerate(row):
                if px:
                    x0 = ox + c * self._s
                    y0 = oy + r * self._s
                    self.create_rectangle(
                        x0, y0, x0 + self._s - 1, y0 + self._s - 1,
                        fill=color, outline="",
                    )

    # ── Setup ────────────────────────────────────────────────────────

    def _reset(self, base_speed: int = 18, bomb_chance: float = 0.18) -> None:
        s = self._scale
        self._px = self.W // 2
        self._py = self.H - int(36 * s)
        self._score = 0
        self._lives = 3
        self._frame = 0

        self._base_speed  = base_speed
        self._bomb_chance = bomb_chance
        self._bullet_speed = max(int(11 * s), int((40 - base_speed) * s))

        self._invaders: list[list] = [
            [c, r, True] for r in range(self.ROWS) for c in range(self.COLS)
        ]
        self._gx = (self.W - self.COLS * self.H_GAP) // 2
        self._gy = int(48 * s)
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
        self._state = "title"   # title | start | play | quit_confirm | dead | won

    # ── Main loop ────────────────────────────────────────────────────

    def _loop(self) -> None:
        self._update()
        self._draw()
        self._tick_id = self.after(40, self._loop)

    def _on_escape(self) -> None:
        if self._state == "title":
            self._quit()
        elif self._state == "start":
            self._state = "title"
        elif self._state == "play":
            self._state = "quit_confirm"
        elif self._state == "quit_confirm":
            self._state = "play"
        elif self._state in ("dead", "won"):
            self._quit()

    def _on_click(self, event: tk.Event) -> None:
        x, y = event.x, event.y
        cx, cy = self.W // 2, self.H // 2
        s = self._scale

        if self._state == "title":
            self._state = "start"

        elif self._state == "start":
            for i, (speed, chance) in enumerate([(25, 0.10), (18, 0.18), (11, 0.28)]):
                row_y = cy - int(10 * s) + i * int(26 * s)
                if abs(x - cx) < int(130 * s) and abs(y - row_y) < int(16 * s):
                    self._reset(base_speed=speed, bomb_chance=chance)
                    self._state = "play"
                    return

        elif self._state == "quit_confirm":
            if abs(y - (cy + int(16 * s))) < int(16 * s):
                if x < cx:
                    self._reset()
                else:
                    self._state = "play"

        elif self._state in ("dead", "won"):
            if abs(y - (cy + int(36 * s))) < int(16 * s):
                self._reset()

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
        except Exception:  # SAFE: file absent on first run
            return 0

    def _save_high_score(self, score: int) -> None:
        try:
            _SAVE_PATH.write_text(
                json.dumps({"high_score": score}, indent=2), encoding="utf-8"
            )
        except Exception:  # MEDIUM: high-score write failure silently lost
            pass

    # ── Update ───────────────────────────────────────────────────────

    def _update(self) -> None:
        self._frame += 1

        if self._state == "title":
            if self._keys - {"Escape"}:
                self._keys.clear()
                self._state = "start"
            return

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

        if self._state == "quit_confirm":
            if "y" in self._keys or "Y" in self._keys:
                self._keys.discard("y")
                self._reset()
            elif "n" in self._keys or "N" in self._keys:
                self._keys.discard("n")
                self._state = "play"
            return

        if self._state in ("dead", "won"):
            if "r" in self._keys:
                self._keys.discard("r")
                self._reset()
            return

        if self._invincible > 0:
            self._invincible -= 1

        # Player movement
        margin = self._spr_w // 2
        if "Left" in self._keys or "a" in self._keys:
            self._px = max(margin, self._px - self._player_spd)
        if "Right" in self._keys or "d" in self._keys:
            self._px = min(self.W - margin, self._px + self._player_spd)

        # Fire
        if self._fire_cd > 0:
            self._fire_cd -= 1
        if "space" in self._keys and self._fire_cd == 0:
            self._bullets.append([float(self._px), float(self._py - self._spr_h // 2)])
            self._fire_cd = 15
            audio.shoot()

        # Bullet ↔ invader collision
        for bullet in self._bullets[:]:
            bx, by = bullet
            for inv in self._invaders:
                if not inv[2]:
                    continue
                ix = self._gx + inv[0] * self.H_GAP + self.H_GAP // 2
                iy = self._gy + inv[1] * self.V_GAP + self.V_GAP // 2
                if abs(bx - ix) < self._spr_w // 2 and abs(by - iy) < self._spr_h // 2 + 2:
                    inv[2] = False
                    if bullet in self._bullets:
                        self._bullets.remove(bullet)
                    self._score += 10
                    self._explosions.append([ix, iy, 8])
                    audio.hit()
                    break

        # Move player bullets
        self._bullets = [[x, y - self._bullet_speed] for x, y in self._bullets if y > 0]

        # Move invader bombs
        self._bombs = [[x, y + self._bomb_spd] for x, y in self._bombs if y < self.H]

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
            audio.tick(len(alive))
            if self._step_down:
                self._gy += self.V_GAP // 2
                self._step_down = False
                self._gdx *= -1
            else:
                self._gx += self._gdx * self._inv_step
                cols_alive = [inv[0] for inv in alive]
                left  = self._gx + min(cols_alive) * self.H_GAP
                right = self._gx + max(cols_alive) * self.H_GAP + self._spr_w
                if right >= self.W - 4 or left <= 4:
                    self._step_down = True

            if random.random() < self._bomb_chance:
                shooter = random.choice(alive)
                bx = self._gx + shooter[0] * self.H_GAP + self.H_GAP // 2
                by = self._gy + shooter[1] * self.V_GAP + self._spr_h
                self._bombs.append([float(bx), float(by)])

        # Bomb ↔ player collision
        hm = self._hit_margin
        for bomb in self._bombs[:]:
            bx, by = bomb
            if self._invincible == 0 and abs(bx - self._px) < hm and abs(by - self._py) < hm:
                self._bombs.remove(bomb)
                self._lives -= 1
                self._explosions.append([self._px, self._py, 12])
                self._px = self.W // 2
                self._bullets.clear()
                if self._lives <= 0:
                    self._state = "dead"
                    self._check_high_score()
                    audio.death()
                else:
                    self._invincible = 60
                    audio.player_hit()

        # Game over when invader bottom reaches the player's gun line
        for inv in self._invaders:
            if inv[2]:
                iy = self._gy + inv[1] * self.V_GAP + self._spr_h
                if iy >= self._py - self._spr_h // 2:
                    self._state = "dead"

    # ── Draw ─────────────────────────────────────────────────────────

    def _draw(self) -> None:
        self.delete("all")
        scan_step = max(2, int(4 * self._scale))
        for y in range(0, self.H, scan_step):
            self.create_line(0, y, self.W, y, fill="#020e02")

        if self._state == "title":
            self._title_screen()
            return

        # HUD
        self.create_text(8, 8, anchor="nw",
                         text=f"SCORE  {self._score:05d}",
                         fill=_HUD, font=self._font_hud)
        hearts = "▮" * self._lives + "▯" * (3 - self._lives)
        self.create_text(self.W - 8, 8, anchor="ne",
                         text=f"LIVES  {hearts}",
                         fill=_HUD, font=self._font_hud)
        self.create_line(0, int(24 * self._scale), self.W, int(24 * self._scale), fill=_GD)
        self.create_line(0, self.H - int(22 * self._scale), self.W, self.H - int(22 * self._scale), fill=_GD)

        self.create_text(self.W // 2, self.H - int(11 * self._scale), anchor="center",
                         text="[←/A][→/D] MOVE    [SPACE] FIRE    [ESC] EXIT",
                         fill=_GD, font=self._font_sm)

        # Invaders
        anim = _INV_A if (self._frame // 6) % 2 == 0 else _INV_B
        for inv in self._invaders:
            if not inv[2]:
                continue
            ix = self._gx + inv[0] * self.H_GAP + self.H_GAP // 2
            iy = self._gy + inv[1] * self.V_GAP + self.V_GAP // 2
            self._draw_sprite(anim, ix, iy, _G)

        # Bullets
        bw = max(1, int(1 * self._scale))
        bh = max(3, int(6 * self._scale))
        for bx, by in self._bullets:
            self.create_rectangle(bx - bw, by - bh, bx + bw, by + bh,
                                  fill=_GH, outline="")

        # Bombs
        bw2 = max(1, int(1 * self._scale))
        bh2 = max(3, int(5 * self._scale))
        for bx, by in self._bombs:
            self.create_rectangle(bx - bw2, by - bh2, bx + bw2, by + bh2,
                                  fill=_GD, outline="")

        # Player
        if self._state != "dead" or self._frame % 6 < 4:
            self._draw_sprite(_PLAYER, int(self._px), int(self._py), _GH)

        # Explosions
        for ex, ey, t in self._explosions:
            r = (self._s * 4) - t
            color = _GH if t > 5 else _G
            ep = max(1, self._s)
            for _ in range(6):
                px = ex + r * (0.5 - random.random()) * 2
                py = ey + r * (0.5 - random.random()) * 2
                self.create_rectangle(px - ep, py - ep, px + ep, py + ep,
                                      fill=color, outline="")

        # Invincibility blink
        if self._invincible > 0 and (self._frame // 3) % 2 == 0:
            hm = self._hit_margin
            cx, cy = int(self._px), int(self._py)
            self.create_rectangle(cx - hm, cy - hm, cx + hm, cy + hm,
                                  outline=_GH, fill="", width=1)

        # State overlays
        if self._state == "start":
            self._difficulty_screen()
        elif self._state == "quit_confirm":
            self._quit_confirm_overlay()
        elif self._state == "dead":
            self._overlay("GAME OVER", f"SCORE  {self._score:05d}", _G)
        elif self._state == "won":
            self._overlay("  YOU WIN  ", f"SCORE  {self._score:05d}", _GH)

    # ── Screens ──────────────────────────────────────────────────────

    def _title_screen(self) -> None:
        s = self._scale
        cx, cy = self.W // 2, self.H // 2

        self.create_text(cx, cy - int(90 * s), text="NULL",
                         fill=_GH, font=self._font_title)
        self.create_text(cx, cy - int(58 * s), text="INVADERS",
                         fill=_GH, font=self._font_title)

        anim = _INV_A if (self._frame // 8) % 2 == 0 else _INV_B
        spacing = int(44 * s)
        start_x = cx - int(154 * s)
        for i in range(8):
            self._draw_sprite(anim, start_x + i * spacing, cy - int(20 * s), _GD)

        self.create_line(cx - int(160 * s), cy - int(2 * s),
                         cx + int(160 * s), cy - int(2 * s), fill=_GD)

        hs = f"HI  {self._high_score:05d}" if self._high_score else "HI  -----"
        self.create_text(cx, cy + int(18 * s), text=hs, fill=_G, font=self._font_mid)

        if (self._frame // 15) % 2 == 0:
            self.create_text(cx, cy + int(46 * s), text="PRESS ANY KEY TO PLAY",
                             fill=_GH, font=self._font_mid_b)

        self.create_text(cx, cy + int(80 * s), text="[ESC] EXIT",
                         fill=_GD, font=self._font_sm)

    def _difficulty_screen(self) -> None:
        s = self._scale
        cx, cy = self.W // 2, self.H // 2
        self.create_rectangle(cx - int(150 * s), cy - int(80 * s),
                              cx + int(150 * s), cy + int(70 * s),
                              fill="#010a01", outline=_G, width=2)
        self.create_text(cx, cy - int(58 * s), text="SELECT DIFFICULTY",
                         fill=_GH, font=self._font_diff)
        self.create_line(cx - int(120 * s), cy - int(38 * s),
                         cx + int(120 * s), cy - int(38 * s), fill=_GD)
        for i, (label, key) in enumerate([("EASY", "[1]"), ("MEDIUM", "[2]"), ("HARD", "[3]")]):
            y = cy - int(10 * s) + i * int(26 * s)
            self.create_text(cx - int(30 * s), y, text=key,   fill=_G,  font=self._font_mid_b, anchor="e")
            self.create_text(cx - int(20 * s), y, text=label, fill=_GH, font=self._font_mid,   anchor="w")
        self.create_text(cx, cy + int(56 * s), text="[ESC] BACK",
                         fill=_GD, font=self._font_sm)

    def _quit_confirm_overlay(self) -> None:
        s = self._scale
        cx, cy = self.W // 2, self.H // 2
        self.create_rectangle(cx - int(160 * s), cy - int(50 * s),
                              cx + int(160 * s), cy + int(50 * s),
                              fill="#010a01", outline=_G, width=2)
        self.create_text(cx, cy - int(20 * s), text="Are you really a quitter?",
                         fill=_GH, font=self._font_diff)
        self.create_text(cx - int(30 * s), cy + int(16 * s), text="[Y]", fill=_G,  font=self._font_mid_b, anchor="e")
        self.create_text(cx - int(20 * s), cy + int(16 * s), text="Yes", fill=_GH, font=self._font_mid,   anchor="w")
        self.create_text(cx + int(30 * s), cy + int(16 * s), text="[N]", fill=_G,  font=self._font_mid_b, anchor="e")
        self.create_text(cx + int(40 * s), cy + int(16 * s), text="No",  fill=_GH, font=self._font_mid,   anchor="w")

    def _overlay(self, title: str, sub: str, color: str) -> None:
        s = self._scale
        cx, cy = self.W // 2, self.H // 2
        self.create_rectangle(cx - int(130 * s), cy - int(60 * s),
                              cx + int(130 * s), cy + int(70 * s),
                              fill="#010a01", outline=_G, width=2)
        self.create_text(cx, cy - int(32 * s), text=title,
                         fill=color, font=self._font_over)
        self.create_text(cx, cy - int(4 * s), text=sub,
                         fill=_G, font=self._font_mid)
        if self._new_high_score:
            self.create_text(cx, cy + int(16 * s), text="** NEW HIGH SCORE **",
                             fill=_GH, font=self._font_hud)
        else:
            if self._high_score:
                self.create_text(cx, cy + int(16 * s), text=f"HI  {self._high_score:05d}",
                                 fill=_GD, font=self._font_hud)
        self.create_text(cx, cy + int(36 * s), text="[R] PLAY AGAIN",
                         fill=_G, font=self._font_hud)
        self.create_text(cx, cy + int(52 * s), text="[ESC] EXIT",
                         fill=_GD, font=self._font_sm)


# =====================================================================
# KleinGame registration
# =====================================================================

class SpaceInvaders(KleinGame):
    title = "NULL Invaders"
    description = "Blast the invaders before they breach the null line."

    def create(self, parent: tk.Widget, on_exit: Callable) -> tk.Widget:
        from kleinos.config import load as _cfg_load, _PC_SIZES
        cfg = _cfg_load()
        scale = _PC_SIZES.get(cfg.get("pc_size", "medium"), 1.0)
        return SpaceInvadersPane(parent, on_exit=on_exit, scale=scale)
