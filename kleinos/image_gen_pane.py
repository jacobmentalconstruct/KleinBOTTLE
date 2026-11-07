"""
kleinos/image_gen_pane.py

In-PC image generator — KleinApp that wraps the image-generation-pipeline
submodule (tools/image-pipeline/) with a simple GUI.

Prompt input → style selector → Generate button → live status → image display.
"""
from __future__ import annotations

import shutil
import sys
import threading
import tkinter as tk
from pathlib import Path
from typing import Optional

from kleinos.klein_app import KleinApp
from kleinos.room_panel import _pipeline_root

try:
    from PIL import Image as _PilImage, ImageTk as _PilImageTk  # type: ignore[import-untyped]
    _NEAREST = getattr(getattr(_PilImage, "Resampling", _PilImage), "NEAREST", 0)
    _PILLOW = True
except ImportError:
    _PilImage = _PilImageTk = None  # type: ignore[assignment]
    _NEAREST = 0
    _PILLOW = False

_BG     = "#010a01"
_BORDER = "#003300"
_FG     = "#00cc33"
_DIM    = "#005500"
_HDR_BG = "#001a00"

_OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "generated"
_STYLES  = ("default", "kleinbottle", "projectmapper")


def _mk_btn(parent: tk.Widget, text: str, command, fg: str = _FG) -> tk.Button:
    return tk.Button(
        parent, text=text, bg=_BG, fg=fg,
        activebackground="#001a00", activeforeground=_FG,
        relief="flat", font=("Consolas", 9, "bold"),
        cursor="hand2", command=command,
    )


class ImageGenPane(tk.Frame):
    """Full image-generator panel for embedding in the KleinPC content area."""

    def __init__(self, parent: tk.Widget, on_exit=None):
        super().__init__(parent, bg=_BG)
        self._on_exit = on_exit
        self._photo: Optional[object] = None
        self._busy  = False
        self._build()

    def _build(self) -> None:
        # ── Header ────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=_HDR_BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text=" IMAGE GENERATOR ", bg=_HDR_BG, fg=_FG,
                 font=("Consolas", 10, "bold")).pack(side="left", padx=8, pady=6)

        # ── Prompt row ────────────────────────────────────────────────
        pr = tk.Frame(self, bg=_BG)
        pr.pack(fill="x", padx=8, pady=(10, 4))
        tk.Label(pr, text="PROMPT", bg=_BG, fg=_DIM,
                 font=("Consolas", 8)).pack(anchor="w")
        self._prompt_var = tk.StringVar()
        tk.Entry(
            pr, textvariable=self._prompt_var,
            bg=_BG, fg=_FG, insertbackground=_FG,
            font=("Consolas", 9), relief="flat",
            highlightthickness=1, highlightbackground=_BORDER,
            highlightcolor=_FG,
        ).pack(fill="x", pady=(2, 0))

        # ── Style + Generate row ──────────────────────────────────────
        ctrl = tk.Frame(self, bg=_BG)
        ctrl.pack(fill="x", padx=8, pady=4)
        tk.Label(ctrl, text="STYLE", bg=_BG, fg=_DIM,
                 font=("Consolas", 8)).pack(side="left")
        self._style_var = tk.StringVar(value="kleinbottle")
        style_menu = tk.OptionMenu(ctrl, self._style_var, *_STYLES)
        style_menu.configure(
            bg=_BG, fg=_FG, activebackground=_HDR_BG, activeforeground=_FG,
            highlightthickness=0, relief="flat", font=("Consolas", 9),
        )
        style_menu["menu"].configure(bg=_BG, fg=_FG, activebackground=_HDR_BG)
        style_menu.pack(side="left", padx=(6, 16))
        self._gen_btn = _mk_btn(ctrl, "[ Generate ]", self._generate)
        self._gen_btn.pack(side="left")

        # ── Status ────────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Ready.")
        tk.Label(self, textvariable=self._status_var,
                 bg=_BG, fg=_DIM, font=("Consolas", 8),
                 anchor="w").pack(fill="x", padx=10, pady=(0, 4))

        # ── Image canvas ──────────────────────────────────────────────
        self._canvas = tk.Canvas(self, bg="#000000",
                                 highlightthickness=1, highlightbackground=_BORDER)
        self._canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._canvas.bind("<Configure>", self._on_resize)

    # ── Generation ────────────────────────────────────────────────────

    def _generate(self) -> None:
        prompt = self._prompt_var.get().strip()
        if not prompt:
            self._status("Enter a prompt first.")
            return
        if self._busy:
            self._status("Already generating…")
            return
        self._busy = True
        self._gen_btn.configure(state="disabled")
        self._status("Queuing…")
        threading.Thread(
            target=self._worker,
            args=(prompt, self._style_var.get()),
            daemon=True,
        ).start()

    def _worker(self, prompt: str, style: str) -> None:
        import uuid
        try:
            root = _pipeline_root()
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from pipeline.client import collect_images, queue_prompt, wait_for_completion  # type: ignore[import]
            from pipeline.styles import build_workflow  # type: ignore[import]

            self.after(0, lambda: self._status("Building workflow…"))
            workflow, _ = build_workflow(prompt, style)
            pid = queue_prompt(workflow, str(uuid.uuid4()))
            self.after(0, lambda: self._status(f"Generating (id={pid[:8]}…)"))
            result = wait_for_completion(pid, timeout=300.0)

            _OUT_DIR.mkdir(parents=True, exist_ok=True)
            tmp = _OUT_DIR / "_tmp"
            tmp.mkdir(exist_ok=True)
            saved = collect_images(result, tmp)
            if saved:
                dest = _OUT_DIR / saved[0].name
                shutil.move(str(saved[0]), str(dest))
                self.after(0, lambda p=dest: self._show(p))
                self.after(0, lambda: self._status(f"Saved → {dest.name}"))
            else:
                self.after(0, lambda: self._status("No image returned."))
        except Exception as exc:
            msg = str(exc)[:120]
            self.after(0, lambda: self._status(f"Error: {msg}"))
        finally:
            self._busy = False
            self.after(0, lambda: self._gen_btn.configure(state="normal"))

    # ── Display ───────────────────────────────────────────────────────

    def _show(self, path: Path) -> None:
        if not _PILLOW:
            self._status("Pillow not installed — pip install pillow")
            return
        try:
            w = self._canvas.winfo_width()
            h = self._canvas.winfo_height()
            if w < 2 or h < 2:
                self.after(50, lambda: self._show(path))
                return
            img = _PilImage.open(path)  # type: ignore[union-attr]
            iw, ih = img.size
            scale = min(w / iw, h / ih)
            img = img.resize((int(iw * scale), int(ih * scale)), _NEAREST)  # type: ignore[union-attr]
            self._photo = _PilImageTk.PhotoImage(img)  # type: ignore[union-attr]
            self._canvas.delete("all")
            self._canvas.create_image(w // 2, h // 2, anchor="center", image=self._photo)
            self._last_path = path
        except Exception as exc:
            self._status(f"Display error: {exc}")

    def _on_resize(self, _=None) -> None:
        if hasattr(self, "_last_path") and self._last_path:
            self._show(self._last_path)

    def _status(self, text: str) -> None:
        self._status_var.set(text)


# ── KleinApp registration ─────────────────────────────────────────────

class ImageGenerator(KleinApp):
    title       = "Image Generator"
    description = "Generate images with ComfyUI via the KleinBOTTLE pipeline."

    def commands(self):  # type: ignore[override]
        return []

    def create(self, parent: tk.Widget, on_exit) -> tk.Widget:  # type: ignore[override]
        return ImageGenPane(parent, on_exit=on_exit)
