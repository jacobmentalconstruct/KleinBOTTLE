"""Midnight Blue Tk/ttk presentation for KleinBOTTLE.

This module is a local copy of theme values, not a dependency on development
sidecars. Widgets keep their existing behavior; only their presentation changes.
"""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

BACKGROUND = "#1e1e2f"
INSET = "#151521"
SURFACE = "#2a2a3f"
ACCENT = "#007ACC"
TEXT = "#E7EDF4"
MUTED = "#97A4B3"
STATUS = "#00FF00"
DANGER = "#C23621"
BORDER = "#333333"

FONT_UI = ("Segoe UI", 9)
FONT_HEADING = ("Segoe UI", 10, "bold")
FONT_MONO = ("Consolas", 9)
FONT_STORY = ("Segoe UI", 10)


@dataclass
class Palette:
    """Token set for a complete UI colour scheme."""
    background: str
    inset: str
    surface: str
    accent: str
    text: str
    muted: str
    font_heading: tuple
    font_story: tuple


def activate(palette: Palette) -> None:
    """Replace the active theme tokens with those from *palette*.

    Call before ``apply_theme`` / before surfaces are instantiated.
    Replaces direct module-global assignment from outside this module.
    """
    global BACKGROUND, INSET, SURFACE, ACCENT, TEXT, MUTED, FONT_HEADING, FONT_STORY
    BACKGROUND   = palette.background
    INSET        = palette.inset
    SURFACE      = palette.surface
    ACCENT       = palette.accent
    TEXT         = palette.text
    MUTED        = palette.muted
    FONT_HEADING = palette.font_heading
    FONT_STORY   = palette.font_story


def apply_theme(root: tk.Tk) -> None:
    """Set the single application-wide ttk style before creating either surface."""
    root.configure(bg=BACKGROUND)
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=BACKGROUND, foreground=TEXT, font=FONT_UI)
    style.configure("TFrame", background=BACKGROUND)
    style.configure("TLabel", background=BACKGROUND, foreground=TEXT, font=FONT_UI)
    style.configure("Heading.TLabel", font=FONT_HEADING)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Status.TLabel", foreground=STATUS)

    style.configure("TButton", background=SURFACE, foreground=TEXT,
                    bordercolor=BORDER, borderwidth=1, relief="flat", padding=(10, 5))
    style.map("TButton",
              background=[("pressed", ACCENT), ("active", ACCENT)],
              foreground=[("disabled", MUTED), ("active", "#FFFFFF")])
    style.configure("Accent.TButton", background=ACCENT, foreground="#FFFFFF")
    style.map("Accent.TButton",
              background=[("pressed", "#0065a8"), ("active", "#178cdb")],
              foreground=[("disabled", MUTED), ("active", "#FFFFFF")])
    style.configure("Danger.TButton", background=DANGER, foreground="#FFFFFF")
    style.map("Danger.TButton",
              background=[("pressed", "#8c291b"), ("active", "#a52d1c")],
              foreground=[("disabled", MUTED), ("active", "#FFFFFF")])

    style.configure("TEntry", fieldbackground=INSET, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=5)
    style.map("TEntry", fieldbackground=[("readonly", SURFACE), ("disabled", SURFACE)],
              foreground=[("disabled", MUTED)])
    style.configure("TCombobox", fieldbackground=INSET, foreground=TEXT,
                    background=SURFACE, arrowcolor=TEXT, bordercolor=BORDER, padding=4,
                    selectbackground=ACCENT, selectforeground="#FFFFFF")
    style.map("TCombobox",
              fieldbackground=[("readonly", INSET), ("disabled", SURFACE)],
              foreground=[("readonly", TEXT), ("disabled", MUTED)],
              selectbackground=[("readonly", ACCENT)],
              selectforeground=[("readonly", "#FFFFFF")])
    root.option_add("*TCombobox*Listbox.background", INSET)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")

    style.configure("TNotebook", background=BACKGROUND, borderwidth=0)
    style.configure("TNotebook.Tab", background=SURFACE, foreground=MUTED,
                    padding=(14, 8), borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", BACKGROUND), ("active", ACCENT)],
              foreground=[("selected", TEXT), ("active", "#FFFFFF")])
    style.configure("Treeview", background=INSET, fieldbackground=INSET,
                    foreground=TEXT, rowheight=25, bordercolor=BORDER,
                    borderwidth=0, font=FONT_UI)
    style.map("Treeview", background=[("selected", ACCENT)],
              foreground=[("selected", "#FFFFFF")])
    style.configure("TLabelFrame", background=BACKGROUND, bordercolor=BORDER)
    style.configure("TLabelFrame.Label", background=BACKGROUND,
                    foreground=TEXT, font=FONT_HEADING)
    style.configure("TRadiobutton", background=BACKGROUND, foreground=TEXT, font=FONT_UI)
    style.map("TRadiobutton", foreground=[("disabled", MUTED)])
    style.configure("TCheckbutton", background=BACKGROUND, foreground=TEXT, font=FONT_UI)
    style.map("TCheckbutton", foreground=[("disabled", MUTED)],
              background=[("active", BACKGROUND)])
    style.configure("TPanedwindow", background=BACKGROUND)
    style.configure("TScrollbar", background=SURFACE, troughcolor=INSET,
                    arrowcolor=TEXT, bordercolor=BORDER)
    style.map("TScrollbar", background=[("active", ACCENT)])


def style_text(widget: tk.Text, *, font: tuple = FONT_MONO) -> None:
    """ttk styles do not affect classic tk.Text widgets; style them explicitly."""
    widget.configure(bg=INSET, fg=TEXT, insertbackground=TEXT,
                     selectbackground=ACCENT, selectforeground="#FFFFFF",
                     highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=ACCENT, relief="flat", font=font)


def style_dialog(window: tk.Toplevel) -> None:
    """Ensure classic Tk dialog backgrounds match the ttk theme."""
    window.configure(bg=BACKGROUND)
