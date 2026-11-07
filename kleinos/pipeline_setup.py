"""
kleinos/pipeline_setup.py

One-time HITL setup gate for the image-generation pipeline.

Shown instead of any image-gen-dependent UI when the user has not yet
configured the pipeline.  On completion it persists the choice to
data/kleinos_config.json and calls on_complete().

Two paths:
  A) I have ComfyUI installed — browse for main.py, save path
  B) I manage ComfyUI myself  — just confirm host:port defaults

A sub-step checks whether the pipeline client submodule is present and
offers to initialise it (git submodule update --init) if it is not.
"""
from __future__ import annotations

import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Callable

_KB_ROOT = Path(__file__).resolve().parent.parent

_BG     = "#010a01"
_BORDER = "#003300"
_FG     = "#00cc33"
_DIM    = "#005500"
_HDR_BG = "#001a00"
_WARN   = "#cc6600"
_ERR    = "#cc3300"

_DOT_OK  = "#00cc33"
_DOT_BAD = "#cc3300"
_DOT_BUSY= "#cc6600"

_COMFYUI_GUIDE = "https://github.com/comfyanonymous/ComfyUI#installing"


def _mk_btn(parent: tk.Widget, text: str, command,
            fg: str = _FG, font_size: int = 9) -> tk.Button:
    return tk.Button(
        parent, text=text, bg=_BG, fg=fg,
        activebackground=_HDR_BG, activeforeground=_FG,
        relief="flat", font=("Consolas", font_size, "bold"),
        cursor="hand2", command=command,
        disabledforeground=_DIM,
    )


def _label(parent: tk.Widget, text: str, fg: str = _DIM,
           size: int = 9, bold: bool = False) -> tk.Label:
    weight = "bold" if bold else "normal"
    return tk.Label(parent, text=text, bg=_BG, fg=fg,
                    font=("Consolas", size, weight), anchor="w")


class PipelineSetupPane(tk.Frame):
    """
    Full-frame setup wizard.  Embed it in a container; it fills the parent.
    Call on_complete() once the user saves.
    """

    def __init__(self, parent: tk.Widget,
                 on_complete: Callable[[], None]):
        super().__init__(parent, bg=_BG)
        self._on_complete = on_complete
        self._submod_ok   = False
        self._build()
        # Async submodule check so the UI appears instantly
        threading.Thread(target=self._check_submodule, daemon=True).start()

    # ── Layout ────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Header
        hdr = tk.Frame(self, bg=_HDR_BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text=" IMAGE PIPELINE SETUP", bg=_HDR_BG, fg=_FG,
                 font=("Consolas", 10, "bold")).pack(side="left", padx=8, pady=7)

        # Scroll-able body (use a plain Frame — content is short)
        body = tk.Frame(self, bg=_BG)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # Intro
        _label(body,
               "Image generation in KleinBOTTLE requires ComfyUI.",
               fg=_FG, size=9, bold=True).pack(anchor="w", pady=(0, 2))
        _label(body,
               "Complete this setup once to enable all image-dependent features.",
               fg=_DIM).pack(anchor="w", pady=(0, 10))

        # ── Step 1: Submodule ─────────────────────────────────────────
        s1 = tk.LabelFrame(body, text=" STEP 1 — Pipeline client ",
                           bg=_BG, fg=_DIM,
                           font=("Consolas", 8), relief="flat",
                           highlightthickness=1, highlightbackground=_BORDER)
        s1.pack(fill="x", pady=(0, 10))

        row1 = tk.Frame(s1, bg=_BG)
        row1.pack(fill="x", padx=8, pady=6)

        self._sub_dot = tk.Label(row1, text="●", bg=_BG, fg=_DOT_BUSY,
                                 font=("Consolas", 10))
        self._sub_dot.pack(side="left")

        self._sub_lbl = tk.Label(row1, text="  Checking…", bg=_BG, fg=_DIM,
                                 font=("Consolas", 8), anchor="w")
        self._sub_lbl.pack(side="left", fill="x", expand=True)

        self._sub_init_btn = _mk_btn(row1, "[ Initialize submodule ]",
                                     self._init_submodule, fg=_WARN, font_size=8)
        # Only shown when submodule is missing

        self._sub_note = tk.Label(s1,
            text="  tools/image-pipeline — the Python client that talks to ComfyUI.",
            bg=_BG, fg=_DIM, font=("Consolas", 7), anchor="w")
        self._sub_note.pack(anchor="w", padx=8, pady=(0, 4))

        # ── Step 2: ComfyUI ───────────────────────────────────────────
        s2 = tk.LabelFrame(body, text=" STEP 2 — ComfyUI ",
                           bg=_BG, fg=_DIM,
                           font=("Consolas", 8), relief="flat",
                           highlightthickness=1, highlightbackground=_BORDER)
        s2.pack(fill="x", pady=(0, 10))

        inner = tk.Frame(s2, bg=_BG)
        inner.pack(fill="x", padx=8, pady=8)

        # Radio choice
        self._mode_var = tk.StringVar(value="path")

        rb_path = tk.Radiobutton(
            inner, text="I have ComfyUI installed — provide the path",
            variable=self._mode_var, value="path",
            bg=_BG, fg=_FG, selectcolor=_BG,
            activebackground=_BG, activeforeground=_FG,
            font=("Consolas", 9), command=self._on_mode_change,
        )
        rb_path.pack(anchor="w")

        # Path sub-row
        self._path_frame = tk.Frame(inner, bg=_BG)
        self._path_frame.pack(fill="x", padx=16, pady=(2, 6))
        _label(self._path_frame, "main.py path:", size=8).pack(anchor="w")
        prow = tk.Frame(self._path_frame, bg=_BG)
        prow.pack(fill="x", pady=(2, 0))
        self._path_var = tk.StringVar()
        self._path_entry = tk.Entry(
            prow, textvariable=self._path_var,
            bg=_BG, fg=_FG, insertbackground=_FG,
            font=("Consolas", 8), relief="flat",
            highlightthickness=1, highlightbackground=_BORDER,
            highlightcolor=_FG, width=50,
        )
        self._path_entry.pack(side="left", fill="x", expand=True)
        _mk_btn(prow, "Browse", self._browse, font_size=8).pack(
            side="left", padx=(6, 0))

        tk.Frame(inner, bg=_BORDER, height=1).pack(fill="x", pady=6)

        rb_manual = tk.Radiobutton(
            inner, text="I'll manage ComfyUI myself  (already running or I start it)",
            variable=self._mode_var, value="manual",
            bg=_BG, fg=_FG, selectcolor=_BG,
            activebackground=_BG, activeforeground=_FG,
            font=("Consolas", 9), command=self._on_mode_change,
        )
        rb_manual.pack(anchor="w")

        # Host:port row (always visible, used by both modes)
        hp_row = tk.Frame(inner, bg=_BG)
        hp_row.pack(anchor="w", padx=16, pady=(4, 2))
        _label(hp_row, "Host ", size=8).pack(side="left")
        self._host_var = tk.StringVar(value="127.0.0.1")
        tk.Entry(hp_row, textvariable=self._host_var,
                 bg=_BG, fg=_FG, insertbackground=_FG,
                 font=("Consolas", 8), relief="flat",
                 highlightthickness=1, highlightbackground=_BORDER,
                 width=14).pack(side="left")
        _label(hp_row, "   Port ", size=8).pack(side="left")
        self._port_var = tk.StringVar(value="8188")
        tk.Entry(hp_row, textvariable=self._port_var,
                 bg=_BG, fg=_FG, insertbackground=_FG,
                 font=("Consolas", 8), relief="flat",
                 highlightthickness=1, highlightbackground=_BORDER,
                 width=6).pack(side="left")

        guide_row = tk.Frame(inner, bg=_BG)
        guide_row.pack(anchor="w", padx=16, pady=(6, 0))
        _label(guide_row, "Don't have ComfyUI? ", size=8, fg=_DIM).pack(side="left")
        link = tk.Label(guide_row,
                        text="Open install guide ↗",
                        bg=_BG, fg=_FG,
                        font=("Consolas", 8, "underline"),
                        cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda _: self._open_guide())

        # ── Error / info line ─────────────────────────────────────────
        self._msg_var = tk.StringVar()
        self._msg_lbl = tk.Label(body, textvariable=self._msg_var,
                                 bg=_BG, fg=_ERR,
                                 font=("Consolas", 8), anchor="w",
                                 wraplength=500)
        self._msg_lbl.pack(anchor="w", pady=(0, 6))

        # ── Save button ───────────────────────────────────────────────
        self._save_btn = _mk_btn(body, "[ ✓  Save & Continue ]",
                                 self._save, fg=_FG, font_size=10)
        self._save_btn.pack(anchor="w")

        self._on_mode_change()

    # ── Submodule check ───────────────────────────────────────────────

    def _check_submodule(self) -> None:
        from kleinos.pipeline_client import is_present
        ok = is_present()
        self.after(0, lambda: self._update_submodule_ui(ok))

    def _update_submodule_ui(self, ok: bool) -> None:
        self._submod_ok = ok
        if ok:
            self._sub_dot.configure(fg=_DOT_OK)
            self._sub_lbl.configure(
                text="  PRESENT  (tools/image-pipeline/)", fg=_FG)
            self._sub_init_btn.pack_forget()
        else:
            self._sub_dot.configure(fg=_DOT_BAD)
            self._sub_lbl.configure(
                text="  MISSING — submodule not initialised", fg=_ERR)
            self._sub_init_btn.pack(side="right", padx=(0, 4))

    def _init_submodule(self) -> None:
        self._sub_dot.configure(fg=_DOT_BUSY)
        self._sub_lbl.configure(text="  Initialising…", fg=_DIM)
        self._sub_init_btn.configure(state="disabled")
        self._set_msg("", err=False)
        threading.Thread(target=self._run_submodule_init, daemon=True).start()

    def _run_submodule_init(self) -> None:
        try:
            result = subprocess.run(
                ["git", "submodule", "update", "--init",
                 "tools/image-pipeline"],
                cwd=str(_KB_ROOT),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                self.after(0, lambda: self._update_submodule_ui(True))
            else:
                err = (result.stderr or result.stdout or "unknown error").strip()[:200]
                self.after(0, lambda: self._set_msg(
                    f"git submodule init failed: {err}", err=True))
                self.after(0, lambda: self._update_submodule_ui(False))
        except FileNotFoundError:
            self.after(0, lambda: self._set_msg(
                "git not found — initialise the submodule manually: "
                "git submodule update --init tools/image-pipeline",
                err=True))
            self.after(0, lambda: self._update_submodule_ui(False))
        except Exception as exc:
            self.after(0, lambda: self._set_msg(str(exc)[:200], err=True))
            self.after(0, lambda: self._update_submodule_ui(False))

    # ── UI helpers ────────────────────────────────────────────────────

    def _on_mode_change(self) -> None:
        if self._mode_var.get() == "path":
            self._path_frame.pack(fill="x", padx=16, pady=(2, 6))
        else:
            self._path_frame.pack_forget()

    def _browse(self) -> None:
        p = filedialog.askopenfilename(
            title="Locate ComfyUI main.py",
            filetypes=[("Python file", "*.py"), ("All files", "*.*")],
            initialdir=str(Path.home()),
        )
        if p:
            self._path_var.set(p)

    def _open_guide(self) -> None:
        import webbrowser
        webbrowser.open(_COMFYUI_GUIDE)

    def _set_msg(self, text: str, *, err: bool = True) -> None:
        self._msg_var.set(text)
        self._msg_lbl.configure(fg=_ERR if err else _FG)

    # ── Save ──────────────────────────────────────────────────────────

    def _save(self) -> None:
        self._set_msg("")
        mode = self._mode_var.get()

        # Validate ComfyUI path in path-mode
        if mode == "path":
            p = self._path_var.get().strip()
            if not p:
                self._set_msg("Enter the path to ComfyUI main.py.")
                return
            if not Path(p).exists():
                self._set_msg(f"File not found: {p}")
                return

        # Validate port
        try:
            port = int(self._port_var.get())
        except ValueError:
            self._set_msg("Port must be a number.")
            return

        host = self._host_var.get().strip() or "127.0.0.1"

        # Persist
        try:
            from kleinos import config as _cfg
            from kleinos.pipeline_client import mark_configured
            cfg = _cfg.load()
            ip = cfg.setdefault("image_pipeline", {})
            ip["comfyui_host"] = host
            ip["comfyui_port"] = port
            if mode == "path":
                ip["comfyui_path"] = self._path_var.get().strip()
            _cfg.save(cfg)
            mark_configured()
        except Exception as exc:
            self._set_msg(f"Could not save config: {exc}")
            return

        self._on_complete()
