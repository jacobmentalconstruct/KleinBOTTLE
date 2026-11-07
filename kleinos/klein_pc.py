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
    from kleinos import KleinPC, KleinApp

    pc = KleinPC(root, apps=[MyApp()])
    pc.show()
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

from kleinos.app_pane import AppPane
from kleinos.klein_app import KleinApp, KleinChat, KleinGame
from kleinos.retro_monitor_frame import RetroMonitorFrame
from kleinos.terminal_pane import TerminalPane
from kleinos import audio as _audio
from kleinos import config as _config

_ASSETS = Path(__file__).parent / "assets"
_LAYOUT_PATH = Path(__file__).resolve().parent.parent / "data" / "kleinos_layout.json"

# ── Sidebar palette ──────────────────────────────────────────────────
from kleinos.palette import (
    BG2 as _S_BG, HEAD as _S_HEAD, HOV as _S_HOV, ACT as _S_ACT,
    FG as _S_FG, FG_ON as _S_FG_ON, FG_DIM as _S_FG_DIM, SEP as _S_SEP,
    BG as _CONTENT_BG,
)
_S_BTN     = _S_BG
_S_FONT    = ("Consolas", 9)
_S_FONT_H  = ("Consolas", 10, "bold")
_S_FONT_SM = ("Consolas", 8)
_S_WIDTH   = 148

_WIN_BG = "#050508"   # outer CRT bezel — constant across palettes


# ── Tooltip ──────────────────────────────────────────────────────────

class _Tooltip:
    """Hover tooltip for sidebar buttons."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self._widget = widget
        self._text = text
        self._win: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._show, add=True)
        widget.bind("<Leave>", self._hide, add=True)

    def _show(self, event: tk.Event) -> None:
        if not self._text or self._win:
            return
        x = event.x_root + 14
        y = event.y_root - 2
        self._win = tk.Toplevel(self._widget)
        self._win.wm_overrideredirect(True)
        self._win.wm_geometry(f"+{x}+{y}")
        self._win.wm_attributes("-topmost", True)
        tk.Label(
            self._win,
            text=self._text,
            bg=_S_HEAD,
            fg=_S_FG_ON,
            font=("Consolas", 8),
            relief="flat",
            padx=8,
            pady=4,
            wraplength=220,
            justify="left",
        ).pack()

    def _hide(self, event: Optional[tk.Event] = None) -> None:
        if self._win:
            self._win.destroy()
            self._win = None


# ── KleinPC ──────────────────────────────────────────────────────────

class KleinPC:
    """
    Single in-game computer window — sidebar + content inside widescreen bezel.

    Parameters
    ----------
    root        : Tk root or any Toplevel
    apps        : list of KleinApp/KleinChat instances
    games       : list of KleinGame instances
    chats       : list of KleinChat instances (deprecated; use apps)
    executor    : callable(text) -> str for the terminal; None = built-in shell
    title       : window title
    layout_path : path to kleinos_layout.json
    """

    def __init__(
        self,
        root: tk.Misc,
        *,
        apps: Optional[list] = None,
        games: Optional[list] = None,
        chats: Optional[list[KleinChat]] = None,
        executor: Optional[Callable[[str], str]] = None,
        title: str = "KleinBOTTLE PC",
        layout_path: Path = _LAYOUT_PATH,
        embedded_in: Optional[tk.Frame] = None,
        on_exit: Optional[Callable[[], None]] = None,
        scale: Optional[float] = None,
    ):
        _startup_cfg = _config.load()
        _audio.configure(_startup_cfg)
        self._root = root
        self._apps: list = apps or []
        self._games: list = games or []
        self._chats: list = chats or []
        self._executor = executor
        self._layout_path = layout_path
        self._on_exit = on_exit
        self._active_btn: Optional[tk.Button] = None
        self._active_title: Optional[str] = None
        self._item_btns: dict[str, tk.Button] = {}

        # Title → item lookup
        self._item_pool: dict[str, object] = {}
        for item in self._apps + self._games + self._chats:
            self._item_pool[item.title] = item

        # Load or initialise layout
        self._layout = self._load_layout()
        if not self._layout.get("categories"):
            self._init_default_layout()
        else:
            self._sync_layout_with_pool()

        _scale = scale if scale is not None else _config._PC_SIZES.get(_startup_cfg.get("pc_size", "medium"), 1.0)

        if embedded_in is not None:
            # Embedded view-swap mode — no separate Toplevel
            self._window: Optional[tk.Toplevel] = None
            _container: tk.Misc = embedded_in
        else:
            self._window = tk.Toplevel(root)
            self._window.title(title)
            self._window.configure(bg=_WIN_BG)
            self._window.resizable(False, False)
            _container = self._window

        self._monitor = RetroMonitorFrame(
            _container,
            bezel_path=_ASSETS / "monitor_widescreen.png",
            rect_path=_ASSETS / "screen_rect_widescreen.json",
            scale=_scale,
        )
        self._monitor.pack(padx=10, pady=10)

        self._monitor.screen.configure(bg=_CONTENT_BG)
        self._build_sidebar(self._monitor.screen)
        self._build_content(self._monitor.screen)

        self._select_terminal()
        if self._window is not None:
            self._window.withdraw()

    # ──────────────────────────────────────────────────────────────────
    # Layout persistence
    # ──────────────────────────────────────────────────────────────────

    def _load_layout(self) -> dict:
        try:
            return json.loads(self._layout_path.read_text(encoding="utf-8"))
        except Exception:
            return {"categories": []}

    def _save_layout(self) -> None:
        cats = []
        for cat in self._layout["categories"]:
            cats.append({
                "id":       cat["id"],
                "label":    cat["label"],
                "expanded": cat["expanded"],
                "items":    list(cat["items"]),
            })
        try:
            self._layout_path.write_text(
                json.dumps({
                    "top_level_items": list(self._layout.get("top_level_items", [])),
                    "categories": cats,
                }, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _init_default_layout(self) -> None:
        app_chat_titles = [i.title for i in self._apps + self._chats]
        game_titles     = [i.title for i in self._games]
        cats = []
        if app_chat_titles:
            cats.append({"id": "cat-apps", "label": "Apps",
                         "expanded": True, "items": app_chat_titles})
        if game_titles:
            cats.append({"id": "cat-games", "label": "Games",
                         "expanded": True, "items": game_titles})
        self._layout = {"top_level_items": [], "categories": cats}
        self._save_layout()

    def _sync_layout_with_pool(self) -> None:
        """Add items registered in code but absent from the saved layout to top level."""
        if "top_level_items" not in self._layout:
            self._layout["top_level_items"] = []
        all_listed: set[str] = set(self._layout["top_level_items"])
        for cat in self._layout["categories"]:
            all_listed.update(cat["items"])
        missing = [t for t in self._item_pool if t not in all_listed]
        if missing:
            self._layout["top_level_items"].extend(missing)
            self._save_layout()

    # ──────────────────────────────────────────────────────────────────
    # Sidebar construction
    # ──────────────────────────────────────────────────────────────────

    def _build_sidebar(self, parent: tk.Widget) -> None:
        sb = tk.Frame(parent, bg=_S_BG, width=_S_WIDTH)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        tk.Frame(parent, bg=_S_SEP, width=1).pack(side="left", fill="y")

        # Header
        tk.Frame(sb, bg=_S_SEP, height=1).pack(fill="x")
        tk.Label(sb, text="KleinOS", bg=_S_HEAD, fg=_S_FG_ON,
                 font=_S_FONT_H, pady=7).pack(fill="x")
        tk.Frame(sb, bg=_S_SEP, height=1).pack(fill="x")

        # Terminal — fixed, never in a category
        self._btn_terminal = self._nav_btn(
            sb, "▶  Terminal", self._select_terminal,
            tooltip="Open the KleinOS terminal",
        )
        tk.Frame(sb, bg=_S_SEP, height=1).pack(fill="x")

        # Dynamic category body — rebuilt when layout changes
        self._sb_body = tk.Frame(sb, bg=_S_BG)
        self._sb_body.pack(fill="x")
        self._populate_categories()

        # Footer
        tk.Frame(sb, bg=_S_SEP, height=1).pack(fill="x")
        self._btn_settings = self._nav_btn(
            sb, "⚙  Settings", self._select_settings,
            tooltip="Manage categories and preferences",
        )
        if self._on_exit is not None:
            tk.Frame(sb, bg=_S_SEP, height=1).pack(fill="x")
            self._nav_btn(sb, "← Back", self._on_exit,
                          tooltip="Return to text adventure")
        tk.Frame(sb, bg=_S_SEP, height=1).pack(fill="x")
        tk.Frame(sb, bg=_S_BG).pack(fill="both", expand=True)

    def _populate_categories(self) -> None:
        """Rebuild the category section from the current layout."""
        # Identify if an item button is currently active
        active_title: Optional[str] = None
        for title, btn in self._item_btns.items():
            if btn is self._active_btn:
                active_title = title
                break

        for w in self._sb_body.winfo_children():
            w.destroy()
        self._item_btns.clear()

        # Clear active_btn only if it was an item button (now destroyed)
        btn_terminal = getattr(self, "_btn_terminal", None)
        btn_settings = getattr(self, "_btn_settings", None)
        if self._active_btn not in (btn_terminal, btn_settings):
            self._active_btn = None

        # Top-level (ungrouped) items — same visual level as Terminal
        for title in self._layout.get("top_level_items", []):
            item = self._item_pool.get(title)
            if item is not None:
                self._add_toplevel_btn(self._sb_body, item)

        for cat in self._layout["categories"]:
            self._add_category_section(cat)

        # Restore highlight on rebuilt item button
        if active_title and active_title in self._item_btns:
            self._active_btn = self._item_btns[active_title]
            self._active_btn.configure(bg=_S_ACT, fg=_S_FG_ON)

    def _add_category_section(self, cat: dict) -> None:
        arrow = "▼" if cat["expanded"] else "▶"
        section = tk.Frame(self._sb_body, bg=_S_BG)
        section.pack(fill="x")

        toggle_btn = self._nav_btn(
            section,
            f"{arrow}  {cat['label']}",
            lambda c=cat: self._toggle_category(c),
            dim=True,
        )

        items_frame = tk.Frame(section, bg=_S_BG)
        if cat["expanded"]:
            items_frame.pack(fill="x")

        for title in cat["items"]:
            item = self._item_pool.get(title)
            if item is not None:
                self._add_item_btn(items_frame, item)

        # Store live UI refs in the cat dict for toggle and in-place rename
        cat["_toggle_btn"]  = toggle_btn
        cat["_items_frame"] = items_frame

        tk.Frame(self._sb_body, bg=_S_SEP, height=1).pack(fill="x")

    def _add_toplevel_btn(self, parent: tk.Frame, item: object) -> tk.Button:
        desc = getattr(item, "description", "")
        btn = self._nav_btn(
            parent,
            f"·  {item.title}",  # type: ignore[attr-defined]
            lambda i=item: self._select_item(i),
            tooltip=desc,
        )
        btn.bind("<Button-3>", lambda e, i=item: self._show_item_menu(i, e))
        self._item_btns[item.title] = btn  # type: ignore[attr-defined]
        return btn

    def _add_item_btn(self, parent: tk.Frame, item: object) -> tk.Button:
        desc = getattr(item, "description", "")
        btn = tk.Button(
            parent,
            text=f"    {item.title}",  # type: ignore[attr-defined]
            command=lambda i=item: self._select_item(i),
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
        btn.bind("<Button-3>", lambda e, i=item: self._show_item_menu(i, e))
        if desc:
            _Tooltip(btn, desc)
        self._item_btns[item.title] = btn  # type: ignore[attr-defined]
        return btn

    def _nav_btn(
        self,
        parent: tk.Widget,
        label: str,
        command: Callable,
        dim: bool = False,
        tooltip: str = "",
    ) -> tk.Button:
        fg = _S_FG_DIM if dim else _S_FG
        btn = tk.Button(
            parent,
            text=label,
            command=command,
            bg=_S_BTN, fg=fg,
            activebackground=_S_HOV, activeforeground=_S_FG_ON,
            font=_S_FONT if not dim else _S_FONT_SM,
            relief="flat", anchor="w",
            padx=10, pady=5, bd=0, cursor="hand2",
        )
        btn.pack(fill="x")
        btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=_S_HOV, fg=_S_FG_ON))
        btn.bind("<Leave>", lambda e, b=btn, f=fg: b.configure(
            bg=_S_ACT if b is self._active_btn else _S_BTN,
            fg=_S_FG_ON if b is self._active_btn else f,
        ))
        if tooltip:
            _Tooltip(btn, tooltip)
        return btn

    def _toggle_category(self, cat: dict) -> None:
        cat["expanded"] = not cat["expanded"]
        if cat["expanded"]:
            cat["_items_frame"].pack(fill="x", after=cat["_toggle_btn"])
            cat["_toggle_btn"].configure(text=f"▼  {cat['label']}")
        else:
            cat["_items_frame"].pack_forget()
            cat["_toggle_btn"].configure(text=f"▶  {cat['label']}")
        self._save_layout()

    def _set_active(self, btn: Optional[tk.Button], title: Optional[str] = None) -> None:
        if self._active_btn:
            try:
                self._active_btn.configure(bg=_S_BTN, fg=_S_FG)
            except tk.TclError:
                pass
        self._active_btn = btn
        self._active_title = title
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
        _after_widget = self._window if self._window is not None else self._content
        _after_widget.after(50, lambda: self._focus_first_input(widget))

    @staticmethod
    def _focus_first_input(parent: tk.Widget) -> None:
        for w in parent.winfo_children():
            if isinstance(w, (tk.Entry, tk.Text)):
                w.focus_set()
                return
            KleinPC._focus_first_input(w)

    # ──────────────────────────────────────────────────────────────────
    # Navigation
    # ──────────────────────────────────────────────────────────────────

    def _select_terminal(self) -> None:
        self._set_active(self._btn_terminal)
        self._swap(lambda: TerminalPane(self._content, executor=self._executor))

    def _select_item(self, item: object) -> None:
        btn = self._item_btns.get(item.title)  # type: ignore[attr-defined]
        self._set_active(btn, item.title)  # type: ignore[attr-defined]
        if hasattr(item, "create"):
            self._swap(lambda i=item: i.create(self._content, on_exit=self._select_terminal))
        else:
            self._swap(lambda i=item: AppPane(self._content, app=i, on_exit=self._select_terminal))

    def _select_settings(self) -> None:
        from kleinos.settings_pane import SettingsPane
        self._set_active(self._btn_settings)
        self._swap(lambda: SettingsPane(
            self._content,
            on_exit=self._select_terminal,
            get_layout=lambda: self._layout,
            add_category=self._add_category,
            delete_category=self._delete_category,
            rename_category=self._rename_category,
        ))

    # ──────────────────────────────────────────────────────────────────
    # Layout management (called from SettingsPane)
    # ──────────────────────────────────────────────────────────────────

    def _add_category(self, name: str) -> None:
        import uuid
        cat_id = f"cat-{uuid.uuid4().hex[:8]}"
        self._layout["categories"].append({
            "id": cat_id, "label": name, "expanded": True, "items": [],
        })
        self._save_layout()
        self._populate_categories()

    def _delete_category(self, cat_id: str) -> None:
        cats = self._layout["categories"]
        for cat in cats:
            if cat["id"] == cat_id:
                self._layout.setdefault("top_level_items", []).extend(cat["items"])
                break
        self._layout["categories"] = [c for c in cats if c["id"] != cat_id]
        self._save_layout()
        self._populate_categories()

    def _rename_category(self, cat_id: str, new_name: str) -> None:
        for cat in self._layout["categories"]:
            if cat["id"] == cat_id:
                cat["label"] = new_name
                if "_toggle_btn" in cat:
                    arrow = "▼" if cat["expanded"] else "▶"
                    cat["_toggle_btn"].configure(text=f"{arrow}  {new_name}")
                break
        self._save_layout()

    # ──────────────────────────────────────────────────────────────────
    # Right-click item menu
    # ──────────────────────────────────────────────────────────────────

    def _show_item_menu(self, item: object, event: tk.Event) -> None:
        title: str = item.title  # type: ignore[attr-defined]

        current_cat_id: Optional[str] = None
        for cat in self._layout["categories"]:
            if title in cat["items"]:
                current_cat_id = cat["id"]
                break

        menu = tk.Menu(
            self._window, tearoff=0,
            bg=_S_BTN, fg=_S_FG_ON,
            activebackground=_S_HOV, activeforeground=_S_FG_ON,
            relief="flat", bd=1,
        )
        sub = tk.Menu(
            menu, tearoff=0,
            bg=_S_BTN, fg=_S_FG_ON,
            activebackground=_S_HOV, activeforeground=_S_FG_ON,
            relief="flat", bd=1,
        )

        has_dest = False
        if current_cat_id is not None:
            sub.add_command(
                label="  Top level",
                command=lambda: self._move_item(title, "__top__"),
            )
            has_dest = True
        for cat in self._layout["categories"]:
            if cat["id"] != current_cat_id:
                sub.add_command(
                    label=f"  {cat['label']}",
                    command=lambda cid=cat["id"]: self._move_item(title, cid),
                )
                has_dest = True

        if has_dest:
            sub.add_separator()
        sub.add_command(
            label="  + New category",
            command=lambda: self._quick_add_category_move(title),
        )

        menu.add_cascade(label="Move to", menu=sub)
        menu.tk_popup(event.x_root, event.y_root)

    def _move_item(self, title: str, to_cat_id: str) -> None:
        tl = self._layout.setdefault("top_level_items", [])
        if title in tl:
            tl.remove(title)
        for cat in self._layout["categories"]:
            if title in cat["items"]:
                cat["items"].remove(title)
        if to_cat_id == "__top__":
            tl.append(title)
        else:
            for cat in self._layout["categories"]:
                if cat["id"] == to_cat_id:
                    cat["items"].append(title)
                    break
        self._save_layout()
        self._populate_categories()

    def _quick_add_category_move(self, item_title: str) -> None:
        from tkinter import simpledialog
        import uuid
        name = simpledialog.askstring(
            "New category", "Category name:",
            parent=self._window,
        )
        if not name or not name.strip():
            return
        cat_id = f"cat-{uuid.uuid4().hex[:8]}"
        self._layout["categories"].append({
            "id": cat_id, "label": name.strip(), "expanded": True, "items": [],
        })
        self._move_item(item_title, cat_id)

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def show(self) -> None:
        if self._window is None:
            return  # embedded mode — always visible
        # On first show, position window offset from root so it doesn't stack on top
        if self._window.winfo_x() == 0 and self._window.winfo_y() == 0:
            root = self._window.master
            try:
                rx = root.winfo_x()  # type: ignore[union-attr]
                ry = root.winfo_y()  # type: ignore[union-attr]
                rw = root.winfo_width()  # type: ignore[union-attr]
                # Open to the right of the main window; fall back to a fixed offset
                x = rx + rw + 20
                y = ry + 40
                self._window.geometry(f"+{x}+{y}")
            except Exception:
                self._window.geometry("+80+80")
        self._window.deiconify()
        self._window.lift()

    def hide(self) -> None:
        if self._window is not None:
            self._window.withdraw()

    def add_app(self, app: KleinApp) -> None:
        """Register a new app as a top-level sidebar item."""
        self._apps.append(app)
        self._item_pool[app.title] = app
        self._layout.setdefault("top_level_items", []).append(app.title)
        self._save_layout()
        self._populate_categories()

    def set_executor(self, executor: Callable[[str], str]) -> None:
        self._executor = executor

    @property
    def window(self) -> Optional[tk.Toplevel]:
        return self._window
