"""
kleinos/settings_pane.py

SettingsPane — 4-tab settings panel for KleinOS.
Tabs: Display | Sound | Keybinds | Navigation
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from kleinos import audio as _audio
from kleinos import config as _config

from kleinos.palette import (
    BG as _BG, CHROME as _CHROME, BORDER as _BORDER,
    BTN_BG as _BTN_BG, BTN_ACT as _BTN_ACT,
    BTN_DEL as _BTN_DEL, BTN_DEL_A as _BTN_DEL_ACT,
    BG2 as _STATUS, FG_ON as _TEXT_FG, FG_DIM as _TEXT_DIM, FG_HI as _TEXT_HI,
)
_BTN_TAB_ON  = _BTN_ACT
_BTN_TAB_OFF = _STATUS
_FONT        = ("Consolas", 9)
_FONT_B      = ("Consolas", 9, "bold")
_FONT_SM     = ("Consolas", 8)

_PALETTE_COLORS = {
    "green": "#00dd33",
    "amber": "#ffaa00",
    "white": "#d0d0d0",
    "blue":  "#66aaff",
    "red":   "#ff4444",
}
_PALETTE_LABELS = {
    "green": "Green Phosphor",
    "amber": "Amber Phosphor",
    "white": "White Phosphor",
    "blue":  "Blue-White Phosphor",
    "red":   "Red Phosphor",
}

_KEYBINDS = [
    ("Move left",     "← / A"),
    ("Move right",    "→ / D"),
    ("Move up",       "↑ / W"),
    ("Move down",     "↓ / S"),
    ("Fire / Select", "Space / Enter"),
    ("Exit / Back",   "Escape"),
]

_SOUND_LABELS = {
    "shoot":      "Shoot",
    "hit":        "Invader hit",
    "explosion":  "Explosion",
    "player_hit": "Player hit",
    "death":      "Player death",
    "tick":       "Alien step",
}


class SettingsPane(tk.Frame):
    """
    Four-tab settings panel.

    Category callbacks supplied by KleinPC:
        on_exit()
        get_layout() -> dict
        add_category(name)
        delete_category(cat_id)
        rename_category(cat_id, name)
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
        self._cfg = _config.load()
        self._status_var = tk.StringVar(value="")
        self._tab_frames: dict[str, tk.Frame] = {}
        self._tab_btns: dict[str, tk.Button] = {}
        self._palette_btns: dict[str, tk.Button] = {}
        self._sound_btns: dict[str, tk.Button] = {}
        self._master_btn: Optional[tk.Button] = None
        self._nav_list_frame: Optional[tk.Frame] = None
        self._new_name = tk.StringVar()
        self._build()
        self.bind("<Escape>", lambda _: on_exit())

    # ── Build ────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Chrome bar
        bar = tk.Frame(self, bg=_CHROME, bd=0)
        bar.pack(fill="x")
        tk.Label(bar, text="SETTINGS", bg=_CHROME, fg=_TEXT_FG,
                 font=_FONT_B, padx=8, pady=4).pack(side="left")
        tk.Button(
            bar, text="← Back", command=self._on_exit,
            bg=_BTN_BG, fg=_TEXT_FG, activebackground=_BTN_ACT,
            activeforeground=_TEXT_HI, font=_FONT_SM,
            relief="flat", padx=8, pady=2, bd=0, cursor="hand2",
        ).pack(side="right", padx=6, pady=2)

        # Tab bar
        tab_bar = tk.Frame(self, bg=_CHROME, bd=0)
        tab_bar.pack(fill="x")
        for name in ("Display", "Sound", "Keybinds", "Navigation", "AI"):
            btn = tk.Button(
                tab_bar, text=name,
                command=lambda n=name: self._switch_tab(n),
                bg=_BTN_TAB_OFF, fg=_TEXT_DIM,
                activebackground=_BTN_TAB_ON, activeforeground=_TEXT_FG,
                font=_FONT_SM, relief="flat", padx=10, pady=4, bd=0,
                cursor="hand2",
            )
            btn.pack(side="left")
            self._tab_btns[name] = btn

        tk.Frame(self, bg=_BORDER, height=1).pack(fill="x")

        # Tab content area
        content = tk.Frame(self, bg=_BG)
        content.pack(fill="both", expand=True)

        for name, builder in (
            ("Display",    self._build_display_tab),
            ("Sound",      self._build_sound_tab),
            ("Keybinds",   self._build_keybinds_tab),
            ("Navigation", self._build_navigation_tab),
            ("AI",         self._build_ai_tab),
        ):
            frame = tk.Frame(content, bg=_BG)
            self._tab_frames[name] = frame
            builder(frame)

        # Status bar
        tk.Label(
            self, textvariable=self._status_var,
            bg=_STATUS, fg=_TEXT_DIM, font=_FONT_SM, anchor="w", padx=8,
        ).pack(fill="x", side="bottom")

        self._switch_tab("Display")
        self.after(50, self.focus_set)

    def _switch_tab(self, name: str) -> None:
        for n, frame in self._tab_frames.items():
            frame.pack_forget()
        for n, btn in self._tab_btns.items():
            if n == name:
                btn.configure(bg=_BTN_TAB_ON, fg=_TEXT_FG)
            else:
                btn.configure(bg=_BTN_TAB_OFF, fg=_TEXT_DIM)
        self._tab_frames[name].pack(fill="both", expand=True, padx=8, pady=6)
        self._status_var.set("")

    # ── Display tab ──────────────────────────────────────────────────

    def _build_display_tab(self, parent: tk.Frame) -> None:
        # ── PC Window Size ──────────────────────────────────────────────
        tk.Label(parent, text="PC WINDOW SIZE",
                 bg=_BG, fg=_TEXT_DIM, font=_FONT_SM, anchor="w",
                 ).pack(fill="x", pady=(4, 2))
        tk.Frame(parent, bg=_BORDER, height=1).pack(fill="x", pady=(0, 6))

        self._size_btns: dict[str, tk.Button] = {}
        current_size = self._cfg.get("pc_size", "medium")
        for key, label in (("small", "Small  (65%)"), ("medium", "Medium  (100%)"), ("large", "Large  (130%)"), ("xlarge", "X-Large  (160%)")):
            is_sel = key == current_size
            btn = tk.Button(
                parent,
                text=f"{'● ' if is_sel else '○ '}{label}",
                command=lambda k=key: self._select_pc_size(k),
                bg=_BTN_ACT if is_sel else _BTN_BG,
                fg=_TEXT_FG,
                activebackground=_BTN_ACT, activeforeground=_TEXT_HI,
                font=_FONT if is_sel else _FONT_SM,
                relief="flat", anchor="w", padx=12, pady=4, bd=0, cursor="hand2",
            )
            btn.pack(fill="x", pady=1)
            self._size_btns[key] = btn

        tk.Label(parent, text="Takes effect on next PC open",
                 bg=_BG, fg=_TEXT_DIM, font=_FONT_SM, anchor="w",
                 ).pack(fill="x", pady=(4, 10))

        # ── Phosphor Color ──────────────────────────────────────────────
        tk.Label(parent, text="PHOSPHOR COLOR",
                 bg=_BG, fg=_TEXT_DIM, font=_FONT_SM, anchor="w",
                 ).pack(fill="x", pady=(4, 2))
        tk.Frame(parent, bg=_BORDER, height=1).pack(fill="x", pady=(0, 6))

        current = self._cfg.get("palette", "green")
        for key in ("green", "amber", "white", "blue", "red"):
            color  = _PALETTE_COLORS[key]
            label  = _PALETTE_LABELS[key]
            is_sel = key == current
            prefix = "● " if is_sel else "○ "
            btn = tk.Button(
                parent,
                text=f"{prefix}{label}",
                command=lambda k=key: self._select_palette(k),
                bg=_BTN_ACT if is_sel else _BTN_BG,
                fg=color,
                activebackground=_BTN_ACT, activeforeground=color,
                font=_FONT if is_sel else _FONT_SM,
                relief="flat", anchor="w", padx=12, pady=4, bd=0, cursor="hand2",
            )
            btn.pack(fill="x", pady=1)
            self._palette_btns[key] = btn

        tk.Frame(parent, bg=_BORDER, height=1).pack(fill="x", pady=(8, 4))
        tk.Label(parent, text="⚠  Restart required to apply",
                 bg=_BG, fg=_TEXT_DIM, font=_FONT_SM, anchor="w",
                 ).pack(fill="x")
        tk.Button(
            parent, text="Apply (restart now)",
            command=self._show_restart_popup,
            bg=_BTN_BG, fg=_TEXT_FG, activebackground=_BTN_ACT,
            activeforeground=_TEXT_HI, font=_FONT,
            relief="flat", padx=12, pady=4, bd=0, cursor="hand2",
        ).pack(anchor="w", pady=(6, 0))

        # ── Image Generation Pipeline ───────────────────────────────────
        tk.Label(parent, text="IMAGE GENERATION PIPELINE",
                 bg=_BG, fg=_TEXT_DIM, font=_FONT_SM, anchor="w",
                 ).pack(fill="x", pady=(14, 2))
        tk.Frame(parent, bg=_BORDER, height=1).pack(fill="x", pady=(0, 6))

        # Status line showing current configured path
        self._pipe_status_var = tk.StringVar()
        self._update_pipeline_status()
        tk.Label(parent, textvariable=self._pipe_status_var,
                 bg=_BG, fg=_TEXT_FG, font=_FONT_SM, anchor="w",
                 ).pack(fill="x", pady=(0, 6))

        # Option 1: Browse for an existing installation
        browse_row = tk.Frame(parent, bg=_BG)
        browse_row.pack(fill="x", pady=(0, 2))
        tk.Button(
            browse_row, text="Browse existing…",
            command=self._browse_pipeline,
            bg=_BTN_BG, fg=_TEXT_FG, activebackground=_BTN_ACT,
            activeforeground=_TEXT_HI, font=_FONT,
            relief="flat", padx=10, pady=4, bd=0, cursor="hand2",
        ).pack(side="left")
        tk.Label(browse_row, text="  Pick a folder where it is already installed",
                 bg=_BG, fg=_TEXT_DIM, font=_FONT_SM).pack(side="left")

        # Option 2: Clone into the KleinBOTTLE install directory
        from pathlib import Path as _Path
        _local_pipe = _Path(__file__).resolve().parent.parent / "tools" / "image-pipeline"
        install_row = tk.Frame(parent, bg=_BG)
        install_row.pack(fill="x", pady=(0, 8))
        tk.Button(
            install_row, text="Install locally",
            command=self._install_pipeline_local,
            bg=_BTN_BG, fg=_TEXT_FG, activebackground=_BTN_ACT,
            activeforeground=_TEXT_HI, font=_FONT,
            relief="flat", padx=10, pady=4, bd=0, cursor="hand2",
        ).pack(side="left")
        tk.Label(install_row, text=f"  → {_local_pipe}",
                 bg=_BG, fg=_TEXT_DIM, font=_FONT_SM).pack(side="left")

        # Advanced: Git URL (for Install locally)
        gh_row = tk.Frame(parent, bg=_BG)
        gh_row.pack(fill="x", pady=(0, 2))
        tk.Label(gh_row, text="Git URL:", bg=_BG, fg=_TEXT_DIM,
                 font=_FONT_SM, width=8, anchor="w").pack(side="left")
        self._pipeline_github_var = tk.StringVar(
            value=self._cfg.get("image_pipeline", {}).get("github_url", "")
        )
        tk.Entry(
            gh_row, textvariable=self._pipeline_github_var,
            bg=_BG, fg=_TEXT_DIM, insertbackground=_TEXT_FG,
            font=_FONT_SM, relief="flat",
            highlightthickness=1, highlightcolor=_BORDER,
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))
        tk.Label(parent, text="Paste repo URL above before clicking Install locally.",
                 bg=_BG, fg=_TEXT_DIM, font=_FONT_SM, anchor="w",
                 ).pack(fill="x", pady=(2, 0))

    def _select_pc_size(self, key: str) -> None:
        if key == self._cfg.get("pc_size", "medium"):
            return
        self._cfg["pc_size"] = key
        _config.save(self._cfg)
        for k, btn in self._size_btns.items():
            is_sel = k == key
            _size_labels = {"small": "Small  (65%)", "medium": "Medium  (100%)", "large": "Large  (130%)", "xlarge": "X-Large  (160%)"}
            btn.configure(
                text=f"{'● ' if is_sel else '○ '}{_size_labels.get(k, k.capitalize())}",
                bg=_BTN_ACT if is_sel else _BTN_BG,
                font=_FONT_B if is_sel else _FONT_SM,
            )

    def _select_palette(self, key: str) -> None:
        current = self._cfg.get("palette", "green")
        if key == current:
            return
        self._cfg["palette"] = key
        _config.save(self._cfg)
        for k, btn in self._palette_btns.items():
            is_sel = k == key
            color  = _PALETTE_COLORS[k]
            btn.configure(
                text=f"{'● ' if is_sel else '○ '}{_PALETTE_LABELS[k]}",
                bg=_BTN_ACT if is_sel else _BTN_BG,
                fg=color,
                font=_FONT if is_sel else _FONT_SM,
            )
        self._status_var.set(f"Palette set to '{_PALETTE_LABELS[key]}' — restart to apply.")

    def _update_pipeline_status(self) -> None:
        from pathlib import Path as _Path
        cfg_pip = self._cfg.get("image_pipeline", {})
        path = cfg_pip.get("path", "")
        local = _Path(__file__).resolve().parent.parent / "tools" / "image-pipeline"
        if path and _Path(path).exists():
            self._pipe_status_var.set(f"● Configured: {path}")
        elif not path and local.exists():
            self._pipe_status_var.set(f"● Local install: {local}")
        elif path:
            self._pipe_status_var.set(f"⚠ Not found: {path}")
        else:
            self._pipe_status_var.set("○ Not configured")

    def _browse_pipeline(self) -> None:
        from tkinter.filedialog import askdirectory
        folder = askdirectory(title="Select image-generation-pipeline folder")
        if not folder:
            return
        cfg_pip = self._cfg.setdefault("image_pipeline", {})
        cfg_pip["path"] = folder
        _config.save(self._cfg)
        self._update_pipeline_status()
        self._status_var.set("Pipeline path saved.")

    def _install_pipeline_local(self) -> None:
        import subprocess
        from pathlib import Path as _Path
        local = _Path(__file__).resolve().parent.parent / "tools" / "image-pipeline"
        url = self._pipeline_github_var.get().strip()
        if not url:
            url = self._cfg.get("image_pipeline", {}).get("github_url", "")
        if not url:
            self._status_var.set("Paste the Git URL above, then try again.")
            return
        if local.exists():
            self._status_var.set(f"Already installed: {local}")
            self._update_pipeline_status()
            return
        local.parent.mkdir(parents=True, exist_ok=True)
        cfg_pip = self._cfg.setdefault("image_pipeline", {})
        cfg_pip["github_url"] = url
        cfg_pip["path"] = ""  # empty → _pipeline_root() falls back to local install
        _config.save(self._cfg)
        self._status_var.set(f"Cloning to {local}…  (check terminal for progress)")
        try:
            subprocess.Popen(["git", "clone", url, str(local)])
            self._update_pipeline_status()
        except FileNotFoundError:
            self._status_var.set("git not found — install Git first.")

    # ── Sound tab ────────────────────────────────────────────────────

    def _build_sound_tab(self, parent: tk.Frame) -> None:
        cfg_audio = self._cfg.get("audio", {})
        master_on = bool(cfg_audio.get("enabled", True))

        # Master toggle
        master_row = tk.Frame(parent, bg=_BG)
        master_row.pack(fill="x", pady=(4, 0))
        tk.Label(master_row, text="Master Audio",
                 bg=_BG, fg=_TEXT_FG, font=_FONT_B, anchor="w",
                 ).pack(side="left", padx=(0, 8))
        self._master_btn = tk.Button(
            master_row,
            text=self._toggle_text(master_on),
            command=self._toggle_master,
            bg=_BTN_ACT if master_on else _BTN_BG,
            fg=_TEXT_FG if master_on else _TEXT_DIM,
            activebackground=_BTN_ACT, activeforeground=_TEXT_HI,
            font=_FONT_SM, relief="flat", padx=8, pady=2, bd=0, cursor="hand2",
        )
        self._master_btn.pack(side="left")

        tk.Frame(parent, bg=_BORDER, height=1).pack(fill="x", pady=(6, 4))

        # Per-sound toggles
        sounds = cfg_audio.get("sounds", {})
        for key, label in _SOUND_LABELS.items():
            on = bool(sounds.get(key, True))
            row = tk.Frame(parent, bg=_BG)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, bg=_BG, fg=_TEXT_DIM, font=_FONT_SM,
                     anchor="w", width=16).pack(side="left")
            btn = tk.Button(
                row,
                text=self._toggle_text(on),
                command=lambda k=key: self._toggle_sound(k),
                bg=_BTN_ACT if on else _BTN_BG,
                fg=_TEXT_FG if on else _TEXT_DIM,
                activebackground=_BTN_ACT, activeforeground=_TEXT_HI,
                font=_FONT_SM, relief="flat", padx=8, pady=2, bd=0, cursor="hand2",
            )
            btn.pack(side="left")
            self._sound_btns[key] = btn

    @staticmethod
    def _toggle_text(on: bool) -> str:
        return " ON " if on else "OFF"

    def _toggle_master(self) -> None:
        cfg_audio = self._cfg.setdefault("audio", {})
        new_val = not bool(cfg_audio.get("enabled", True))
        cfg_audio["enabled"] = new_val
        _audio.set_enabled(new_val)
        _config.save(self._cfg)
        if self._master_btn:
            self._master_btn.configure(
                text=self._toggle_text(new_val),
                bg=_BTN_ACT if new_val else _BTN_BG,
                fg=_TEXT_FG if new_val else _TEXT_DIM,
            )
        self._status_var.set("Audio " + ("enabled." if new_val else "disabled."))

    def _toggle_sound(self, key: str) -> None:
        cfg_audio = self._cfg.setdefault("audio", {})
        sounds = cfg_audio.setdefault("sounds", {})
        new_val = not bool(sounds.get(key, True))
        sounds[key] = new_val
        _audio.set_sound(key, new_val)
        _config.save(self._cfg)
        btn = self._sound_btns.get(key)
        if btn:
            btn.configure(
                text=self._toggle_text(new_val),
                bg=_BTN_ACT if new_val else _BTN_BG,
                fg=_TEXT_FG if new_val else _TEXT_DIM,
            )
        label = _SOUND_LABELS.get(key, key)
        self._status_var.set(f"{label} " + ("on." if new_val else "off."))

    # ── Keybinds tab ─────────────────────────────────────────────────

    def _build_keybinds_tab(self, parent: tk.Frame) -> None:
        tk.Label(parent, text="KEY BINDINGS",
                 bg=_BG, fg=_TEXT_DIM, font=_FONT_SM, anchor="w",
                 ).pack(fill="x", pady=(4, 2))
        tk.Frame(parent, bg=_BORDER, height=1).pack(fill="x", pady=(0, 6))

        # Header
        hdr = tk.Frame(parent, bg=_BG)
        hdr.pack(fill="x", pady=(0, 2))
        tk.Label(hdr, text="Action", bg=_BG, fg=_TEXT_DIM,
                 font=_FONT_SM, anchor="w", width=18).pack(side="left")
        tk.Label(hdr, text="Keys", bg=_BG, fg=_TEXT_DIM,
                 font=_FONT_SM, anchor="w").pack(side="left")
        tk.Frame(parent, bg=_BORDER, height=1).pack(fill="x", pady=(0, 4))

        for action, keys in _KEYBINDS:
            row = tk.Frame(parent, bg=_BG)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=action, bg=_BG, fg=_TEXT_FG,
                     font=_FONT, anchor="w", width=18).pack(side="left")
            tk.Label(row, text=keys, bg=_BG, fg=_TEXT_HI,
                     font=_FONT_B, anchor="w").pack(side="left")

        tk.Frame(parent, bg=_BORDER, height=1).pack(fill="x", pady=(8, 4))
        tk.Label(parent, text="Rebinding coming later.",
                 bg=_BG, fg=_TEXT_DIM, font=_FONT_SM, anchor="w",
                 ).pack(fill="x")

    # ── AI tab ───────────────────────────────────────────────────────

    def _build_ai_tab(self, parent: tk.Frame) -> None:
        tk.Label(parent, text="OLLAMA",
                 bg=_BG, fg=_TEXT_DIM, font=_FONT_SM, anchor="w",
                 ).pack(fill="x", pady=(4, 2))
        tk.Frame(parent, bg=_BORDER, height=1).pack(fill="x", pady=(0, 6))
        tk.Label(parent,
                 text="Ollama host, port, and models for the room-assist AI.\nChanges take effect on next KleinOS launch.",
                 bg=_BG, fg=_TEXT_DIM, font=_FONT_SM, anchor="w", justify="left",
                 ).pack(fill="x", pady=(0, 8))

        ocfg = self._cfg.get("ollama", {})

        fields = [
            ("Host",             "host",        str(ocfg.get("host",        "127.0.0.1"))),
            ("Port",             "port",        str(ocfg.get("port",        11434))),
            ("Narrative model",  "narr_model",  str(ocfg.get("narr_model",  "qwen2.5:7b"))),
            ("Field model",      "field_model", str(ocfg.get("field_model", "qwen2.5:3b"))),
        ]
        self._ollama_vars: dict[str, tk.StringVar] = {}
        for label, key, default in fields:
            row = tk.Frame(parent, bg=_BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{label}:", bg=_BG, fg=_TEXT_DIM,
                     font=_FONT_SM, width=18, anchor="w").pack(side="left")
            var = tk.StringVar(value=default)
            self._ollama_vars[key] = var
            tk.Entry(
                row, textvariable=var,
                bg=_BG, fg=_TEXT_FG, insertbackground=_TEXT_FG,
                font=_FONT_SM, relief="flat",
                highlightthickness=1, highlightcolor=_BORDER,
            ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        tk.Frame(parent, bg=_BORDER, height=1).pack(fill="x", pady=(10, 6))
        tk.Button(
            parent, text="Save Ollama settings",
            command=self._save_ollama,
            bg=_BTN_BG, fg=_TEXT_FG, activebackground=_BTN_ACT,
            activeforeground=_TEXT_HI, font=_FONT,
            relief="flat", padx=12, pady=4, bd=0, cursor="hand2",
        ).pack(anchor="w")

    def _save_ollama(self) -> None:
        try:
            port = int(self._ollama_vars["port"].get().strip())
        except ValueError:
            self._status_var.set("Port must be a number.")
            return
        ocfg = self._cfg.setdefault("ollama", {})
        ocfg["host"]        = self._ollama_vars["host"].get().strip()
        ocfg["port"]        = port
        ocfg["narr_model"]  = self._ollama_vars["narr_model"].get().strip()
        ocfg["field_model"] = self._ollama_vars["field_model"].get().strip()
        _config.save(self._cfg)
        self._status_var.set("Ollama settings saved — restart to apply.")

    # ── Navigation tab ───────────────────────────────────────────────

    def _build_navigation_tab(self, parent: tk.Frame) -> None:
        # Category list
        self._nav_list_frame = tk.Frame(parent, bg=_BG)
        self._nav_list_frame.pack(fill="both", expand=True)
        self._refresh_list()

        # Add-category footer
        tk.Frame(parent, bg=_BORDER, height=1).pack(fill="x")
        add_row = tk.Frame(parent, bg=_STATUS, bd=0)
        add_row.pack(fill="x")
        tk.Label(add_row, text="New:", bg=_STATUS, fg=_TEXT_DIM,
                 font=_FONT_SM, padx=8).pack(side="left")
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

    def _refresh_list(self) -> None:
        if not self._nav_list_frame:
            return
        for w in self._nav_list_frame.winfo_children():
            w.destroy()

        cats = self._get_layout().get("categories", [])
        if not cats:
            tk.Label(self._nav_list_frame, text="No categories yet.",
                     bg=_BG, fg=_TEXT_DIM, font=_FONT_SM, anchor="w",
                     ).pack(fill="x", pady=4)
            return

        # Column headers
        hdr = tk.Frame(self._nav_list_frame, bg=_BG)
        hdr.pack(fill="x", pady=(0, 2))
        tk.Label(hdr, text="Name", bg=_BG, fg=_TEXT_DIM,
                 font=_FONT_SM, anchor="w", width=18).pack(side="left")
        tk.Label(hdr, text="n", bg=_BG, fg=_TEXT_DIM,
                 font=_FONT_SM, anchor="w", width=4).pack(side="left")
        tk.Frame(self._nav_list_frame, bg=_BORDER, height=1).pack(fill="x", pady=(0, 4))

        for cat in cats:
            self._add_cat_row(cat)

    def _add_cat_row(self, cat: dict) -> None:
        n = len(cat.get("items", []))
        row = tk.Frame(self._nav_list_frame, bg=_BG)  # type: ignore[arg-type]
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

    # ── Navigation actions ───────────────────────────────────────────

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

    # ── Restart popup ────────────────────────────────────────────────

    def _show_restart_popup(self) -> None:
        palette_name = _PALETTE_LABELS.get(self._cfg.get("palette", "green"), "selected")
        popup = tk.Toplevel(self)
        popup.configure(bg=_BG)
        popup.resizable(False, False)
        popup.transient(self.winfo_toplevel())
        popup.grab_set()

        tk.Label(popup,
                 text=f"Apply '{palette_name}'?\nKleinOS will restart now.",
                 bg=_BG, fg=_TEXT_FG, font=_FONT, padx=16, pady=12,
                 justify="center").pack()

        btn_row = tk.Frame(popup, bg=_BG)
        btn_row.pack(pady=(0, 12))

        # 0 = Yes focused, 1 = No focused; default to Yes (user just clicked Apply)
        sel = [0]

        yes_btn = tk.Button(btn_row, text="[Y]  Yes", command=lambda: _confirm(0),
                            bg=_BTN_ACT, fg=_TEXT_HI,
                            activebackground=_BTN_ACT, activeforeground=_TEXT_HI,
                            font=_FONT_B, relief="flat", padx=12, pady=4, bd=0,
                            cursor="hand2")
        yes_btn.pack(side="left", padx=6)

        no_btn = tk.Button(btn_row, text="[N]  No", command=lambda: _confirm(1),
                           bg=_BTN_BG, fg=_TEXT_DIM,
                           activebackground=_BTN_ACT, activeforeground=_TEXT_HI,
                           font=_FONT_SM, relief="flat", padx=12, pady=4, bd=0,
                           cursor="hand2")
        no_btn.pack(side="left", padx=6)

        def _highlight() -> None:
            if sel[0] == 0:
                yes_btn.configure(bg=_BTN_ACT, fg=_TEXT_HI, font=_FONT_B)
                no_btn.configure(bg=_BTN_BG,   fg=_TEXT_DIM, font=_FONT_SM)
            else:
                yes_btn.configure(bg=_BTN_BG,   fg=_TEXT_DIM, font=_FONT_SM)
                no_btn.configure(bg=_BTN_ACT, fg=_TEXT_HI, font=_FONT_B)

        def _confirm(choice: int) -> None:
            popup.destroy()
            if choice == 0:
                self._do_restart()

        def _on_key(event: tk.Event) -> None:
            k = event.keysym
            if k in ("y", "Y"):
                _confirm(0)
            elif k in ("n", "N", "Escape"):
                _confirm(1)
            elif k in ("Left", "a"):
                sel[0] = 0; _highlight()
            elif k in ("Right", "d"):
                sel[0] = 1; _highlight()
            elif k in ("space", "Return"):
                _confirm(sel[0])

        popup.bind("<Key>", _on_key)
        popup.focus_set()

        # Centre over parent
        popup.update_idletasks()
        pw = popup.winfo_reqwidth()
        ph = popup.winfo_reqheight()
        px = self.winfo_rootx() + (self.winfo_width()  - pw) // 2
        py = self.winfo_rooty() + (self.winfo_height() - ph) // 2
        popup.geometry(f"+{px}+{py}")

    def _do_restart(self) -> None:
        import subprocess
        import sys
        subprocess.Popen([sys.executable] + sys.argv)
        self.winfo_toplevel().destroy()

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
        popup.update_idletasks()
        pw = popup.winfo_reqwidth()
        ph = popup.winfo_reqheight()
        px = self.winfo_rootx() + (self.winfo_width() - pw) // 2
        py = self.winfo_rooty() + (self.winfo_height() - ph) // 2
        popup.geometry(f"+{px}+{py}")
