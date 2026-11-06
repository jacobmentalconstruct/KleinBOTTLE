"""
kleinos/room_panel.py

Room image panel for the KleinBOTTLE text adventure.
Shows a 320×240 retro pixel art background per room, generated on demand
via the local ComfyUI pipeline and displayed with a green phosphor tint.

Images are cached in data/rooms/<room_id>.png.
"""

from __future__ import annotations

import shutil
import sys
import threading
import uuid
from pathlib import Path
from typing import Optional
import tkinter as tk

try:
    from PIL import Image as _PilImage, ImageTk as _PilImageTk  # type: ignore[import-untyped]
    _PILLOW = True
except ImportError:
    _PilImage = None   # type: ignore[assignment]
    _PilImageTk = None  # type: ignore[assignment]
    _PILLOW = False

_NEAREST = getattr(getattr(_PilImage, "Resampling", _PilImage), "NEAREST", 0)

_PIPELINE_ROOT = Path(r"C:\Jacob\Apps & Tools\image-generation-pipeline")
_ROOMS_DIR = Path(__file__).resolve().parent.parent / "data" / "rooms"

_BG      = "#010a01"
_BORDER  = "#003300"
_FG      = "#00cc33"
_DIM     = "#005500"
_CANVAS_BG = "#000000"


def _build_room_prompt(room_name: str, description: str, area: str = "") -> str:
    first_sentence = description.split(".")[0].strip()
    scene_type = "exterior" if area.lower() in ("outside",) else "interior"
    return (
        f"R3TR0, {room_name}, {first_sentence}, "
        f"point and click adventure game background, {scene_type}, Sierra style"
    )


def _green_tint(img: object, w: int, h: int) -> object:
    """Resize to w×h, convert to grayscale, map into green channel only."""
    img = img.resize((w, h), _NEAREST)  # type: ignore[union-attr]
    gray = img.convert("L")  # type: ignore[union-attr]
    zeros = gray.point(lambda _: 0)
    return _PilImage.merge("RGB", (zeros, gray, zeros))  # type: ignore[union-attr]


class RoomImagePanel(tk.Frame):
    PANEL_W = 328   # 320 image + 4px padding each side
    IMG_W   = 320
    IMG_H   = 240

    def __init__(self, parent: tk.Widget, **kw):
        super().__init__(parent, bg=_BG, width=self.PANEL_W,
                         highlightthickness=1, highlightbackground=_BORDER, **kw)
        self.pack_propagate(False)

        self._room_id:    Optional[str] = None
        self._area:       str = ""
        self._description: str = ""
        self._photo:      Optional[object] = None  # keep ImageTk reference
        self._generating: bool = False

        # Room name label
        self._name_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._name_var,
                 bg=_BG, fg=_FG,
                 font=("Consolas", 10, "bold"),
                 anchor="w").pack(fill="x", padx=6, pady=(6, 2))

        # Image canvas
        self._canvas = tk.Canvas(
            self, width=self.IMG_W, height=self.IMG_H,
            bg=_CANVAS_BG, highlightthickness=1, highlightbackground=_BORDER,
        )
        self._canvas.pack(padx=4, pady=2)
        self._canvas.create_text(
            self.IMG_W // 2, self.IMG_H // 2,
            text="", fill=_FG, font=("Consolas", 9),
            tags="status",
        )

        # Regen button
        self._regen_btn = tk.Button(
            self, text="↺ regen",
            bg=_BG, fg=_DIM,
            activebackground="#001a00", activeforeground=_FG,
            relief="flat", font=("Consolas", 8),
            command=self._regen,
            state="disabled",
        )
        self._regen_btn.pack(anchor="e", padx=6, pady=(2, 6))

    # ── Public API ────────────────────────────────────────────────────

    def update_room(self, room_id: str, room_name: str,
                    description: str, area: str = "") -> None:
        if room_id == self._room_id:
            return
        self._room_id    = room_id
        self._area       = area
        self._description = description
        self._name_var.set(room_name.upper())
        self._regen_btn.configure(state="normal")

        img_path = _ROOMS_DIR / f"{room_id}.png"
        if img_path.exists():
            self._display(img_path)
        else:
            self._start_generation(room_id, room_name, description, area)

    # ── Generation ────────────────────────────────────────────────────

    def _regen(self) -> None:
        if not self._room_id or self._generating:
            return
        img_path = _ROOMS_DIR / f"{self._room_id}.png"
        if img_path.exists():
            img_path.unlink()
        self._start_generation(
            self._room_id,
            self._name_var.get().title(),
            self._description,
            self._area,
        )

    def _start_generation(self, room_id: str, room_name: str,
                           description: str, area: str) -> None:
        self._generating = True
        self._regen_btn.configure(state="disabled")
        self._set_status("Generating…")
        threading.Thread(
            target=self._generate_worker,
            args=(room_id, room_name, description, area),
            daemon=True,
        ).start()

    def _generate_worker(self, room_id: str, room_name: str,
                          description: str, area: str) -> None:
        try:
            if str(_PIPELINE_ROOT) not in sys.path:
                sys.path.insert(0, str(_PIPELINE_ROOT))
            from pipeline.client import collect_images, queue_prompt, wait_for_completion  # type: ignore[import]
            from pipeline.styles import build_workflow  # type: ignore[import]

            prompt = _build_room_prompt(room_name, description, area)
            workflow, _ = build_workflow(prompt, "default")
            prompt_id = queue_prompt(workflow, str(uuid.uuid4()))
            result = wait_for_completion(prompt_id, timeout=300.0)

            tmp_dir = _ROOMS_DIR / "_tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            saved = collect_images(result, tmp_dir)
            if saved:
                dest = _ROOMS_DIR / f"{room_id}.png"
                shutil.move(str(saved[0]), str(dest))
                self.after(0, lambda: self._on_generated(room_id, dest))
            else:
                self.after(0, lambda: self._set_status("No image returned"))
        except Exception as exc:
            msg = str(exc)[:60]
            self.after(0, lambda: self._set_status(f"Error: {msg}"))
        finally:
            self._generating = False
            self.after(0, lambda: self._regen_btn.configure(state="normal"))

    def _on_generated(self, room_id: str, path: Path) -> None:
        if self._room_id == room_id:
            self._display(path)

    # ── Display ───────────────────────────────────────────────────────

    def _display(self, path: Path) -> None:
        if not _PILLOW:
            self._set_status("Pillow not installed\npip install pillow")
            return
        try:
            img = _PilImage.open(path)  # type: ignore[union-attr]
            tinted = _green_tint(img, self.IMG_W, self.IMG_H)
            self._photo = _PilImageTk.PhotoImage(tinted)  # type: ignore[union-attr]
            self._canvas.delete("all")
            self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
        except Exception as exc:
            self._set_status(f"Load error:\n{exc}")

    def _set_status(self, text: str) -> None:
        self._canvas.delete("all")
        self._canvas.create_text(
            self.IMG_W // 2, self.IMG_H // 2,
            text=text, fill=_FG, font=("Consolas", 9),
            width=self.IMG_W - 20, tags="status",
        )
