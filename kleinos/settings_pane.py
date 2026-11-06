"""
kleinos/settings_pane.py

SettingsPane — category management panel for the KleinOS sidebar.
Opened from the ⚙ Settings button; callbacks are supplied by KleinPC.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

_BG          = "#010a01"
_CHROME      = "#003311"
_BORDER      = "#005522"
_BTN_BG      = "#0a2010"
_BTN_ACT     = "#0d3a1a"
_BTN_DEL     = "#2a0808"
_BTN_DEL_ACT = "#4a1010"
_TEXT_FG     = "#00dd33"
_TEXT_DIM    = "#1a4a1a"
_TEXT_HI     = "#aaffaa"
_STATUS      = "#050e05"
_FONT        = ("Consolas", 9)
_FONT_B      = ("Consolas", 9, "bold")
_FONT_SM     = ("Consolas", 8)


class SettingsPane(tk.Frame):
    """
    Category management panel.

    Callbacks supplied by KleinPC:
        on_exit()                     — return to terminal
        get_layout() -> dict          — read current layout
        add_category(name)            — create a new category
        delete_category(cat_id)       — remove; items → Uncategorized
        rename_category(cat_id, name) — change label
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_exit: Callable,
        get_layout: Callable[[], dict],
        add_category: Callable[[str], None],
        delete_category: Callable[[str], None],
        rename_category: Callable[[str, str], None],
    ):
        super().__init__(parent, bg=_BG, bd=0, highlightthickness=0)
        self._on_exit = on_exit
        self._get_layout = get_layout
        self._add_category = add_category
        self._delete_category = delete_category
        self._rename_category = rename_category
        self._build()
        self.bind("<Escape>", lambda _: on_exit())

    # ── Build ────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Chrome bar
        bar = tk.Frame(self, bg=_CHROME, bd=0)
        bar.pack(fill="x")
        tk.Label(bar, text="SETTINGS — CATEGORIES",
                 bg=_CHROME, fg=_TEXT_FG, font=_FONT_B, padx=8, pady=4,
                 ).pack(side="left")
        tk.Button(
            bar, text="← Back", command=self._on_exit,
            bg=_BTN_BG, fg=_TEXT_FG, activebackground=_BTN_ACT,
            activeforeground=_TEXT_HI, font=_FONT_SM,
            relief="flat", padx=8, pady=2, bd=0, cursor="hand2",
        ).pack(side="right", padx=6, pady=2)
        tk.Frame(self, bg=_BORDER, height=1).pack(fill="x")

        # Category list
        self._list_frame = tk.Frame(self, bg=_BG)
        self._list_frame.pack(fill="both", expand=True, padx=8, pady=8)
        self._refresh_list()

        # Add-category footer
        tk.Frame(self, bg=_BORDER, height=1).pack(fill="x")
        add_row = tk.Frame(self, bg=_STATUS, bd=0)
        add_row.pack(fill="x")
        tk.Label(add_row, text="New:", bg=_STATUS, fg=_TEXT_DIM,
                 font=_FONT_SM, padx=8).pack(side="left")
        self._new_name = tk.StringVar()
        entry = tk.Entry(
            add_row, textvariable=self._new_name,
            bg=_BG, fg=_TEXT_FG, insertbackground=_TEXT_FG,
            font=_FONT, relief="flat", bd=0, highlightthickness=0,
        )
        entry.pack(side="left", fill="x", expand=True, padx=4, pady=5)
        entry.bind("<Return>", lambda _: self._do_add())
        tk.Button(
            add_row, text="Add", command=self._do_add,
            bg=_BTN_BG, fg=_TEXT_FG, activebackground=_BTN_ACT,
            activeforeground=_TEXT_HI, font=_FONT_B,
            relief="flat", padx=10, pady=3, bd=0, cursor="hand2",
        ).pack(side="right", padx=6, pady=4)

        # Status bar
        self._status_var = tk.StringVar(value="")
        tk.Label(
            self, textvariable=self._status_var,
            bg=_STATUS, fg=_TEXT_DIM, font=_FONT_SM, anchor="w", padx=8,
        ).pack(fill="x", side="bottom")

        self.after(50, self.focus_set)

    def _refresh_list(self) -> None:
        for w in self._list_frame.winfo_children():
            w.destroy()

        cats = self._get_layout().get("categories", [])
        if not cats:
            tk.Label(self._list_frame, text="No categories yet.",
                     bg=_BG, fg=_TEXT_DIM, font=_FONT_SM, anchor="w",
                     ).pack(fill="x", pady=4)
            return

        # Column headers
        hdr = tk.Frame(self._list_frame, bg=_BG)
        hdr.pack(fill="x", pady=(0, 2))
        tk.Label(hdr, text="Name", bg=_BG, fg=_TEXT_DIM,
                 font=_FONT_SM, anchor="w", width=18).pack(side="left")
        tk.Label(hdr, text="n", bg=_BG, fg=_TEXT_DIM,
                 font=_FONT_SM, anchor="w", width=4).pack(side="left")
        tk.Frame(self._list_frame, bg=_BORDER, height=1).pack(fill="x", pady=(0, 4))

        for cat in cats:
            self._add_cat_row(cat)

    def _add_cat_row(self, cat: dict) -> None:
        n = len(cat.get("items", []))

        row = tk.Frame(self._list_frame, bg=_BG)
        row.pack(fill="x", pady=1)

        tk.Label(row, text=cat["label"], bg=_BG, fg=_TEXT_FG,
                 font=_FONT, anchor="w", width=18).pack(side="left")
        tk.Label(row, text=str(n), bg=_BG, fg=_TEXT_DIM,
                 font=_FONT_SM, anchor="w", width=4).pack(side="left")

        tk.Button(
            row, text="✕", command=lambda c=cat: self._do_delete(c),
            bg=_BTN_DEL, fg="#aa4444",
            activebackground=_BTN_DEL_ACT, activeforeground="#ff8888",
            font=_FONT_SM, relief="flat", padx=6, pady=1, bd=0, cursor="hand2",
        ).pack(side="right", padx=2)
        tk.Button(
            row, text="✎", command=lambda c=cat: self._do_rename(c),
            bg=_BTN_BG, fg=_TEXT_DIM,
            activebackground=_BTN_ACT, activeforeground=_TEXT_HI,
            font=_FONT_SM, relief="flat", padx=6, pady=1, bd=0, cursor="hand2",
        ).pack(side="right", padx=2)

    # ── Actions ──────────────────────────────────────────────────────

    def _do_add(self) -> None:
        name = self._new_name.get().strip()
        if not name:
            self._status_var.set("Enter a name first.")
            return
        cats = self._get_layout().get("categories", [])
        if any(c["label"].lower() == name.lower() for c in cats):
            self._status_var.set(f"'{name}' already exists.")
            return
        self._add_category(name)
        self._new_name.set("")
        self._status_var.set(f"Added '{name}'.")
        self._refresh_list()

    def _do_rename(self, cat: dict) -> None:
        popup = self._make_popup(f"Rename '{cat['label']}'")
        entry_var = tk.StringVar(value=cat["label"])
        entry = tk.Entry(
            popup, textvariable=entry_var,
            bg="#0a2010", fg=_TEXT_HI, insertbackground=_TEXT_HI,
            font=_FONT_B, relief="flat", bd=0,
            highlightthickness=1, highlightcolor=_BORDER, width=22,
        )
        entry.pack(padx=16, pady=8)
        entry.select_range(0, "end")
        entry.focus_set()

        def _confirm() -> None:
            name = entry_var.get().strip()
            if name and name != cat["label"]:
                self._rename_category(cat["id"], name)
                self._status_var.set(f"Renamed to '{name}'.")
                self._refresh_list()
            popup.destroy()

        entry.bind("<Return>", lambda _: _confirm())
        entry.bind("<Escape>", lambda _: popup.destroy())
        self._popup_buttons(popup, _confirm, popup.destroy)

    def _do_delete(self, cat: dict) -> None:
        n = len(cat.get("items", []))
        msg = (
            f"Delete '{cat['label']}'?\n{n} item(s) will become top-level sidebar items."
            if n else
            f"Delete '{cat['label']}'?"
        )
        popup = self._make_popup(msg)

        def _confirm() -> None:
            self._delete_category(cat["id"])
            self._status_var.set(f"Deleted '{cat['label']}'.")
            self._refresh_list()
            popup.destroy()

        self._popup_buttons(popup, _confirm, popup.destroy)

    # ── Popup helpers ────────────────────────────────────────────────

    def _make_popup(self, message: str) -> tk.Toplevel:
        popup = tk.Toplevel(self)
        popup.configure(bg=_BG)
        popup.resizable(False, False)
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        tk.Label(popup, text=message, bg=_BG, fg=_TEXT_FG,
                 font=_FONT, padx=16, pady=12, justify="left").pack()
        return popup

    def _popup_buttons(
        self, popup: tk.Toplevel, on_ok: Callable, on_cancel: Callable
    ) -> None:
        row = tk.Frame(popup, bg=_BG)
        row.pack(pady=(0, 10))
        tk.Button(
            row, text="OK", command=on_ok,
            bg=_BTN_BG, fg=_TEXT_FG, activebackground=_BTN_ACT,
            activeforeground=_TEXT_HI, font=_FONT_B,
            relief="flat", padx=12, pady=3, bd=0, cursor="hand2",
        ).pack(side="left", padx=4)
        tk.Button(
            row, text="Cancel", command=on_cancel,
            bg=_BTN_BG, fg=_TEXT_DIM, activebackground=_BTN_ACT,
            activeforeground=_TEXT_HI, font=_FONT_SM,
            relief="flat", padx=12, pady=3, bd=0, cursor="hand2",
        ).pack(side="left", padx=4)
        popup.bind("<Escape>", lambda _: on_cancel())
        # Centre over parent after all widgets are placed
        popup.update_idletasks()
        pw = popup.winfo_reqwidth()
        ph = popup.winfo_reqheight()
        px = self.winfo_rootx() + (self.winfo_width() - pw) // 2
        py = self.winfo_rooty() + (self.winfo_height() - ph) // 2
        popup.geometry(f"+{px}+{py}")
