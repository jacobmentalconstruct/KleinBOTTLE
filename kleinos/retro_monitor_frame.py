"""
klein_monitors/retro_monitor_frame.py

Self-contained copy of RetroMonitorFrame from the pipeline's
modules/retro_monitor/frame.py.

Wraps any child Tkinter widget in a CRT monitor bezel PNG.
The bezel PNG and screen_rect.json live in assets/ beside this package.

Usage:
    mon = RetroMonitorFrame(parent, bezel="green")   # or "amber"
    mon.pack()
    # put content inside mon.screen
    MyWidget(mon.screen).pack(fill="both", expand=True)
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from typing import Optional

_ASSETS = Path(__file__).parent / "assets"

try:
    from PIL import Image, ImageTk  # type: ignore[import-untyped]
    _PILLOW = True
except ImportError:
    _PILLOW = False


class RetroMonitorFrame(tk.Frame):
    """
    Displays a CRT monitor bezel with a live Tkinter widget inside the screen.

    Parameters
    ----------
    parent     : Tkinter parent widget
    bezel      : "green" | "amber" — selects the bundled PNG
    bezel_path : override with an explicit PNG path
    rect_path  : override with an explicit screen_rect.json path
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        bezel: str = "green",
        bezel_path: Optional[Path] = None,
        rect_path: Optional[Path] = None,
        scale: float = 1.0,
        **kw,
    ):
        super().__init__(parent, bd=0, highlightthickness=0, **kw)

        png = bezel_path or (_ASSETS / f"monitor_{bezel}.png")
        rct = rect_path or (_ASSETS / "screen_rect.json")

        rect = self._load_rect(rct)
        s = max(0.3, float(scale))
        canvas_w = int(rect.get("canvas_w", 480) * s)
        canvas_h = int(rect.get("canvas_h", 360) * s)
        # Scale rect coordinates proportionally
        rect = {
            "x":      int(rect["x"]      * s),
            "y":      int(rect["y"]      * s),
            "width":  int(rect["width"]  * s),
            "height": int(rect["height"] * s),
        }

        self._canvas = tk.Canvas(
            self,
            width=canvas_w,
            height=canvas_h,
            bd=0,
            highlightthickness=0,
            bg="#000000",
            takefocus=0,
        )
        self._canvas.pack()
        # Redirect clicks on the bezel border to the screen content area
        self._canvas.bind("<Button-1>", lambda e: self.screen.focus_set())

        if _PILLOW and png.exists():
            self._prepare_image_bezel(png, canvas_w, canvas_h)
        else:
            self._draw_fallback(canvas_w, canvas_h, rect, bezel)

        # Public frame — callers put content here
        self.screen = tk.Frame(
            self._canvas,
            bg="#000000",
            bd=0,
            highlightthickness=0,
        )
        self._canvas.create_window(
            rect["x"],
            rect["y"],
            anchor="nw",
            width=rect["width"],
            height=rect["height"],
            window=self.screen,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_rect(path: Path) -> dict:
        default = {"x": 36, "y": 36, "width": 408, "height": 288,
                   "canvas_w": 480, "canvas_h": 360}
        if not path.exists():
            return default
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Inject canvas dims if missing (older format didn't store them)
            data.setdefault("canvas_w", 480)
            data.setdefault("canvas_h", 360)
            return data
        except Exception:
            return default

    def _prepare_image_bezel(self, png: Path, w: int, h: int) -> None:
        img = Image.open(png).resize(
            (w, h),
            getattr(Image, "Resampling", Image).LANCZOS,
        )
        self._photo = ImageTk.PhotoImage(img)
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)

    def _draw_fallback(self, w: int, h: int, rect: dict, style: str) -> None:
        screen_color = "#00dd33" if style == "green" else "#ff8800"
        self._canvas.create_rectangle(0, 0, w, h, fill="#c8bfa0", outline="#8a8068", width=2)
        sx, sy, sw, sh = rect["x"], rect["y"], rect["width"], rect["height"]
        self._canvas.create_rectangle(sx - 4, sy - 4, sx + sw + 4, sy + sh + 4,
                                      fill="#303030")
        self._canvas.create_rectangle(sx, sy, sx + sw, sy + sh, fill="#010a01")
        led_x, led_y = w - 20, h - 20
        self._canvas.create_oval(led_x - 5, led_y - 5, led_x + 5, led_y + 5,
                                 fill=screen_color)
