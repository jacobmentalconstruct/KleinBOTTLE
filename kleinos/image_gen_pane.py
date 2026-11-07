"""
kleinos/image_gen_pane.py

In-PC image generator — KleinApp that wraps the image-generation-pipeline
submodule (tools/image-pipeline/) with a simple GUI.

Pipeline lifecycle:
  The status bar shows ● OFFLINE / STARTING / ONLINE and exposes
  Start / Stop / Reset buttons.  Generate is disabled until ONLINE.
  A background poll every 4 s keeps the state current so externally-
  launched ComfyUI instances are detected automatically.

Generation flow (when ONLINE):
  User clicks Generate → queue workflow → stream status → display result
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
from kleinos.pipeline_client import (
    ensure_on_path as _pipeline_ensure_on_path,
    is_configured as _pipeline_is_configured,
)

try:
    from PIL import Image as _PilImage, ImageEnhance as _PilEnhance  # type: ignore[import-untyped]
    from PIL import ImageFilter as _PilFilter, ImageOps as _PilOps  # type: ignore[import-untyped]
    from PIL import ImageTk as _PilImageTk  # type: ignore[import-untyped]
    _NEAREST = getattr(getattr(_PilImage, "Resampling", _PilImage), "NEAREST", 0)
    _PILLOW = True
except ImportError:
    _PilImage = _PilImageTk = _PilEnhance = _PilFilter = _PilOps = None  # type: ignore[assignment]
    _NEAREST = 0
    _PILLOW = False

_BG     = "#010a01"
_BORDER = "#003300"
_FG     = "#00cc33"
_DIM    = "#005500"
_HDR_BG = "#001a00"
_WARN   = "#cc6600"

_DOT_OFFLINE  = "#cc3300"
_DOT_STARTING = "#cc6600"
_DOT_ONLINE   = "#00cc33"

_OUT_DIR  = Path(__file__).resolve().parent.parent / "data" / "generated"
_STYLES   = ("default", "kleinbottle", "projectmapper")

# Experimental filters available in the filter bar.
# Each entry: (label, internal_key)
_FILTERS = (
    ("Phosphor",   "phosphor"),
    ("Grayscale",  "gray"),
    ("Sepia",      "sepia"),
    ("Sharpen",    "sharpen"),
    ("Edge",       "edge"),
    ("Invert",     "invert"),
    ("ASCII",      "ascii"),
)

# Lines in ComfyUI stdout that mean the server is ready
_READY_SIGNALS = (
    "To see the GUI go to:",
    "Starting server",
    "Serving on",
)

_POLL_MS = 4000   # pipeline health-check interval


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


def _mk_btn(parent: tk.Widget, text: str, command, fg: str = _FG,
            font_size: int = 9) -> tk.Button:
    return tk.Button(
        parent, text=text, bg=_BG, fg=fg,
        activebackground="#001a00", activeforeground=_FG,
        relief="flat", font=("Consolas", font_size, "bold"),
        cursor="hand2", command=command,
        disabledforeground=_DIM,
    )


class ImageGenPane(tk.Frame):
    """Full image-generator panel for embedding in the KleinPC content area."""

    def __init__(self, parent: tk.Widget, on_exit=None):
        super().__init__(parent, bg=_BG)
        self._on_exit      = on_exit
        self._photo: Optional[object] = None
        self._busy         = False
        self._proc: Optional[subprocess.Popen] = None  # type: ignore[type-arg]
        self._pending_prompt: Optional[tuple[str, str]] = None
        self._orig_img: Optional[object] = None
        self._active_filter: Optional[str] = None
        self._filter_btns: dict[str, tk.Button] = {}
        self._pl_state     = "offline"   # "offline" | "starting" | "online" | "stopping"
        self._poll_after: Optional[str] = None
        self._ascii_start_ts: float = 0.0
        self._status_lbl: Optional[tk.Label] = None
        self._toast_win: Optional[tk.Toplevel] = None  # type: ignore[name-defined]
        self._toast_after: Optional[str] = None

        if not _pipeline_is_configured():
            self._show_setup_gate()
        else:
            self._build_main()

    def _show_setup_gate(self) -> None:
        from kleinos.pipeline_setup import PipelineSetupPane
        gate = PipelineSetupPane(self, on_complete=self._on_setup_complete)
        gate.pack(fill="both", expand=True)

    def _on_setup_complete(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        self._build_main()

    # ── Layout ────────────────────────────────────────────────────────

    def _build_main(self) -> None:
        # Header + pipeline status bar on one row
        hdr = tk.Frame(self, bg=_HDR_BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text=" IMAGE GENERATOR ", bg=_HDR_BG, fg=_FG,
                 font=("Consolas", 10, "bold")).pack(side="left", padx=8, pady=6)

        # Pipeline status cluster (right side of header)
        pl_bar = tk.Frame(hdr, bg=_HDR_BG)
        pl_bar.pack(side="right", padx=8, pady=4)

        self._pl_dot = tk.Label(pl_bar, text="●", bg=_HDR_BG, fg=_DOT_OFFLINE,
                                font=("Consolas", 10))
        self._pl_dot.pack(side="left", padx=(0, 4))

        self._pl_lbl = tk.Label(pl_bar, text="OFFLINE", bg=_HDR_BG, fg=_DIM,
                                font=("Consolas", 8, "bold"), width=8, anchor="w")
        self._pl_lbl.pack(side="left", padx=(0, 8))

        self._pl_start_btn = _mk_btn(pl_bar, "[ Start ]",  self._start_pipeline,
                                     fg=_FG, font_size=8)
        self._pl_start_btn.pack(side="left", padx=2)

        self._pl_stop_btn  = _mk_btn(pl_bar, "[ Stop ]",   self._stop_pipeline,
                                     fg=_WARN, font_size=8)
        self._pl_stop_btn.pack(side="left", padx=2)

        self._pl_reset_btn = _mk_btn(pl_bar, "[ Reset ]",  self._restart_pipeline,
                                     fg=_DIM, font_size=8)
        self._pl_reset_btn.pack(side="left", padx=2)

        # Prompt
        pr = tk.Frame(self, bg=_BG)
        pr.pack(fill="x", padx=8, pady=(10, 4))
        tk.Label(pr, text="PROMPT", bg=_BG, fg=_DIM,
                 font=("Consolas", 8)).pack(anchor="w")
        self._prompt_var = tk.StringVar()
        self._prompt_entry = tk.Entry(
            pr, textvariable=self._prompt_var,
            bg=_BG, fg=_FG, insertbackground=_FG,
            font=("Consolas", 9), relief="flat",
            highlightthickness=1, highlightbackground=_BORDER,
            highlightcolor=_FG,
            disabledbackground=_BG, disabledforeground=_DIM,
        )
        self._prompt_entry.pack(fill="x", pady=(2, 0))

        # Style + Generate row
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
        self._status_var = tk.StringVar(value="Waiting for pipeline…")
        self._status_lbl = tk.Label(self, textvariable=self._status_var,
                                    bg=_BG, fg=_DIM, font=("Consolas", 8),
                                    anchor="w")
        self._status_lbl.pack(fill="x", padx=10, pady=(0, 2))

        # Experimental filter bar (Pillow-only)
        if _PILLOW:
            fbar = tk.Frame(self, bg=_BG)
            fbar.pack(fill="x", padx=8, pady=(0, 2))
            tk.Label(fbar, text="FILTER", bg=_BG, fg=_DIM,
                     font=("Consolas", 7)).pack(side="left", padx=(0, 6))
            for label, key in _FILTERS:
                btn = tk.Button(
                    fbar, text=label,
                    bg=_BG, fg=_DIM,
                    activebackground=_HDR_BG, activeforeground=_FG,
                    relief="flat", font=("Consolas", 8), cursor="hand2",
                    command=lambda k=key: self._toggle_filter(k),
                )
                btn.pack(side="left", padx=2)
                self._filter_btns[key] = btn
            tk.Button(
                fbar, text="✕ Reset",
                bg=_BG, fg=_DIM,
                activebackground=_HDR_BG, activeforeground=_FG,
                relief="flat", font=("Consolas", 8), cursor="hand2",
                command=self._reset_filter,
            ).pack(side="left", padx=(8, 0))

        # Launch log — hidden until pipeline is starting
        self._log_frame = tk.Frame(self, bg=_BG)
        self._log_text: Optional[tk.Text] = None

        # Image canvas
        self._canvas = tk.Canvas(self, bg="#000000",
                                 highlightthickness=1, highlightbackground=_BORDER)
        self._canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._canvas.bind("<Configure>", self._on_resize)

        # Apply initial disabled state, then kick off async ping
        self._apply_pl_state()
        threading.Thread(target=self._async_poll, daemon=True).start()

    # ── Pipeline state machine ────────────────────────────────────────

    def _set_pl_state(self, state: str) -> None:
        self._pl_state = state
        self._apply_pl_state()

    def _apply_pl_state(self) -> None:
        """Update all UI to match self._pl_state. Must run on main thread."""
        s = self._pl_state
        dot_color = {
            "offline":  _DOT_OFFLINE,
            "starting": _DOT_STARTING,
            "online":   _DOT_ONLINE,
            "stopping": _DOT_STARTING,
        }.get(s, _DOT_OFFLINE)
        label_text = s.upper()

        self._pl_dot.configure(fg=dot_color)
        self._pl_lbl.configure(text=label_text,
                               fg=_FG if s == "online" else _DIM)

        self._pl_start_btn.configure(
            state="normal" if s == "offline" else "disabled")
        self._pl_stop_btn.configure(
            state="normal" if s == "online" else "disabled",
            fg=_WARN if s == "online" else _DIM)
        self._pl_reset_btn.configure(
            state="normal" if s == "online" else "disabled",
            fg=_FG if s == "online" else _DIM)

        gen_ok = s == "online" and not self._busy
        self._gen_btn.configure(
            state="normal" if gen_ok else "disabled",
            fg=_FG if gen_ok else _DIM)
        self._prompt_entry.configure(
            state="normal" if s == "online" else "disabled")

        if s == "online" and self._status_var.get() == "Waiting for pipeline…":
            self._status_var.set("Ready.")

    # ── Pipeline lifecycle ────────────────────────────────────────────

    def _start_pipeline(self) -> None:
        exe = _comfyui_exe()
        if not exe:
            self._status("Set comfyui_path in Settings → image_pipeline before starting.")
            return
        self._set_pl_state("starting")
        self._show_log()
        self._append_log(f"Launch: {exe}")
        threading.Thread(target=self._launch_worker, args=(exe,), daemon=True).start()

    def _stop_pipeline(self) -> None:
        self._set_pl_state("stopping")
        self._status("Stopping pipeline…")
        threading.Thread(target=self._stop_worker, daemon=True).start()

    def _restart_pipeline(self) -> None:
        exe = _comfyui_exe()
        if not exe:
            self._status("Set comfyui_path in Settings → image_pipeline.")
            return
        self._set_pl_state("stopping")
        self._status("Restarting pipeline…")
        threading.Thread(target=self._restart_worker, args=(exe,), daemon=True).start()

    def _stop_worker(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        self.after(0, lambda: self._set_pl_state("offline"))
        self.after(0, lambda: self._status("Pipeline stopped."))
        self.after(0, self._hide_log)

    def _restart_worker(self, exe: str) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        self.after(0, lambda: self._set_pl_state("starting"))
        self.after(0, self._show_log)
        self.after(0, lambda: self._append_log("─── restarting ───"))
        self._launch_worker(exe)

    def _launch_worker(self, exe: str) -> None:
        try:
            exe_path = Path(exe)
            cmd = ([sys.executable, str(exe_path)]
                   if exe_path.suffix.lower() == ".py"
                   else [str(exe_path)])

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
                # Echo each line to the status bar so startup progress is visible
                self.after(0, lambda l=line: self._status(l[:90]))
                if not ready and any(sig in line for sig in _READY_SIGNALS):
                    ready = True
                    self.after(0, self._on_pipeline_ready)

            if not ready:
                self.after(0, lambda: self._status("Pipeline exited unexpectedly."))
                self.after(0, lambda: self._set_pl_state("offline"))
        except Exception as exc:
            msg = str(exc)[:120]
            self.after(0, lambda: self._status(f"Launch error: {msg}"))
            self.after(0, lambda: self._set_pl_state("offline"))

    def _on_pipeline_ready(self) -> None:
        self._append_log("─── Pipeline ready ───")
        self._set_pl_state("online")
        self._status("Pipeline online.")
        if self._pending_prompt:
            prompt, style = self._pending_prompt
            self._pending_prompt = None
            self._run_generation(prompt, style)

    # ── Background health poll ────────────────────────────────────────

    def _async_poll(self) -> None:
        """Run in a background thread; reschedules itself via after()."""
        alive = _ping()
        self.after(0, lambda: self._on_poll_result(alive))

    def _on_poll_result(self, alive: bool) -> None:
        if alive and self._pl_state == "offline":
            self._set_pl_state("online")
            self._status("Pipeline online.")
        elif not alive and self._pl_state == "online":
            self._set_pl_state("offline")
            self._status("Pipeline went offline.")
        self._poll_after = self.after(
            _POLL_MS,
            lambda: threading.Thread(target=self._async_poll, daemon=True).start(),
        )

    # ── Generation ────────────────────────────────────────────────────

    def _on_generate_click(self) -> None:
        if self._pl_state != "online":
            self._status("Start the pipeline first.")
            return
        prompt = self._prompt_var.get().strip()
        if not prompt:
            self._status("Enter a prompt first.")
            return
        if self._busy:
            self._status("Already generating…")
            return
        self._run_generation(prompt, self._style_var.get())

    def _run_generation(self, prompt: str, style: str) -> None:
        self._busy = True
        self._apply_pl_state()
        threading.Thread(
            target=self._worker,
            args=(prompt, style),
            daemon=True,
        ).start()

    def _worker(self, prompt: str, style: str) -> None:
        try:
            if not _pipeline_ensure_on_path():
                self.after(0, lambda: self._status("Pipeline not found — check submodule."))
                return
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
        except ImportError as exc:
            pkg = str(exc).replace("No module named ", "").strip("'\"")
            msg = f"Missing dependency: {pkg} — pip install {pkg}"
            self.after(0, lambda: self._status(msg))
        except Exception as exc:
            msg = str(exc)[:120]
            self.after(0, lambda: self._status(f"Error: {msg}"))
        finally:
            self._busy = False
            self.after(0, self._apply_pl_state)

    # ── Launch log ────────────────────────────────────────────────────

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
            img = _PilImage.open(path).convert("RGB")  # type: ignore[union-attr]
            self._orig_img = img.copy()
            self._last_path = path
            self._active_filter = None
            self._update_filter_buttons()
            self._render(img, w, h)
        except Exception as exc:
            self._status(f"Display error: {exc}")

    def _render(self, img: object, w: int, h: int) -> None:
        iw, ih = img.size  # type: ignore[union-attr]
        scale = min(w / iw, h / ih)
        img = img.resize((int(iw * scale), int(ih * scale)), _NEAREST)  # type: ignore[union-attr]
        self._photo = _PilImageTk.PhotoImage(img)  # type: ignore[union-attr]
        self._canvas.delete("all")
        self._canvas.create_image(w // 2, h // 2, anchor="center", image=self._photo)

    # ── Experimental filters ──────────────────────────────────────────

    def _toggle_filter(self, key: str) -> None:
        if self._orig_img is None:
            self._status_warn("No image loaded — generate one first.")
            return
        if self._active_filter == key:
            self._reset_filter()
            return
        self._active_filter = key
        self._update_filter_buttons()
        if key == "ascii":
            self._status("ASCII: converting in background…")
            self._ascii_start_ts = __import__("time").monotonic()
            self._show_toast(
                "ASCII: converting in background…\n"
                "Result will appear in the canvas when done.")
            threading.Thread(
                target=self._ascii_worker,
                args=(self._orig_img,),
                daemon=True,
            ).start()
            self._ascii_progress_tick()
            return
        try:
            filtered = self._run_filter(self._orig_img, key)
            w = self._canvas.winfo_width()
            h = self._canvas.winfo_height()
            self._render(filtered, w, h)
            self._status(f"Filter: {key}")
        except Exception as exc:
            self._status(f"Filter error: {exc}")

    def _ascii_progress_tick(self) -> None:
        """Update status every 2 s while ASCII filter is active."""
        if self._active_filter != "ascii":
            return
        import time
        elapsed = int(time.monotonic() - getattr(self, "_ascii_start_ts", time.monotonic()))
        self._status(f"ASCII: converting… {elapsed}s elapsed (may take 60-120 s on CPU)")
        self.after(2000, self._ascii_progress_tick)

    def _ascii_worker(self, orig_img: object) -> None:
        try:
            from kleinos.pipeline_client import convert_available, ensure_on_path
            if not convert_available():
                self.after(0, lambda: self._status_warn(
                    "ASCII filter needs torch + numpy — run: pip install torch numpy"))
                # Leave button lit so user sees the click registered; don't auto-reset
                return
            ensure_on_path()
            from pipeline.convert import to_ascii  # type: ignore[import]
            import os
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                orig_img.save(tmp_path)  # type: ignore[union-attr]
                w = self._canvas.winfo_width() or 320
                cols = max(40, min(120, w // 7))
                art = to_ascii(tmp_path, width=cols, iterations=150)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

            img = self._ascii_to_image(art)
            self.after(0, lambda i=img: self._render(
                i, self._canvas.winfo_width(), self._canvas.winfo_height()))
            self.after(0, lambda: self._status("Filter: ascii — done"))
            self.after(0, lambda: self._show_toast(
                "✓ ASCII conversion done — image ready.", auto_ms=4000))
        except ImportError as exc:
            msg = str(exc)
            self.after(0, lambda: self._status_warn(f"ASCII import error: {msg}"))
            self.after(0, lambda m=msg: self._show_toast(
                f"ASCII error: {m}", auto_ms=5000))
            self.after(0, self._reset_filter)
        except Exception as exc:
            msg = str(exc)[:120]
            self.after(0, lambda: self._status_warn(f"ASCII error: {msg}"))
            self.after(0, lambda m=msg: self._show_toast(
                f"ASCII error: {m}", auto_ms=5000))
            self.after(0, self._reset_filter)

    @staticmethod
    def _ascii_to_image(art: str) -> object:
        """Render ASCII art string to a PIL image using monospace font in KleinOS green."""
        lines = art.splitlines()
        cols  = max((len(l) for l in lines), default=1)
        rows  = len(lines) or 1
        ch_w, ch_h = 7, 13
        img_w, img_h = cols * ch_w + 4, rows * ch_h + 4
        img = _PilImage.new("RGB", (img_w, img_h), color=(1, 10, 1))  # type: ignore[union-attr]
        from PIL import ImageDraw, ImageFont  # type: ignore[import]
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("Consola.ttf", 12)
        except Exception:
            font = ImageFont.load_default()
        for row_i, line in enumerate(lines):
            draw.text((2, 2 + row_i * ch_h), line, fill=(0, 204, 51), font=font)
        return img

    def _reset_filter(self) -> None:
        if self._orig_img is None:
            return
        self._close_toast()
        self._active_filter = None
        self._update_filter_buttons()
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        self._render(self._orig_img, w, h)
        self._status(f"Filter reset.  {getattr(self, '_last_path', Path()).name}")

    def _update_filter_buttons(self) -> None:
        for key, btn in self._filter_btns.items():
            if key == self._active_filter:
                btn.configure(fg=_FG, relief="groove")
            else:
                btn.configure(fg=_DIM, relief="flat")

    @staticmethod
    def _run_filter(img: object, key: str) -> object:  # type: ignore[return]
        """Apply a named filter to a PIL RGB image; return a new image."""
        if key == "phosphor":
            gray = img.convert("L")  # type: ignore[union-attr]
            r = gray.point(lambda v: int(v * 0.00))
            g = gray.point(lambda v: int(v * 1.00))
            b = gray.point(lambda v: int(v * 0.27))
            return _PilImage.merge("RGB", (r, g, b))  # type: ignore[union-attr]
        if key == "gray":
            return img.convert("L").convert("RGB")  # type: ignore[union-attr]
        if key == "sepia":
            gray = img.convert("L")  # type: ignore[union-attr]
            r = gray.point(lambda v: min(255, int(v * 1.08)))
            g = gray.point(lambda v: int(v * 0.85))
            b = gray.point(lambda v: int(v * 0.66))
            return _PilImage.merge("RGB", (r, g, b))  # type: ignore[union-attr]
        if key == "sharpen":
            return _PilEnhance.Sharpness(img).enhance(3.0)  # type: ignore[union-attr]
        if key == "edge":
            return img.convert("L").filter(  # type: ignore[union-attr]
                _PilFilter.FIND_EDGES).convert("RGB")  # type: ignore[union-attr]
        if key == "invert":
            return _PilOps.invert(img)  # type: ignore[union-attr]
        return img

    def _on_resize(self, _=None) -> None:
        if self._orig_img is None:
            return
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w < 2 or h < 2:
            return
        if self._active_filter and self._active_filter != "ascii":
            try:
                img = self._run_filter(self._orig_img, self._active_filter)
            except Exception:
                img = self._orig_img
        else:
            img = self._orig_img
        self._render(img, w, h)

    # ── Toast notifications ───────────────────────────────────────────

    def _show_toast(self, msg: str, *, auto_ms: int = 0) -> None:
        """Display a small floating toast anchored to the bottom-right of the app window."""
        self._close_toast()
        try:
            root = self.winfo_toplevel()
            win = tk.Toplevel(root)
            win.overrideredirect(True)
            win.configure(bg=_BG)
            win.attributes("-topmost", True)  # type: ignore[arg-type]

            tw, th = 320, 56
            rx = root.winfo_rootx() + root.winfo_width()  - tw - 10
            ry = root.winfo_rooty() + root.winfo_height() - th - 10
            win.geometry(f"{tw}x{th}+{rx}+{ry}")

            outer = tk.Frame(win, bg=_BORDER, padx=1, pady=1)
            outer.pack(fill="both", expand=True)
            inner = tk.Frame(outer, bg=_BG)
            inner.pack(fill="both", expand=True, padx=1, pady=1)

            tk.Label(inner, text=msg, bg=_BG, fg=_FG,
                     font=("Consolas", 8), wraplength=270,
                     anchor="w", justify="left").pack(
                side="left", fill="both", expand=True, padx=6, pady=4)
            tk.Button(inner, text="✕", bg=_BG, fg=_DIM,
                      activebackground=_HDR_BG, activeforeground=_FG,
                      relief="flat", font=("Consolas", 8), cursor="hand2",
                      command=self._close_toast).pack(side="right", padx=4)

            self._toast_win = win
            if auto_ms > 0:
                self._toast_after = self.after(auto_ms, self._close_toast)
        except Exception:
            pass   # never crash the main flow over a notification

    def _close_toast(self) -> None:
        if self._toast_after is not None:
            try:
                self.after_cancel(self._toast_after)
            except Exception:
                pass
            self._toast_after = None
        if self._toast_win is not None:
            try:
                self._toast_win.destroy()
            except Exception:
                pass
            self._toast_win = None

    def _status(self, text: str) -> None:
        self._status_var.set(text)
        if self._status_lbl is not None:
            self._status_lbl.configure(fg=_DIM)

    def _status_warn(self, text: str) -> None:
        self._status_var.set(text)
        if self._status_lbl is not None:
            self._status_lbl.configure(fg=_WARN)


# ── KleinApp registration ─────────────────────────────────────────────

class ImageGenerator(KleinApp):
    title       = "Image Generator"
    description = "Generate images with ComfyUI via the KleinBOTTLE pipeline."

    def commands(self):  # type: ignore[override]
        return []

    def create(self, parent: tk.Widget, on_exit) -> tk.Widget:  # type: ignore[override]
        return ImageGenPane(parent, on_exit=on_exit)
