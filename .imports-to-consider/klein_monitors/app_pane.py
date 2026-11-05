"""
klein_monitors/app_pane.py

AppPane — renders any KleinApp inside a standardized chrome:
  [Title bar]
  [Button row — one button per command]
  [Scrollable output area]
  [Status bar]

No Tkinter knowledge needed to write an app.
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from klein_monitors.klein_app import KleinApp

_BG       = "#010a01"
_CHROME   = "#003311"
_BORDER   = "#005522"
_BTN_BG   = "#0a2010"
_BTN_ACT  = "#0d3a1a"
_TEXT_FG  = "#00dd33"
_STATUS   = "#050e05"
_FONT     = ("Consolas", 9)
_FONT_TTL = ("Consolas", 10, "bold")


class AppPane(tk.Frame):
    """
    Fixed chrome shell that renders any KleinApp.

    Usage:
        pane = AppPane(parent, app=MyApp())
        pane.pack(fill="both", expand=True)
    """

    def __init__(self, parent: tk.Widget, *, app: "KleinApp"):
        super().__init__(parent, bg=_BG, bd=0, highlightthickness=0)
        self._app = app
        self._build()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def load_app(self, app: "KleinApp") -> None:
        """Swap in a different app at runtime."""
        self._app = app
        self._title_var.set(app.title)
        self._rebuild_buttons()
        self._output("--- " + app.title + " ---")

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # Title bar
        self._title_var = tk.StringVar(value=self._app.title)
        title_bar = tk.Frame(self, bg=_CHROME, bd=0)
        title_bar.pack(fill="x")
        tk.Label(
            title_bar,
            textvariable=self._title_var,
            bg=_CHROME,
            fg="white",
            font=_FONT_TTL,
            padx=6,
            pady=3,
        ).pack(side="left")

        # Button row
        self._btn_frame = tk.Frame(self, bg=_STATUS, bd=0)
        self._btn_frame.pack(fill="x", pady=(1, 0))
        self._rebuild_buttons()

        # Separator
        tk.Frame(self, bg=_BORDER, height=1).pack(fill="x")

        # Output area
        self._text = tk.Text(
            self,
            bg=_BG,
            fg=_TEXT_FG,
            font=_FONT,
            relief="flat",
            bd=0,
            wrap="word",
            state="disabled",
            cursor="arrow",
            highlightthickness=0,
        )
        scroll = tk.Scrollbar(self, command=self._text.yview, bg=_STATUS, troughcolor=_STATUS)
        self._text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._text.pack(fill="both", expand=True, padx=4, pady=4)

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(
            self,
            textvariable=self._status_var,
            bg=_STATUS,
            fg="#445577",
            font=("Consolas", 8),
            anchor="w",
            padx=4,
        ).pack(fill="x", side="bottom")

        # Welcome
        self._output(f"=== {self._app.title} ===\nSelect a command below.")

    def _rebuild_buttons(self) -> None:
        for w in self._btn_frame.winfo_children():
            w.destroy()
        for label, cmd in self._app.commands():
            btn = tk.Button(
                self._btn_frame,
                text=label,
                command=lambda c=cmd, l=label: self._run(l, c),
                bg=_BTN_BG,
                fg=_TEXT_FG,
                activebackground=_BTN_ACT,
                activeforeground=_TEXT_FG,
                font=_FONT,
                relief="flat",
                padx=8,
                pady=2,
                cursor="hand2",
                bd=0,
            )
            btn.pack(side="left", padx=2, pady=2)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run(self, label: str, cmd) -> None:
        self._status_var.set(f"Running: {label}…")
        self.update_idletasks()
        try:
            result = cmd()
        except Exception as exc:
            result = f"[Error] {exc}"
        self._output(f"> {label}\n{result}")
        self._status_var.set("Ready")

    def _output(self, text: str) -> None:
        self._text.config(state="normal")
        self._text.insert("end", text.rstrip("\n") + "\n\n")
        self._text.see("end")
        self._text.config(state="disabled")
