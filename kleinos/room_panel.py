"""
kleinos/room_panel.py

Full-width room banner for the KleinBOTTLE text adventure.

Layout (packed above GameSurface):
  ┌──────────────────────────────────────── ↺ regen ┐
  │  ROOM NAME                                       │  ← title row
  ├──────────────────────────────────────────────────┤
  │                                                  │
  │  [generated image — scales to column width]      │  ← 200px tall banner
  │                                                  │
  └──────────────────────────────────────────────────┘

Images are cached in data/rooms/<room_id>.png and displayed with a
green phosphor tint (grayscale → green channel).
"""

from __future__ import annotations

import shutil
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

from kleinos.pipeline_client import ensure_on_path as _pipeline_ensure_on_path

_ROOMS_DIR = Path(__file__).resolve().parent.parent / "data" / "rooms"

_BG        = "#010a01"
_BORDER    = "#003300"
_FG        = "#00cc33"
_DIM       = "#005500"
_CANVAS_BG = "#000000"

_IMG_ASPECT = 240 / 320   # 4:3 — height = width × this
_IMG_MAX_H  = 260         # hard ceiling — cmd/quick are bottom-packed so this just
                          # controls how much of the transcript is visible


def _build_room_prompt(room_name: str, description: str, area: str = "") -> str:
    first_sentence = description.split(".")[0].strip()
    scene_type = "exterior" if area.lower() in ("outside",) else "interior"
    return (
        f"R3TR0, {room_name}, {first_sentence}, "
        f"point and click adventure game background, {scene_type}, Sierra style"
    )


def _green_tint(img: object, canvas_w: int, canvas_h: int) -> object:
    """
    Scale img to fit within canvas_w×canvas_h keeping aspect ratio,
    center it on a black canvas, then map to green channel.
    """
    iw, ih = img.size  # type: ignore[union-attr]
    scale = min(canvas_w / iw, canvas_h / ih)
    new_w = int(iw * scale)
    new_h = int(ih * scale)
    img = img.resize((new_w, new_h), _NEAREST)  # type: ignore[union-attr]
    gray = img.convert("L")  # type: ignore[union-attr]
    zeros = gray.point(lambda _: 0)
    tinted = _PilImage.merge("RGB", (zeros, gray, zeros))  # type: ignore[union-attr]
    # Paste onto black canvas — centers the image
    out = _PilImage.new("RGB", (canvas_w, canvas_h), (0, 0, 0))  # type: ignore[union-attr]
    ox = (canvas_w - new_w) // 2
    oy = (canvas_h - new_h) // 2
    out.paste(tinted, (ox, oy))
    return out


class RoomImagePanel(tk.Frame):
    """Full-width banner: title row on top, image canvas below."""

    def __init__(self, parent: tk.Widget, **kw):
        super().__init__(parent, bg=_BG,
                         highlightthickness=1, highlightbackground=_BORDER, **kw)

        self._room_id:     Optional[str]  = None
        self._area:        str            = ""
        self._description: str            = ""
        self._photo:       Optional[object] = None   # hold ImageTk ref
        self._current_path: Optional[Path] = None
        self._generating:  bool           = False

        # ── Title row ────────────────────────────────────────────────
        title_row = tk.Frame(self, bg=_BG)
        title_row.pack(fill="x", padx=6, pady=(4, 2))

        self._name_var = tk.StringVar(value="")
        tk.Label(
            title_row, textvariable=self._name_var,
            bg=_BG, fg=_FG, font=("Consolas", 11, "bold"), anchor="w",
        ).pack(side="left")

        self._regen_btn = tk.Button(
            title_row, text="↺ regen",
            bg=_BG, fg=_DIM,
            activebackground="#001a00", activeforeground=_FG,
            relief="flat", font=("Consolas", 8),
            command=self._regen,
            state="disabled",
        )
        self._regen_btn.pack(side="right")

        # ── Image canvas — fills column width, height tracks aspect ratio ──
        self._canvas = tk.Canvas(
            self, height=200,                 # initial placeholder; resized on Configure
            bg=_CANVAS_BG, highlightthickness=1, highlightbackground=_BORDER,
        )
        self._canvas.pack(fill="x", padx=4, pady=(0, 4))
        self._canvas.bind("<Configure>", self._on_resize)

    # ── Public API ────────────────────────────────────────────────────

    def update_room(self, room_id: str, room_name: str,
                    description: str, area: str = "") -> None:
        if room_id == self._room_id:
            return
        self._room_id     = room_id
        self._area        = area
        self._description = description
        self._name_var.set(room_name.upper())
        self._regen_btn.configure(state="normal")

        img_path = _ROOMS_DIR / f"{room_id}.png"
        if img_path.exists():
            self._display(img_path)
        else:
            self._start_generation(room_id, room_name, description, area)

    # ── Resize ────────────────────────────────────────────────────────

    def _canvas_h(self) -> int:
        """Desired canvas height: 4:3 of width, capped at _IMG_MAX_H.

        cmd/quick are bottom-packed in GameSurface so they are always visible
        regardless of this height; the transcript fills whatever is in between.
        """
        w = self._canvas.winfo_width() or 320
        return min(int(w * _IMG_ASPECT), _IMG_MAX_H)

    def _on_resize(self, _=None) -> None:
        new_h = self._canvas_h()
        if self._canvas.winfo_height() != new_h:
            self._canvas.configure(height=new_h)
        if self._current_path and self._current_path.exists():
            self._display(self._current_path)

    # ── Generation ────────────────────────────────────────────────────

    def _regen(self) -> None:
        if not self._room_id or self._generating:
            return
        img_path = _ROOMS_DIR / f"{self._room_id}.png"
        if img_path.exists():
            img_path.unlink()
        self._current_path = None
        self._start_generation(
            self._room_id,
            self._name_var.get().title(),
            self._description,
            self._area,
        )

    def _start_generation(self, room_id: str, room_name: str,
                           description: str, area: str) -> None:
        # Silently skip if pipeline is offline (auto-triggered, non-interactive)
        try:
            import urllib.request as _ur
            from kleinos import config as _cfg
            c = _cfg.load().get("image_pipeline", {})
            host = c.get("comfyui_host", "127.0.0.1")
            port = int(c.get("comfyui_port", 8188))
            with _ur.urlopen(f"http://{host}:{port}/system_stats", timeout=0.8):
                pass
        except Exception:
            self._generating = False
            return
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
            if not _pipeline_ensure_on_path():
                self.after(0, lambda: self._set_status("Pipeline not found — check submodule."))
                return
            from pipeline.client import collect_images, queue_prompt, wait_for_completion  # type: ignore[import]
            from pipeline.styles import build_workflow  # type: ignore[import]

            prompt = _build_room_prompt(room_name, description, area)
            workflow, _ = build_workflow(prompt, "default")
            pid = queue_prompt(workflow, str(uuid.uuid4()))
            result = wait_for_completion(pid, timeout=300.0)

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
            msg = str(exc)[:80]
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
            w = self._canvas.winfo_width()
            if w < 2:
                # Canvas not yet laid out — defer one frame
                self.after(50, lambda: self._display(path))
                return
            img = _PilImage.open(path)  # type: ignore[union-attr]
            tinted = _green_tint(img, w, self._canvas_h())
            self._photo = _PilImageTk.PhotoImage(tinted)  # type: ignore[union-attr]
            self._canvas.delete("all")
            self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
            self._current_path = path
        except Exception as exc:
            self._set_status(f"Load error:\n{exc}")

    def _set_status(self, text: str) -> None:
        self._canvas.delete("all")
        w = self._canvas.winfo_width() or 400
        self._canvas.create_text(
            w // 2, self._canvas_h() // 2,
            text=text, fill=_FG, font=("Consolas", 9),
            width=w - 20,
        )
