"""Workspace Manager pane — custom Tkinter UI for KleinPC."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext
from typing import Callable, Optional

from kleinos.palette import (
    BG as _BG, BG2 as _BG2, CHROME as _CHROME, BORDER as _BORDER,
    BTN_BG as _BTN_BG, BTN_ACT as _BTN_ACT,
    FG as _FG, FG_ON as _FG_ON, FG_DIM as _FG_DIM,
)
from kleinos.workspace_manager.workspace import (
    WorkspaceDef, WorkspaceStore, log_event,
    validate_new_workspace, default_parent, new_workspace,
)
from kleinos.workspace_manager.installer import install as _install, launch as _launch
from kleinos.workspace_manager.process_registry import ProcessRegistry

_FONT    = ("Consolas", 9)
_FONT_HD = ("Consolas", 10, "bold")
_FONT_SM = ("Consolas", 8)
_POLL_MS = 2000


class WorkspacePane(tk.Frame):
    """Full-content-area UI for the Workspace Manager."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_exit: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent, bg=_BG, bd=0, highlightthickness=0)
        self._on_exit = on_exit
        self._store = WorkspaceStore()
        self._registry = ProcessRegistry()
        self._workspaces: list[WorkspaceDef] = []
        self._selected_ws: Optional[WorkspaceDef] = None
        self._installing = False
        self._build()
        self._refresh_list()
        self._poll()

    # ── Layout ─────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Header bar
        hdr = tk.Frame(self, bg=_CHROME)
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="Workspace Manager",
            bg=_CHROME, fg=_FG_ON, font=_FONT_HD, pady=5, padx=10, anchor="w",
        ).pack(side="left")
        if self._on_exit:
            tk.Button(
                hdr, text="✕", command=self._on_exit,
                bg=_CHROME, fg=_FG_DIM,
                activebackground=_BTN_ACT, activeforeground=_FG_ON,
                font=_FONT_SM, relief="flat", bd=0, cursor="hand2", padx=8,
            ).pack(side="right")

        # Two-column body
        body = tk.Frame(self, bg=_BG)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        left = tk.Frame(body, bg=_BG)
        left.pack(side="left", fill="both", expand=True)

        tk.Frame(body, bg=_BORDER, width=1).pack(side="left", fill="y", padx=6)

        right = tk.Frame(body, bg=_BG)
        right.pack(side="left", fill="both", expand=True)

        self._build_create_form(left)
        tk.Frame(left, bg=_BORDER, height=1).pack(fill="x", pady=6)
        self._build_ws_list(left)
        self._build_log(right)

        # Status bar
        self._status_var = tk.StringVar(value="Ready.")
        tk.Label(
            self, textvariable=self._status_var,
            bg=_BG2, fg=_FG_DIM, font=_FONT_SM, anchor="w", padx=8,
        ).pack(fill="x", side="bottom")

    def _build_create_form(self, parent: tk.Widget) -> None:
        tk.Label(
            parent, text="Create Workspace",
            bg=_BG, fg=_FG_ON, font=_FONT_HD, anchor="w",
        ).pack(fill="x")

        row1 = tk.Frame(parent, bg=_BG)
        row1.pack(fill="x", pady=2)
        tk.Label(row1, text="Name:", bg=_BG, fg=_FG, font=_FONT, width=8, anchor="w").pack(side="left")
        self._name_var = tk.StringVar()
        tk.Entry(
            row1, textvariable=self._name_var,
            bg=_BTN_BG, fg=_FG_ON, insertbackground=_FG_ON,
            font=_FONT, relief="flat", bd=1,
            highlightthickness=1, highlightcolor=_BORDER, highlightbackground=_BORDER,
        ).pack(side="left", fill="x", expand=True)

        row2 = tk.Frame(parent, bg=_BG)
        row2.pack(fill="x", pady=2)
        tk.Label(row2, text="Parent:", bg=_BG, fg=_FG, font=_FONT, width=8, anchor="w").pack(side="left")
        self._parent_var = tk.StringVar(value=str(default_parent()))
        tk.Entry(
            row2, textvariable=self._parent_var,
            bg=_BTN_BG, fg=_FG_ON, insertbackground=_FG_ON,
            font=_FONT, relief="flat", bd=1,
            highlightthickness=1, highlightcolor=_BORDER, highlightbackground=_BORDER,
        ).pack(side="left", fill="x", expand=True)
        tk.Button(
            row2, text="…", command=self._browse_parent,
            bg=_BTN_BG, fg=_FG, activebackground=_BTN_ACT, activeforeground=_FG_ON,
            font=_FONT_SM, relief="flat", bd=0, cursor="hand2", padx=6,
        ).pack(side="left", padx=(2, 0))

        self._create_btn = tk.Button(
            parent, text="Create + Install ProjectMapper",
            command=self._on_create,
            bg=_BTN_BG, fg=_FG_ON,
            activebackground=_BTN_ACT, activeforeground=_FG_ON,
            font=_FONT, relief="flat", bd=0, cursor="hand2", pady=4,
        )
        self._create_btn.pack(fill="x", pady=(4, 0))

    def _build_ws_list(self, parent: tk.Widget) -> None:
        tk.Label(
            parent, text="Workspaces",
            bg=_BG, fg=_FG_ON, font=_FONT_HD, anchor="w",
        ).pack(fill="x")

        frame = tk.Frame(parent, bg=_BG)
        frame.pack(fill="both", expand=True)

        sb = tk.Scrollbar(frame, orient="vertical", bg=_BG2, troughcolor=_BG)
        self._ws_listbox = tk.Listbox(
            frame,
            bg=_BTN_BG, fg=_FG_ON,
            selectbackground=_BTN_ACT, selectforeground=_FG_ON,
            font=_FONT_SM, relief="flat", bd=0, highlightthickness=0,
            yscrollcommand=sb.set,
        )
        sb.config(command=self._ws_listbox.yview)
        sb.pack(side="right", fill="y")
        self._ws_listbox.pack(side="left", fill="both", expand=True)
        self._ws_listbox.bind("<<ListboxSelect>>", self._on_ws_select)

        btns = tk.Frame(parent, bg=_BG)
        btns.pack(fill="x", pady=4)
        self._launch_btn = tk.Button(
            btns, text="Launch",
            command=self._on_launch,
            bg=_BTN_BG, fg=_FG_ON,
            activebackground=_BTN_ACT, activeforeground=_FG_ON,
            font=_FONT, relief="flat", bd=0, cursor="hand2",
            state="disabled", padx=8, pady=2,
        )
        self._launch_btn.pack(side="left", padx=(0, 4))
        self._proc_label = tk.Label(btns, text="", bg=_BG, fg=_FG_DIM, font=_FONT_SM)
        self._proc_label.pack(side="left")

    def _build_log(self, parent: tk.Widget) -> None:
        tk.Label(
            parent, text="Log",
            bg=_BG, fg=_FG_ON, font=_FONT_HD, anchor="w",
        ).pack(fill="x")
        self._log = scrolledtext.ScrolledText(
            parent,
            bg=_BTN_BG, fg=_FG, insertbackground=_FG_ON,
            font=_FONT_SM, relief="flat", bd=0,
            state="disabled", wrap="word",
        )
        self._log.pack(fill="both", expand=True)

    # ── Helpers ────────────────────────────────────────────────────────

    def _log_line(self, text: str) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _set_status(self, text: str) -> None:
        self._status_var.set(text)

    def _browse_parent(self) -> None:
        d = filedialog.askdirectory(
            title="Select parent directory",
            initialdir=self._parent_var.get() or str(default_parent()),
        )
        if d:
            self._parent_var.set(d)

    def _refresh_list(self) -> None:
        self._workspaces = self._store.load_all()
        self._ws_listbox.delete(0, "end")
        for ws in self._workspaces:
            mark = "✓" if ws.installed else "…"
            self._ws_listbox.insert("end", f"[{mark}] {ws.name}")
        # Restore selection
        if self._selected_ws:
            for i, ws in enumerate(self._workspaces):
                if ws.workspace_id == self._selected_ws.workspace_id:
                    self._ws_listbox.selection_set(i)
                    self._selected_ws = ws
                    break
        self._update_launch_btn()

    def _on_ws_select(self, _event: tk.Event) -> None:
        sel = self._ws_listbox.curselection()
        self._selected_ws = self._workspaces[sel[0]] if sel else None
        self._update_launch_btn()

    def _update_launch_btn(self) -> None:
        ws = self._selected_ws
        if ws and ws.installed:
            self._launch_btn.configure(state="normal")
        else:
            self._launch_btn.configure(state="disabled")

        if ws:
            running = self._registry.running_for_workspace(ws.workspace_id)
            if running:
                self._proc_label.configure(
                    text=f"● PID {running[0].pid} running", fg=_FG_ON,
                )
            else:
                self._proc_label.configure(text="○ stopped", fg=_FG_DIM)
        else:
            self._proc_label.configure(text="")

    # ── Actions ────────────────────────────────────────────────────────

    def _on_create(self) -> None:
        if self._installing:
            self._set_status("Installation already in progress.")
            return

        name = self._name_var.get().strip()
        parent_str = self._parent_var.get().strip()
        parent = Path(parent_str) if parent_str else default_parent()

        err = validate_new_workspace(name, parent)
        if err:
            self._log_line(f"[ERROR] {err}")
            self._set_status(f"Error: {err}")
            return

        ws = new_workspace(name, parent)
        self._store.add(ws)
        log_event("workspace.created", workspace_id=ws.workspace_id,
                  name=ws.name, root=ws.root)
        self._log_line(f"[+] Workspace '{ws.name}' created at {ws.root}")
        self._set_status(f"Installing into '{ws.name}' …")
        self._installing = True
        self._create_btn.configure(state="disabled")

        def _progress(msg: str) -> None:
            self.after(0, lambda m=msg: self._log_line(f"    {m}"))

        def _done(rev: str) -> None:
            ws.sidecar_rev = rev
            ws.installed = True
            self._store.update(ws)
            log_event("app.installed", workspace_id=ws.workspace_id, rev=rev)
            self.after(0, self._install_done)

        def _error(msg: str) -> None:
            log_event("app.failed", workspace_id=ws.workspace_id, error=msg)
            self.after(0, lambda m=msg: self._install_error(m))

        _install(Path(ws.root), _progress, _done, _error)

    def _install_done(self) -> None:
        self._installing = False
        self._create_btn.configure(state="normal")
        self._log_line("[✓] Installation complete.")
        self._set_status("Ready.")
        self._refresh_list()

    def _install_error(self, msg: str) -> None:
        self._installing = False
        self._create_btn.configure(state="normal")
        self._log_line(f"[✗] {msg}")
        self._set_status(f"Error: {msg}")

    def _on_launch(self) -> None:
        ws = self._selected_ws
        if not ws or not ws.installed:
            self._log_line("[!] Select an installed workspace first.")
            return

        self._log_line(f"[>] Launching ProjectMapper for '{ws.name}' …")

        def _err(msg: str) -> None:
            self.after(0, lambda m=msg: self._log_line(f"[✗] {m}"))

        proc = _launch(Path(ws.root), on_error=_err)
        if proc:
            record = self._registry.register(ws.workspace_id, proc)
            log_event("app.started", workspace_id=ws.workspace_id,
                      run_id=record.run_id, pid=record.pid)
            self._log_line(f"[✓] Started PID {proc.pid}")
            self._update_launch_btn()

    # ── Periodic poll ──────────────────────────────────────────────────

    def _poll(self) -> None:
        changed = self._registry.poll_all()
        for rec in changed:
            status = "stopped" if rec.exit_code == 0 else "failed"
            log_event(f"app.{status}", workspace_id=rec.workspace_id,
                      run_id=rec.run_id, exit_code=rec.exit_code)
            self._log_line(f"[·] PID {rec.pid} exited (code {rec.exit_code})")
        if changed:
            self._update_launch_btn()
        self.after(_POLL_MS, self._poll)
