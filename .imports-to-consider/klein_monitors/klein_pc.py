"""
klein_monitors/klein_pc.py

KleinPC — unified in-game computer: sidebar + content INSIDE a widescreen
CRT bezel.

    ┌────────────────────────────────────────────────────────────┐
    │  bezel / plastic frame                                     │
    │  ┌──────────┬─────────────────────────────────────────┐   │
    │  │ KleinOS  │                                         │   │
    │  │          │   active content:                       │   │
    │  │▶Terminal │     TerminalPane  or  AppPane            │   │
    │  │          │                                         │   │
    │  │▼ Apps    │                                         │   │
    │  │  • …     │                                         │   │
    │  │          │                                         │   │
    │  │⚙Settings │                                         │   │
    │  └──────────┴─────────────────────────────────────────┘   │
    └────────────────────────────────────────────────────────────┘

Usage:
    from klein_monitors import KleinPC, KleinApp

    pc = KleinPC(root, apps=[MyApp()])
    pc.show()
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

from klein_monitors.app_pane import AppPane
from klein_monitors.klein_app import KleinApp, KleinChat, KleinGame
from klein_monitors.retro_monitor_frame import RetroMonitorFrame
from klein_monitors.terminal_pane import TerminalPane

_ASSETS = Path(__file__).parent / "assets"

# ── Sidebar palette ──────────────────────────────────────────────────
_S_BG      = "#050a05"
_S_HEAD    = "#081208"
_S_BTN     = "#050a05"
_S_HOV     = "#0d2010"
_S_ACT     = "#0a3a0a"
_S_FG      = "#3a7a3a"
_S_FG_ON   = "#00dd33"
_S_FG_DIM  = "#1a4a1a"
_S_SEP     = "#0a180a"
_S_FONT    = ("Consolas", 9)
_S_FONT_H  = ("Consolas", 10, "bold")
_S_FONT_SM = ("Consolas", 8)
_S_WIDTH   = 148

_CONTENT_BG = "#010a01"
_WIN_BG     = "#050508"


class KleinPC:
    """
    Single in-game computer window — sidebar + content inside widescreen bezel.

    Parameters
    ----------
    root        : Tk root or any Toplevel
    apps        : list of KleinApp instances for the Apps section
    executor    : callable(text) -> str for the terminal; None = built-in shell
    title       : window title
    """

    def __init__(
        self,
        root: tk.Misc,
        *,
        apps: Optional[list] = None,
        games: Optional[list[KleinGame]] = None,
        chats: Optional[list[KleinChat]] = None,
        executor: Optional[Callable[[str], str]] = None,
        title: str = "KleinBOTTLE PC",
    ):
        self._root = root
        self._apps: list = apps or []
        self._games = games or []
        self._chats = chats or []
        self._executor = executor
        self._active_btn: Optional[tk.Button] = None

        self._window = tk.Toplevel(root)
        self._window.title(title)
        self._window.configure(bg=_WIN_BG)
        self._window.resizable(False, False)

        # The widescreen bezel is the only direct child
        self._monitor = RetroMonitorFrame(
            self._window,
            bezel_path=_ASSETS / "monitor_widescreen.png",
            rect_path=_ASSETS / "screen_rect_widescreen.json",
        )
        self._monitor.pack(padx=10, pady=10)

        # Inside .screen: sidebar on the left, content on the right
        self._monitor.screen.configure(bg=_CONTENT_BG)
        self._build_sidebar(self._monitor.screen)
        self._build_content(self._monitor.screen)

        self._select_terminal()
        self._window.withdraw()

    # ──────────────────────────────────────────────────────────────────
    # Sidebar
    # ──────────────────────────────────────────────────────────────────

    def _build_sidebar(self, parent: tk.Widget) -> None:
        sb = tk.Frame(parent, bg=_S_BG, width=_S_WIDTH)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        # Vertical separator
        tk.Frame(parent, bg=_S_SEP, width=1).pack(side="left", fill="y")

        # Header
        tk.Frame(sb, bg=_S_SEP, height=1).pack(fill="x")
        tk.Label(
            sb, text="KleinOS", bg=_S_HEAD, fg=_S_FG_ON,
            font=_S_FONT_H, pady=7,
        ).pack(fill="x")
        tk.Frame(sb, bg=_S_SEP, height=1).pack(fill="x")

        # Terminal
        self._btn_terminal = self._nav_btn(sb, "▶  Terminal", self._select_terminal)
        tk.Frame(sb, bg=_S_SEP, height=1).pack(fill="x")

        # Apps section — container keeps toggle + items as one unit so their
        # position in the sidebar never shifts when items are shown/hidden
        self._apps_expanded = True
        apps_section = tk.Frame(sb, bg=_S_BG)
        apps_section.pack(fill="x")
        self._apps_toggle_btn = self._nav_btn(
            apps_section, "▼  Apps", self._toggle_apps, dim=True
        )
        self._apps_frame = tk.Frame(apps_section, bg=_S_BG)
        self._apps_frame.pack(fill="x")
        self._app_btns: list[tuple[tk.Button, KleinApp]] = []
        for app in self._apps:
            self._add_app_btn(app)

        tk.Frame(sb, bg=_S_SEP, height=1).pack(fill="x")

        # Games section (only shown when games are registered)
        if self._games:
            self._games_expanded = True
            games_section = tk.Frame(sb, bg=_S_BG)
            games_section.pack(fill="x")
            self._games_toggle_btn = self._nav_btn(
                games_section, "▼  Games", self._toggle_games, dim=True
            )
            self._games_frame = tk.Frame(games_section, bg=_S_BG)
            self._games_frame.pack(fill="x")
            self._game_btns: list[tuple[tk.Button, KleinGame]] = []
            for game in self._games:
                self._add_game_btn(game)
            tk.Frame(sb, bg=_S_SEP, height=1).pack(fill="x")

        # Chat section (only shown when chats are registered)
        if self._chats:
            self._chats_expanded = True
            chats_section = tk.Frame(sb, bg=_S_BG)
            chats_section.pack(fill="x")
            self._chats_toggle_btn = self._nav_btn(
                chats_section, "▼  Chat", self._toggle_chats, dim=True
            )
            self._chats_frame = tk.Frame(chats_section, bg=_S_BG)
            self._chats_frame.pack(fill="x")
            self._chat_btns: list[tuple[tk.Button, KleinChat]] = []
            for chat in self._chats:
                self._add_chat_btn(chat)
            tk.Frame(sb, bg=_S_SEP, height=1).pack(fill="x")

        # Settings
        self._btn_settings = self._nav_btn(sb, "⚙  Settings", self._select_settings)
        tk.Frame(sb, bg=_S_SEP, height=1).pack(fill="x")

        tk.Frame(sb, bg=_S_BG).pack(fill="both", expand=True)

    def _nav_btn(
        self,
        parent: tk.Widget,
        label: str,
        command: Callable,
        dim: bool = False,
    ) -> tk.Button:
        fg = _S_FG_DIM if dim else _S_FG
        btn = tk.Button(
            parent,
            text=label,
            command=command,
            bg=_S_BTN,
            fg=fg,
            activebackground=_S_HOV,
            activeforeground=_S_FG_ON,
            font=_S_FONT if not dim else _S_FONT_SM,
            relief="flat",
            anchor="w",
            padx=10,
            pady=5,
            bd=0,
            cursor="hand2",
        )
        btn.pack(fill="x")
        btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=_S_HOV, fg=_S_FG_ON))
        btn.bind("<Leave>", lambda e, b=btn, f=fg: b.configure(
            bg=_S_ACT if b is self._active_btn else _S_BTN,
            fg=_S_FG_ON if b is self._active_btn else f,
        ))
        return btn

    def _add_app_btn(self, app) -> tk.Button:
        btn = tk.Button(
            self._apps_frame,
            text=f"    {app.title}",
            command=lambda a=app: self._select_app(a),
            bg=_S_BTN,
            fg=_S_FG,
            activebackground=_S_HOV,
            activeforeground=_S_FG_ON,
            font=_S_FONT_SM,
            relief="flat",
            anchor="w",
            padx=10,
            pady=4,
            bd=0,
            cursor="hand2",
        )
        btn.pack(fill="x")
        btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=_S_HOV, fg=_S_FG_ON))
        btn.bind("<Leave>", lambda e, b=btn: b.configure(
            bg=_S_ACT if b is self._active_btn else _S_BTN,
            fg=_S_FG_ON if b is self._active_btn else _S_FG,
        ))
        self._app_btns.append((btn, app))
        return btn

    def _add_game_btn(self, game: KleinGame) -> tk.Button:
        btn = tk.Button(
            self._games_frame,
            text=f"    {game.title}",
            command=lambda g=game: self._select_game(g),
            bg=_S_BTN, fg=_S_FG,
            activebackground=_S_HOV, activeforeground=_S_FG_ON,
            font=_S_FONT_SM, relief="flat", anchor="w",
            padx=10, pady=4, bd=0, cursor="hand2",
        )
        btn.pack(fill="x")
        btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=_S_HOV, fg=_S_FG_ON))
        btn.bind("<Leave>", lambda e, b=btn: b.configure(
            bg=_S_ACT if b is self._active_btn else _S_BTN,
            fg=_S_FG_ON if b is self._active_btn else _S_FG,
        ))
        self._game_btns.append((btn, game))
        return btn

    def _set_active(self, btn: Optional[tk.Button]) -> None:
        if self._active_btn:
            self._active_btn.configure(bg=_S_BTN, fg=_S_FG)
        self._active_btn = btn
        if btn:
            btn.configure(bg=_S_ACT, fg=_S_FG_ON)

    # ──────────────────────────────────────────────────────────────────
    # Content area
    # ──────────────────────────────────────────────────────────────────

    def _build_content(self, parent: tk.Widget) -> None:
        self._content = tk.Frame(parent, bg=_CONTENT_BG)
        self._content.pack(side="left", fill="both", expand=True)

    def _swap(self, factory: Callable[[], tk.Widget]) -> None:
        for w in self._content.winfo_children():
            w.destroy()
        widget = factory()
        widget.pack(fill="both", expand=True)
        # Give keyboard focus to the first Entry or Text inside the new content
        self._window.after(50, lambda: self._focus_first_input(widget))

    @staticmethod
    def _focus_first_input(parent: tk.Widget) -> None:
        for w in parent.winfo_children():
            if isinstance(w, (tk.Entry, tk.Text)):
                w.focus_set()
                return
            KleinPC._focus_first_input(w)

    # ──────────────────────────────────────────────────────────────────
    # Navigation actions
    # ──────────────────────────────────────────────────────────────────

    def _select_terminal(self) -> None:
        self._set_active(self._btn_terminal)
        self._swap(lambda: TerminalPane(self._content, executor=self._executor))

    def _select_app(self, app) -> None:
        for btn, a in self._app_btns:
            if a is app:
                self._set_active(btn)
                break
        if isinstance(app, KleinChat):
            self._swap(lambda a=app: a.create(self._content, on_exit=self._select_terminal))
        else:
            self._swap(lambda a=app: AppPane(self._content, app=a))

    def _select_game(self, game: KleinGame) -> None:
        for btn, g in self._game_btns:
            if g is game:
                self._set_active(btn)
                break
        self._swap(lambda g=game: g.create(self._content, on_exit=self._select_terminal))

    def _add_chat_btn(self, chat: KleinChat) -> tk.Button:
        btn = tk.Button(
            self._chats_frame,
            text=f"    {chat.title}",
            command=lambda c=chat: self._select_chat(c),
            bg=_S_BTN, fg=_S_FG,
            activebackground=_S_HOV, activeforeground=_S_FG_ON,
            font=_S_FONT_SM, relief="flat", anchor="w",
            padx=10, pady=4, bd=0, cursor="hand2",
        )
        btn.pack(fill="x")
        btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=_S_HOV, fg=_S_FG_ON))
        btn.bind("<Leave>", lambda e, b=btn: b.configure(
            bg=_S_ACT if b is self._active_btn else _S_BTN,
            fg=_S_FG_ON if b is self._active_btn else _S_FG,
        ))
        self._chat_btns.append((btn, chat))
        return btn

    def _select_chat(self, chat: KleinChat) -> None:
        for btn, c in self._chat_btns:
            if c is chat:
                self._set_active(btn)
                break
        self._swap(lambda c=chat: c.create(self._content, on_exit=self._select_terminal))

    def _toggle_chats(self) -> None:
        if self._chats_expanded:
            self._chats_frame.pack_forget()
            self._chats_toggle_btn.configure(text="▶  Chat")
        else:
            self._chats_frame.pack(fill="x", after=self._chats_toggle_btn)
            self._chats_toggle_btn.configure(text="▼  Chat")
        self._chats_expanded = not self._chats_expanded

    def _toggle_games(self) -> None:
        if self._games_expanded:
            self._games_frame.pack_forget()
            self._games_toggle_btn.configure(text="▶  Games")
        else:
            self._games_frame.pack(fill="x", after=self._games_toggle_btn)
            self._games_toggle_btn.configure(text="▼  Games")
        self._games_expanded = not self._games_expanded

    def _select_settings(self) -> None:
        self._set_active(self._btn_settings)

        class _SettingsApp(KleinApp):
            title = "Settings"
            def commands(self_):
                return [
                    ("Display", lambda: "Resolution: 760×480\nBezel: green phosphor\nScanlines: on"),
                    ("Sound",   lambda: "Volume: 80%\nMusic: on\nEffects: on"),
                    ("About",   lambda: "KleinOS v1.0\nBuilt with Python + Tkinter.\nPart of KleinBOTTLE."),
                ]

        self._swap(lambda: AppPane(self._content, app=_SettingsApp()))

    def _toggle_apps(self) -> None:
        if self._apps_expanded:
            self._apps_frame.pack_forget()
            self._apps_toggle_btn.configure(text="▶  Apps")
        else:
            # pack after the toggle button so order is always toggle → items
            self._apps_frame.pack(fill="x", after=self._apps_toggle_btn)
            self._apps_toggle_btn.configure(text="▼  Apps")
        self._apps_expanded = not self._apps_expanded

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def show(self) -> None:
        self._window.deiconify()
        self._window.lift()

    def hide(self) -> None:
        self._window.withdraw()

    def add_app(self, app: KleinApp) -> None:
        """Register a new app into the Apps section at runtime."""
        self._apps.append(app)
        self._add_app_btn(app)
        if not self._apps_expanded:
            self._apps_frame.pack(fill="x")
            self._apps_toggle_btn.configure(text="▼  Apps")
            self._apps_expanded = True

    def set_executor(self, executor: Callable[[str], str]) -> None:
        self._executor = executor

    @property
    def window(self) -> tk.Toplevel:
        return self._window
