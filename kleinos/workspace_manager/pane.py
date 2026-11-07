"""Native KleinOS surface for ProjectMapper — folder picker + AdapterSession actions."""
from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Callable

from kleinos.palette import (
    BG, BG2, BTN_ACT, BTN_BG, FG, FG_DIM, FG_HI, FG_ON, SEP, WARN,
)
from kleinos.workspace_manager.installer import has_sidecar
from kleinos.workspace_manager.session_bridge import (
    PMBridge, _format_outcome, _format_scan,
)

_PROJECTIONS = ("tree", "filedump", "combined", "manifest")


# ── Tooltip ────────────────────────────────────────────────────────────

def _tip(widget: tk.Widget, text: str) -> None:
    """Attach a simple hover tooltip to a widget."""
    from kleinos.palette import HEAD, FG_ON as _FG_ON

    win: list[tk.Toplevel] = []

    def show(event: tk.Event) -> None:
        if win:
            return
        t = tk.Toplevel(widget)
        t.wm_overrideredirect(True)
        t.wm_geometry(f"+{event.x_root + 14}+{event.y_root - 2}")
        t.wm_attributes("-topmost", True)
        tk.Label(t, text=text, bg=HEAD, fg=_FG_ON,
                 font=("Consolas", 8), relief="flat", padx=8, pady=4,
                 wraplength=240, justify="left").pack()
        win.append(t)

    def hide(_: tk.Event) -> None:
        if win:
            win[0].destroy()
            win.clear()

    widget.bind("<Enter>", show, add=True)
    widget.bind("<Leave>", hide, add=True)


class ProjectContextPane(tk.Frame):
    """KleinOS pane that opens a project folder and calls ProjectMapper actions."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        bridge: PMBridge,
        on_exit: Callable[[], None],
    ) -> None:
        super().__init__(parent, bg=BG)
        self._bridge = bridge
        self._on_exit = on_exit
        self._busy = False
        self._build()
        self._refresh_ui()

    # ── Layout ─────────────────────────────────────────────────────────

    def _build(self) -> None:
        # ── Folder picker ──
        top = tk.Frame(self, bg=BG, pady=4)
        top.pack(fill="x", padx=8)

        tk.Label(
            top, text="Folder:", bg=BG, fg=FG_DIM, font=("Consolas", 9),
        ).pack(side="left")

        self._folder_var = tk.StringVar()
        self._folder_entry = tk.Entry(
            top, textvariable=self._folder_var,
            bg=BG2, fg=FG, insertbackground=FG,
            relief="flat", font=("Consolas", 9),
        )
        self._folder_entry.pack(side="left", fill="x", expand=True, padx=(4, 4))
        self._folder_entry.bind("<Return>", lambda _: self._on_folder_confirm())

        self._browse_btn = tk.Button(
            top, text="Browse",
            bg=BTN_BG, fg=FG, activebackground=BTN_ACT,
            relief="flat", font=("Consolas", 9), padx=6,
            command=self._browse,
        )
        self._browse_btn.pack(side="left")
        _tip(self._browse_btn, "Open folder picker")

        self._open_btn = tk.Button(
            top, text="Open",
            bg=BTN_BG, fg=FG, activebackground=BTN_ACT,
            relief="flat", font=("Consolas", 9), padx=6,
            command=self._on_folder_confirm,
        )
        self._open_btn.pack(side="left", padx=(4, 0))
        _tip(self._open_btn, "Open the selected folder (or press Enter in the path field)")

        tk.Frame(self, bg=SEP, height=1).pack(fill="x")

        # ── Status label ──
        self._status_var = tk.StringVar(value="No folder selected.")
        self._status_lbl = tk.Label(
            self, textvariable=self._status_var,
            bg=BG, fg=FG_DIM, font=("Consolas", 9), anchor="w",
            padx=10, pady=4,
        )
        self._status_lbl.pack(fill="x")

        # ── Action buttons (scan / compile / export) ──
        self._action_frame = tk.Frame(self, bg=BG, pady=4)
        # pack/pack_forget toggled by _refresh_ui

        self._scan_btn = tk.Button(
            self._action_frame, text="Scan",
            bg=BTN_BG, fg=FG, activebackground=BTN_ACT,
            relief="flat", font=("Consolas", 9), padx=8,
            command=lambda: self._run_action("scan"),
        )
        self._scan_btn.pack(side="left", padx=(0, 4))
        _tip(self._scan_btn, "Scan the project tree and list all tracked files")

        self._compile_btn = tk.Button(
            self._action_frame, text="Compile",
            bg=BTN_BG, fg=FG, activebackground=BTN_ACT,
            relief="flat", font=("Consolas", 9), padx=8,
            command=lambda: self._run_action("compile"),
        )
        self._compile_btn.pack(side="left", padx=(0, 4))
        _tip(self._compile_btn, "Compile a SQLite snapshot of the current project state")

        self._proj_var = tk.StringVar(value="combined")
        proj_menu = tk.OptionMenu(self._action_frame, self._proj_var, *_PROJECTIONS)
        proj_menu.config(
            bg=BTN_BG, fg=FG, activebackground=BTN_ACT,
            relief="flat", font=("Consolas", 9), padx=4, pady=0,
            highlightthickness=0, bd=0,
        )
        proj_menu["menu"].config(
            bg=BTN_BG, fg=FG, activebackground=BTN_ACT,
            font=("Consolas", 9),
        )
        proj_menu.pack(side="left")
        _tip(proj_menu, "Export format: tree (paths only) · filedump (file contents) · combined (tree + files) · manifest (metadata)")

        self._export_btn = tk.Button(
            self._action_frame, text="Export",
            bg=BTN_BG, fg=FG, activebackground=BTN_ACT,
            relief="flat", font=("Consolas", 9), padx=8,
            command=lambda: self._run_action("export"),
        )
        self._export_btn.pack(side="left", padx=(4, 0))
        _tip(self._export_btn, "Export the snapshot in the selected projection format")

        # ── Install strip (shown when folder set but no sidecar) ──
        self._install_frame = tk.Frame(self, bg=BG, pady=4)
        # pack/pack_forget toggled by _refresh_ui

        tk.Label(
            self._install_frame,
            text="No .project-mapper sidecar found.",
            bg=BG, fg=WARN, font=("Consolas", 9),
        ).pack(side="left", padx=(0, 8))

        self._install_btn = tk.Button(
            self._install_frame, text="Install ProjectMapper",
            bg=BTN_BG, fg=FG, activebackground=BTN_ACT,
            relief="flat", font=("Consolas", 9), padx=8,
            command=self._install,
        )
        self._install_btn.pack(side="left")
        _tip(self._install_btn, "Clone .project-mapper and pip-install it into this folder")

        tk.Frame(self, bg=SEP, height=1).pack(fill="x")

        # ── Scrolled output ──
        out_frame = tk.Frame(self, bg=BG)
        out_frame.pack(fill="both", expand=True)

        self._output = tk.Text(
            out_frame,
            bg=BG2, fg=FG, insertbackground=FG,
            font=("Consolas", 9), relief="flat",
            state="disabled", wrap="none",
        )
        vsb = tk.Scrollbar(
            out_frame, command=self._output.yview,
            bg=BG2, troughcolor=BG, activebackground=FG_DIM,
            relief="flat", width=10,
        )
        self._output.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._output.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=4)

        self._output.tag_configure("dim",  foreground=FG_DIM)
        self._output.tag_configure("warn", foreground=WARN)
        self._output.tag_configure("hi",   foreground=FG_HI)
        self._output.tag_configure("ok",   foreground=FG_ON)

        # ── Status bar ──
        tk.Frame(self, bg=SEP, height=1).pack(fill="x")
        self._bar_var = tk.StringVar(value="Ready.")
        tk.Label(
            self, textvariable=self._bar_var,
            bg=BG, fg=FG_DIM, font=("Consolas", 8), anchor="w",
            padx=8, pady=3,
        ).pack(fill="x", side="bottom")

    # ── State helpers ──────────────────────────────────────────────────

    def _refresh_ui(self) -> None:
        if self._bridge.is_open:
            root = self._bridge.root
            self._folder_var.set(str(root))
            self._status_var.set(f"● {root}")
            self._status_lbl.config(fg=FG_ON)
            self._action_frame.pack(fill="x", padx=8)
            self._install_frame.pack_forget()
        elif self._folder_var.get().strip():
            self._action_frame.pack_forget()
            self._install_frame.pack(fill="x", padx=8)
            self._status_lbl.config(fg=WARN)
        else:
            self._action_frame.pack_forget()
            self._install_frame.pack_forget()
            self._status_var.set("No folder selected.")
            self._status_lbl.config(fg=FG_DIM)

    def _set_busy(self, busy: bool, label: str = "") -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        for btn in (
            self._scan_btn, self._compile_btn, self._export_btn,
            self._install_btn, self._browse_btn, self._open_btn,
        ):
            btn.config(state=state)
        self._bar_var.set(label if label else "Ready.")

    # ── Folder picker ──────────────────────────────────────────────────

    def _browse(self) -> None:
        path = filedialog.askdirectory(title="Select Project Folder")
        if path:
            self._folder_var.set(path)
            self._on_folder_confirm()

    def _on_folder_confirm(self) -> None:
        raw = self._folder_var.get().strip()
        if not raw:
            return
        path = Path(raw)
        if not path.is_dir():
            self._status_var.set(f"✗ Not a directory: {raw}")
            self._status_lbl.config(fg=WARN)
            self._action_frame.pack_forget()
            self._install_frame.pack_forget()
            return

        if has_sidecar(path):
            try:
                self._bridge.open(path)
                self._append(f"Opened {path}\n", "hi")
                self._refresh_ui()
                self._bar_var.set(f"Session open: {path.name}")
            except Exception as exc:
                self._status_var.set(f"✗ {exc}")
                self._status_lbl.config(fg=WARN)
                self._append(f"[error] {exc}\n", "warn")
        else:
            self._status_var.set(f"○  {path}  — no .project-mapper")
            self._status_lbl.config(fg=WARN)
            self._refresh_ui()

    # ── Action runner ──────────────────────────────────────────────────

    def _run_action(self, name: str) -> None:
        if self._busy:
            return
        if not self._bridge.is_open:
            self._append(
                "[error] No session open. Select a folder with .project-mapper first.\n",
                "warn",
            )
            return

        if name == "scan":
            action, payload, label = "project.scan", {}, "Scanning…"
        elif name == "compile":
            action, payload, label = "snapshot.compile", {}, "Compiling snapshot…"
        else:
            proj = self._proj_var.get()
            action = "snapshot.export"
            payload = {"projection": proj}
            label = f"Exporting ({proj})…"

        self._set_busy(True, label)
        self._append(f"» {label}\n", "dim")

        def _worker() -> None:
            outcome = self._bridge.call(action, payload)
            self.after(0, self._on_action_done, name, outcome)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_action_done(self, name: str, outcome: dict) -> None:
        text = _format_scan(outcome) if name == "scan" else _format_outcome(outcome)
        tag = "warn" if outcome.get("status") == "failed" else "ok"
        self._append(text + "\n", tag)
        self._set_busy(False)

    # ── Install ────────────────────────────────────────────────────────

    def _install(self) -> None:
        raw = self._folder_var.get().strip()
        if not raw:
            return
        path = Path(raw)
        from kleinos.workspace_manager.installer import install

        self._set_busy(True, "Installing…")
        self._append(f"Installing .project-mapper into {path} …\n", "dim")

        def _on_progress(line: str) -> None:
            self.after(0, self._append, line + "\n", "dim")

        def _on_done(rev: str) -> None:
            def _finish() -> None:
                self._append(f"[ok] installed at rev {rev}\n", "hi")
                self._on_folder_confirm()
                self._set_busy(False)
            self.after(0, _finish)

        def _on_error(msg: str) -> None:
            def _finish() -> None:
                self._append(f"[error] {msg}\n", "warn")
                self._set_busy(False)
            self.after(0, _finish)

        install(path, _on_progress, _on_done, _on_error)

    # ── Output helper ──────────────────────────────────────────────────

    def _append(self, text: str, tag: str = "") -> None:
        self._output.config(state="normal")
        if tag:
            self._output.insert("end", text, tag)
        else:
            self._output.insert("end", text)
        self._output.see("end")
        self._output.config(state="disabled")
