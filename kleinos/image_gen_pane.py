"""
kleinos/image_gen_pane.py

In-PC image generator — KleinApp that wraps the image-generation-pipeline
submodule (tools/image-pipeline/) with a simple GUI.

Flow:
  1. User clicks Generate → health-check pings ComfyUI /system_stats
  2a. Pipeline alive   → queue workflow, stream status, display result
  2b. Pipeline offline → show Launch button + log area
  3. Launch → subprocess.Popen ComfyUI, stream stdout to log, detect ready
             → auto-trigger generation once ready
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import tkinter as tk
import urllib.request
import uuid
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
_WARN   = "#cc6600"

_OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "generated"
_STYLES  = ("default", "kleinbottle", "projectmapper")

# Lines in ComfyUI stdout that mean the server is ready
_READY_SIGNALS = (
    "To see the GUI go to:",
    "Starting server",
    "Serving on",
)


def _comfyui_base() -> str:
    try:
        from kleinos import config as _cfg
        c = _cfg.load().get("image_pipeline", {})
        host = c.get("comfyui_host", "127.0.0.1")
        port = int(c.get("comfyui_port", 8188))
    except Exception:
        host, port = "127.0.0.1", 8188
    return f"http://{host}:{port}"


def _comfyui_exe() -> str:
    try:
        from kleinos import config as _cfg
        return _cfg.load().get("image_pipeline", {}).get("comfyui_path", "")
    except Exception:
        return ""


def _ping() -> bool:
    """Return True if ComfyUI /system_stats responds within 1 s."""
    try:
        url = f"{_comfyui_base()}/system_stats"
        with urllib.request.urlopen(url, timeout=1.0):
            return True
    except Exception:
        return False


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
        self._on_exit   = on_exit
        self._photo: Optional[object] = None
        self._busy      = False
        self._launching = False
        self._proc: Optional[subprocess.Popen] = None  # type: ignore[type-arg]
        self._pending_prompt: Optional[tuple[str, str]] = None
        self._build()

    # ── Layout ────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Header
        hdr = tk.Frame(self, bg=_HDR_BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text=" IMAGE GENERATOR ", bg=_HDR_BG, fg=_FG,
                 font=("Consolas", 10, "bold")).pack(side="left", padx=8, pady=6)

        # Prompt
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

        # Style + action button row
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
        self._gen_btn = _mk_btn(ctrl, "[ Generate ]", self._on_generate_click)
        self._gen_btn.pack(side="left")

        # Status line
        self._status_var = tk.StringVar(value="Ready.")
        tk.Label(self, textvariable=self._status_var,
                 bg=_BG, fg=_DIM, font=("Consolas", 8),
                 anchor="w").pack(fill="x", padx=10, pady=(0, 2))

        # Launch log — hidden until pipeline needs starting
        self._log_frame = tk.Frame(self, bg=_BG)
        self._log_text: Optional[tk.Text] = None  # created lazily

        # Image canvas
        self._canvas = tk.Canvas(self, bg="#000000",
                                 highlightthickness=1, highlightbackground=_BORDER)
        self._canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._canvas.bind("<Configure>", self._on_resize)

    def _show_log(self) -> None:
        if self._log_text is not None:
            return
        self._log_frame.pack(fill="x", padx=8, pady=(0, 4), before=self._canvas)
        self._log_text = tk.Text(
            self._log_frame,
            height=6, bg="#000a00", fg=_DIM,
            font=("Consolas", 7), relief="flat",
            state="disabled", wrap="word",
            highlightthickness=1, highlightbackground=_BORDER,
        )
        self._log_text.pack(fill="x")

    def _hide_log(self) -> None:
        if self._log_text is None:
            return
        self._log_frame.pack_forget()
        self._log_text.destroy()
        self._log_text = None

    def _append_log(self, line: str) -> None:
        if self._log_text is None:
            return
        self._log_text.configure(state="normal")
        self._log_text.insert("end", line + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    # ── Entry point ───────────────────────────────────────────────────

    def _on_generate_click(self) -> None:
        prompt = self._prompt_var.get().strip()
        if not prompt:
            self._status("Enter a prompt first.")
            return
        if self._busy or self._launching:
            self._status("Already working…")
            return
        self._gen_btn.configure(state="disabled")
        self._status("Checking pipeline…")
        threading.Thread(
            target=self._check_then_generate,
            args=(prompt, self._style_var.get()),
            daemon=True,
        ).start()

    def _check_then_generate(self, prompt: str, style: str) -> None:
        if _ping():
            self.after(0, self._hide_log)
            self._run_generation(prompt, style)
        else:
            self.after(0, lambda: self._pipeline_offline(prompt, style))

    # ── Pipeline offline flow ─────────────────────────────────────────

    def _pipeline_offline(self, prompt: str, style: str) -> None:
        exe = _comfyui_exe()
        if not exe:
            self._status("Pipeline offline — set comfyui_path in config.")
            self._gen_btn.configure(text="[ Generate ]", command=self._on_generate_click,
                                    state="normal", fg=_FG)
            return

        self._status("Pipeline offline.")
        self._show_log()
        self._append_log("ComfyUI is not running.")
        self._append_log(f"Launch target: {exe}")
        self._append_log("Click [ Launch Pipeline ] to start.")

        self._gen_btn.configure(
            text="[ Launch Pipeline ]",
            fg=_WARN,
            command=lambda: self._launch_and_generate(exe, prompt, style),
            state="normal",
        )

    # ── Launch + monitor ──────────────────────────────────────────────

    def _launch_and_generate(self, exe: str, prompt: str, style: str) -> None:
        self._launching = True
        self._pending_prompt = (prompt, style)
        self._gen_btn.configure(state="disabled")
        self._status("Launching pipeline…")
        threading.Thread(
            target=self._launch_worker,
            args=(exe,),
            daemon=True,
        ).start()

    def _launch_worker(self, exe: str) -> None:
        try:
            # Determine python executable or run as script
            exe_path = Path(exe)
            if exe_path.suffix.lower() == ".py":
                cmd = [sys.executable, str(exe_path)]
            else:
                cmd = [str(exe_path)]

            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(exe_path.parent),
            )

            ready = False
            for raw_line in self._proc.stdout:  # type: ignore[union-attr]
                line = raw_line.rstrip()
                self.after(0, lambda l=line: self._append_log(l))
                self.after(0, lambda l=line: self._status(l[:80]))
                if not ready and any(sig in line for sig in _READY_SIGNALS):
                    ready = True
                    self.after(0, self._on_pipeline_ready)

            # Process ended without ready signal
            if not ready:
                self.after(0, lambda: self._status("Pipeline exited unexpectedly."))
                self.after(0, lambda: self._gen_btn.configure(
                    text="[ Generate ]", fg=_FG,
                    command=self._on_generate_click, state="normal",
                ))
        except Exception as exc:
            msg = str(exc)[:120]
            self.after(0, lambda: self._status(f"Launch error: {msg}"))
            self.after(0, lambda: self._gen_btn.configure(
                text="[ Generate ]", fg=_FG,
                command=self._on_generate_click, state="normal",
            ))
        finally:
            self._launching = False

    def _on_pipeline_ready(self) -> None:
        self._status("Pipeline ready. Generating…")
        self._append_log("─── Pipeline ready ───")
        # Restore normal button, then auto-trigger with pending prompt
        self._gen_btn.configure(text="[ Generate ]", fg=_FG,
                                command=self._on_generate_click)
        if self._pending_prompt:
            prompt, style = self._pending_prompt
            self._pending_prompt = None
            self._run_generation(prompt, style)

    # ── Generation worker ─────────────────────────────────────────────

    def _run_generation(self, prompt: str, style: str) -> None:
        self._busy = True
        self._gen_btn.configure(state="disabled")
        threading.Thread(
            target=self._worker,
            args=(prompt, style),
            daemon=True,
        ).start()

    def _worker(self, prompt: str, style: str) -> None:
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
                self.after(0, self._hide_log)
            else:
                self.after(0, lambda: self._status("No image returned."))
        except Exception as exc:
            msg = str(exc)[:120]
            self.after(0, lambda: self._status(f"Error: {msg}"))
        finally:
            self._busy = False
            self.after(0, lambda: self._gen_btn.configure(
                text="[ Generate ]", fg=_FG,
                command=self._on_generate_click, state="normal",
            ))

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
