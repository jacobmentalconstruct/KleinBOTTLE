"""
klein_monitors/klein_theme.py

Green phosphor ttk style — applied once to the Tk root before any KleinBOTTLE
ttk surface (BuilderSurface, GameSurface) is instantiated.

Mirrors the structure of KleinBOTTLE's ui_theme.apply_theme() but with
the KleinOS green phosphor palette so both surfaces blend into the monitor.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# ── Palette ───────────────────────────────────────────────────────────
BG      = "#010a01"   # deep black-green
INSET   = "#000800"   # slightly lighter for text fields
SURFACE = "#0a1a0a"   # button / widget surface
ACCENT  = "#00dd33"   # bright green — primary action
TEXT    = "#00dd33"   # main text
MUTED   = "#1a4a1a"   # dimmed labels
DANGER  = "#005522"   # delete / destructive (dark green — no red)
BORDER  = "#003311"
SELECT  = "#004d18"   # selection background

FONT_UI      = ("Consolas", 9)
FONT_HEADING = ("Consolas", 10, "bold")
FONT_MONO    = ("Consolas", 9)
FONT_STORY   = ("Consolas", 10)


def apply(root: tk.Misc) -> None:
    """
    Configure the ttk Style on root's Tk interpreter for the green theme.
    Safe to call multiple times — Style configuration is idempotent.
    """
    root.tk.call("tk", "appname")  # ensure Tk is initialised
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".",
        background=BG, foreground=TEXT, font=FONT_UI,
        troughcolor=INSET, selectbackground=SELECT, selectforeground=TEXT,
        fieldbackground=INSET,
    )
    style.configure("TFrame",        background=BG)
    style.configure("TLabel",        background=BG, foreground=TEXT, font=FONT_UI)
    style.configure("Heading.TLabel",font=FONT_HEADING, foreground=ACCENT)
    style.configure("Muted.TLabel",  foreground=MUTED)
    style.configure("Status.TLabel", foreground=ACCENT)

    style.configure("TButton",
        background=SURFACE, foreground=TEXT,
        bordercolor=BORDER, borderwidth=1, relief="flat", padding=(10, 5),
    )
    style.map("TButton",
        background=[("pressed", ACCENT), ("active", SELECT)],
        foreground=[("disabled", MUTED), ("active", TEXT)],
    )
    style.configure("Accent.TButton", background=ACCENT, foreground=BG)
    style.map("Accent.TButton",
        background=[("pressed", SELECT), ("active", "#00ff44")],
        foreground=[("disabled", MUTED), ("active", BG)],
    )
    style.configure("Danger.TButton", background=DANGER, foreground=TEXT)
    style.map("Danger.TButton",
        background=[("pressed", "#002211"), ("active", "#006633")],
        foreground=[("disabled", MUTED)],
    )

    style.configure("TEntry",
        fieldbackground=INSET, foreground=TEXT,
        insertcolor=TEXT,
        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=5,
    )
    style.map("TEntry",
        fieldbackground=[("readonly", SURFACE), ("disabled", SURFACE)],
        foreground=[("disabled", MUTED)],
    )
    style.configure("TCombobox",
        fieldbackground=INSET, foreground=TEXT,
        background=SURFACE, arrowcolor=TEXT, bordercolor=BORDER, padding=4,
        selectbackground=SELECT, selectforeground=TEXT,
    )
    style.map("TCombobox",
        fieldbackground=[("readonly", INSET), ("disabled", SURFACE)],
        foreground=[("readonly", TEXT), ("disabled", MUTED)],
        selectbackground=[("readonly", SELECT)],
    )
    root.option_add("*TCombobox*Listbox.background", INSET)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", SELECT)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)

    style.configure("TNotebook",     background=BG, borderwidth=0)
    style.configure("TNotebook.Tab",
        background=SURFACE, foreground=MUTED, padding=(14, 8), borderwidth=0,
    )
    style.map("TNotebook.Tab",
        background=[("selected", BG), ("active", SELECT)],
        foreground=[("selected", ACCENT), ("active", TEXT)],
    )
    style.configure("Treeview",
        background=INSET, fieldbackground=INSET, foreground=TEXT,
        rowheight=22, bordercolor=BORDER, borderwidth=0, font=FONT_UI,
    )
    style.map("Treeview",
        background=[("selected", SELECT)],
        foreground=[("selected", ACCENT)],
    )
    style.configure("TLabelFrame",       background=BG, bordercolor=BORDER)
    style.configure("TLabelFrame.Label", background=BG, foreground=TEXT, font=FONT_HEADING)
    style.configure("TRadiobutton",      background=BG, foreground=TEXT, font=FONT_UI)
    style.map("TRadiobutton",  foreground=[("disabled", MUTED)])
    style.configure("TCheckbutton",      background=BG, foreground=TEXT, font=FONT_UI)
    style.map("TCheckbutton",  foreground=[("disabled", MUTED)], background=[("active", BG)])
    style.configure("TPanedwindow",      background=BG)
    style.configure("Sash",             sashthickness=4)
    style.configure("TScrollbar",
        background=SURFACE, troughcolor=INSET, arrowcolor=MUTED, bordercolor=BORDER,
    )
    style.map("TScrollbar", background=[("active", SELECT)])
    style.configure("TSeparator", background=BORDER)


def style_text(widget: tk.Text, *, font: tuple = FONT_MONO) -> None:
    """Apply green phosphor colours to a classic tk.Text widget."""
    widget.configure(
        bg=INSET, fg=TEXT, insertbackground=TEXT,
        selectbackground=SELECT, selectforeground=ACCENT,
        highlightthickness=1, highlightbackground=BORDER,
        highlightcolor=ACCENT, relief="flat", font=font,
    )
