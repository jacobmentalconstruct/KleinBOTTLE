"""
kleinos/pipeline_setup.py

One-time HITL setup gate for the image-generation-pipeline.

Shown instead of any image-gen-dependent UI when the user has not yet
configured the pipeline.  On completion it persists choices to
data/kleinos_config.json and calls on_complete().

Dependency:  image-generation-pipeline (pip package)
  pip install git+https://github.com/jacobmentalconstruct/image-generation-pipeline.git

Setup steps:
  1. Check whether `pipeline` is importable; offer one-click pip install if not
  2. Configure ComfyUI connection (host:port)
     Optionally set a ComfyUI launch path so KleinBOTTLE can auto-start it
"""
from __future__ import annotations

import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Callable

_BG     = "#010a01"
_BORDER = "#003300"
_FG     = "#00cc33"
_DIM    = "#005500"
_HDR_BG = "#001a00"
_WARN   = "#cc6600"
_ERR    = "#cc3300"

_DOT_OK   = "#00cc33"
_DOT_BAD  = "#cc3300"
_DOT_BUSY = "#cc6600"

_INSTALL_URL  = (
    "git+https://github.com/jacobmentalconstruct/image-generation-pipeline.git"
)
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


def _lbl(parent: tk.Widget, text: str, fg: str = _DIM,
         size: int = 9, bold: bool = False) -> tk.Label:
    return tk.Label(parent, text=text, bg=_BG, fg=fg,
                    font=("Consolas", size, "bold" if bold else "normal"),
                    anchor="w")


class PipelineSetupPane(tk.Frame):
    """
    Full-frame setup wizard.  Embed in a container; it fills the parent.
    Calls on_complete() once the user saves.
    """

    def __init__(self, parent: tk.Widget, on_complete: Callable[[], None]):
        super().__init__(parent, bg=_BG)
        self._on_complete = on_complete
        self._pkg_ok = False
        self._installing = False
        self._build()
        threading.Thread(target=self._check_package, daemon=True).start()

    # ── Layout ────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Header
        hdr = tk.Frame(self, bg=_HDR_BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text=" IMAGE PIPELINE SETUP", bg=_HDR_BG, fg=_FG,
                 font=("Consolas", 10, "bold")).pack(side="left", padx=8, pady=7)

        body = tk.Frame(self, bg=_BG)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # Intro
        _lbl(body,
             "KleinBOTTLE uses image-generation-pipeline for all image features.",
             fg=_FG, bold=True).pack(anchor="w", pady=(0, 2))
        _lbl(body,
             "Complete this setup once to continue.",
             fg=_DIM).pack(anchor="w", pady=(0, 10))

        # ── Step 1: package ───────────────────────────────────────────
        s1 = tk.LabelFrame(body, text=" STEP 1 — Pipeline package ",
                           bg=_BG, fg=_DIM, font=("Consolas", 8),
                           relief="flat",
                           highlightthickness=1, highlightbackground=_BORDER)
        s1.pack(fill="x", pady=(0, 10))

        top1 = tk.Frame(s1, bg=_BG)
        top1.pack(fill="x", padx=8, pady=(6, 2))

        self._pkg_dot = tk.Label(top1, text="●", bg=_BG, fg=_DOT_BUSY,
                                 font=("Consolas", 10))
        self._pkg_dot.pack(side="left")

        self._pkg_lbl = tk.Label(top1, text="  Checking…", bg=_BG, fg=_DIM,
                                 font=("Consolas", 8), anchor="w")
        self._pkg_lbl.pack(side="left", fill="x", expand=True)

        self._install_btn = _mk_btn(top1, "[ pip install ]",
                                    self._install_package,
                                    fg=_WARN, font_size=8)
        # Only shown when package is absent

        # pip install URL display
        url_row = tk.Frame(s1, bg=_BG)
        url_row.pack(anchor="w", padx=8, pady=(0, 4))
        _lbl(url_row, "pip install ", size=7, fg=_DIM).pack(side="left")
        tk.Label(url_row, text=_INSTALL_URL, bg=_BG, fg=_DIM,
                 font=("Consolas", 7), anchor="w").pack(side="left")

        # "Already installed elsewhere" path override
        alt_row = tk.Frame(s1, bg=_BG)
        alt_row.pack(fill="x", padx=8, pady=(0, 6))
        _lbl(alt_row, "Already installed? Point to its folder: ",
             size=7, fg=_DIM).pack(side="left")
        self._alt_path_var = tk.StringVar()
        tk.Entry(alt_row, textvariable=self._alt_path_var,
                 bg=_BG, fg=_FG, insertbackground=_FG,
                 font=("Consolas", 7), relief="flat",
                 highlightthickness=1, highlightbackground=_BORDER,
                 width=28).pack(side="left", fill="x", expand=True, padx=(4, 0))
        _mk_btn(alt_row, "Browse", self._browse_alt,
                font_size=7).pack(side="left", padx=(4, 0))
        _mk_btn(alt_row, "Use", self._use_alt_path,
                fg=_WARN, font_size=7).pack(side="left", padx=(4, 0))

        # Install log — hidden until install is running
        self._log_frame = tk.Frame(s1, bg=_BG)
        self._log_text: tk.Text | None = None

        # ── Step 2: ComfyUI connection ────────────────────────────────
        s2 = tk.LabelFrame(body, text=" STEP 2 — ComfyUI connection ",
                           bg=_BG, fg=_DIM, font=("Consolas", 8),
                           relief="flat",
                           highlightthickness=1, highlightbackground=_BORDER)
        s2.pack(fill="x", pady=(0, 10))

        inner = tk.Frame(s2, bg=_BG)
        inner.pack(fill="x", padx=8, pady=8)

        _lbl(inner,
             "ComfyUI must be running for image generation to work.",
             fg=_DIM, size=8).pack(anchor="w", pady=(0, 6))

        # Host / port
        hp = tk.Frame(inner, bg=_BG)
        hp.pack(anchor="w")
        _lbl(hp, "Host ", size=8).pack(side="left")
        self._host_var = tk.StringVar(value="127.0.0.1")
        tk.Entry(hp, textvariable=self._host_var,
                 bg=_BG, fg=_FG, insertbackground=_FG,
                 font=("Consolas", 8), relief="flat",
                 highlightthickness=1, highlightbackground=_BORDER,
                 width=14).pack(side="left")
        _lbl(hp, "   Port ", size=8).pack(side="left")
        self._port_var = tk.StringVar(value="8188")
        tk.Entry(hp, textvariable=self._port_var,
                 bg=_BG, fg=_FG, insertbackground=_FG,
                 font=("Consolas", 8), relief="flat",
                 highlightthickness=1, highlightbackground=_BORDER,
                 width=6).pack(side="left")

        # ComfyUI auto-launch (optional)
        tk.Frame(inner, bg=_BORDER, height=1).pack(fill="x", pady=(10, 6))

        _lbl(inner,
             "Auto-launch  (optional — leave blank to start ComfyUI yourself)",
             fg=_DIM, size=8).pack(anchor="w")

        launch_row = tk.Frame(inner, bg=_BG)
        launch_row.pack(fill="x", pady=(4, 0))
        _lbl(launch_row, "ComfyUI main.py: ", size=8).pack(side="left")
        self._launch_var = tk.StringVar()
        tk.Entry(launch_row, textvariable=self._launch_var,
                 bg=_BG, fg=_FG, insertbackground=_FG,
                 font=("Consolas", 8), relief="flat",
                 highlightthickness=1, highlightbackground=_BORDER,
                 width=36).pack(side="left", fill="x", expand=True)
        _mk_btn(launch_row, "Browse", self._browse,
                font_size=8).pack(side="left", padx=(6, 0))

        guide_row = tk.Frame(inner, bg=_BG)
        guide_row.pack(anchor="w", pady=(6, 0))
        _lbl(guide_row, "Don't have ComfyUI? ", size=7, fg=_DIM).pack(side="left")
        link = tk.Label(guide_row, text="Install guide ↗",
                        bg=_BG, fg=_FG,
                        font=("Consolas", 7, "underline"), cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda _: self._open_guide())

        # ── Error / info ──────────────────────────────────────────────
        self._msg_var = tk.StringVar()
        self._msg_lbl = tk.Label(body, textvariable=self._msg_var,
                                 bg=_BG, fg=_ERR,
                                 font=("Consolas", 8), anchor="w",
                                 wraplength=520)
        self._msg_lbl.pack(anchor="w", pady=(0, 6))

        # ── Save button ───────────────────────────────────────────────
        self._save_btn = _mk_btn(body, "[ ✓  Save & Continue ]",
                                 self._save, fg=_FG, font_size=10)
        self._save_btn.pack(anchor="w")

    # ── Package check ─────────────────────────────────────────────────

    def _check_package(self) -> None:
        from kleinos.pipeline_client import is_present
        ok = is_present()
        self.after(0, lambda: self._update_pkg_ui(ok))

    def _update_pkg_ui(self, ok: bool) -> None:
        self._pkg_ok = ok
        if ok:
            self._pkg_dot.configure(fg=_DOT_OK)
            self._pkg_lbl.configure(text="  INSTALLED", fg=_FG)
            self._install_btn.pack_forget()
        else:
            self._pkg_dot.configure(fg=_DOT_BAD)
            self._pkg_lbl.configure(text="  NOT FOUND", fg=_ERR)
            self._install_btn.pack(side="right", padx=(0, 4))

    # ── pip install ───────────────────────────────────────────────────

    def _install_package(self) -> None:
        if self._installing:
            return
        self._installing = True
        self._install_btn.configure(state="disabled")
        self._pkg_dot.configure(fg=_DOT_BUSY)
        self._pkg_lbl.configure(text="  Installing…", fg=_WARN)
        self._show_log()
        self._append_log(f"pip install {_INSTALL_URL}")
        self._set_msg("")
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self) -> None:
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", _INSTALL_URL],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for raw in proc.stdout:  # type: ignore[union-attr]
                line = raw.rstrip()
                self.after(0, lambda l=line: self._append_log(l))
            proc.wait()
            if proc.returncode == 0:
                self.after(0, lambda: self._update_pkg_ui(True))
                self.after(0, lambda: self._set_msg(
                    "Pipeline installed successfully.", err=False))
            else:
                self.after(0, lambda: self._set_msg(
                    "pip install failed — see log above.", err=True))
                self.after(0, lambda: self._update_pkg_ui(False))
        except Exception as exc:
            self.after(0, lambda: self._set_msg(str(exc)[:200], err=True))
            self.after(0, lambda: self._update_pkg_ui(False))
        finally:
            self._installing = False

    # ── Install log ───────────────────────────────────────────────────

    def _show_log(self) -> None:
        if self._log_text is not None:
            return
        self._log_frame.pack(fill="x", padx=8, pady=(0, 4))
        self._log_text = tk.Text(
            self._log_frame,
            height=8, bg="#000a00", fg=_DIM,
            font=("Consolas", 7), relief="flat",
            state="disabled", wrap="word",
            highlightthickness=1, highlightbackground=_BORDER,
        )
        self._log_text.pack(fill="x")

    def _append_log(self, line: str) -> None:
        if self._log_text is None:
            return
        self._log_text.configure(state="normal")
        self._log_text.insert("end", line + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    # ── Helpers ───────────────────────────────────────────────────────

    def _browse(self) -> None:
        p = filedialog.askopenfilename(
            title="Locate ComfyUI main.py  (for auto-launch)",
            filetypes=[("Python file", "*.py"), ("All files", "*.*")],
            initialdir=str(Path.home()),
        )
        if p:
            self._launch_var.set(p)

    def _browse_alt(self) -> None:
        """Browse for a directory that contains an existing pipeline/ package."""
        d = filedialog.askdirectory(
            title="Select folder containing the pipeline package  "
                  "(the folder that has pipeline/ inside it)",
            initialdir=str(Path.home()),
        )
        if d:
            self._alt_path_var.set(d)

    def _use_alt_path(self) -> None:
        """Validate the alternate path and mark the package as found."""
        d = self._alt_path_var.get().strip()
        if not d:
            self._set_msg("Enter or browse to the pipeline package folder first.")
            return
        pkg = Path(d) / "pipeline" / "__init__.py"
        if not pkg.exists():
            self._set_msg(
                f"No pipeline package found at {d}\n"
                "Expected: <folder>/pipeline/__init__.py")
            return
        # Persist the custom path so pipeline_client.py picks it up
        try:
            from kleinos import config as _cfg
            cfg = _cfg.load()
            cfg.setdefault("image_pipeline", {})["path"] = d
            _cfg.save(cfg)
        except Exception as exc:
            self._set_msg(f"Could not save path: {exc}")
            return
        self._set_msg("Pipeline found at custom path.", err=False)
        self._update_pkg_ui(True)

    def _open_guide(self) -> None:
        import webbrowser
        webbrowser.open(_COMFYUI_GUIDE)

    def _set_msg(self, text: str, *, err: bool = True) -> None:
        self._msg_var.set(text)
        self._msg_lbl.configure(fg=_ERR if err else _FG)

    # ── Save ──────────────────────────────────────────────────────────

    def _save(self) -> None:
        self._set_msg("")

        if not self._pkg_ok:
            self._set_msg(
                "Pipeline package is not installed. "
                "Click [ pip install ] above first.")
            return

        try:
            port = int(self._port_var.get())
        except ValueError:
            self._set_msg("Port must be a number.")
            return

        host  = self._host_var.get().strip() or "127.0.0.1"
        launch = self._launch_var.get().strip()

        if launch and not Path(launch).exists():
            self._set_msg(f"ComfyUI launch path not found: {launch}")
            return

        try:
            from kleinos import config as _cfg
            from kleinos.pipeline_client import mark_configured
            cfg = _cfg.load()
            ip  = cfg.setdefault("image_pipeline", {})
            ip["comfyui_host"]  = host
            ip["comfyui_port"]  = port
            ip["comfyui_path"]  = launch
            _cfg.save(cfg)
            mark_configured()
        except Exception as exc:
            self._set_msg(f"Could not save config: {exc}")
            return

        self._on_complete()
