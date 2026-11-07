"""Tkinter play surface: structured room display over the standalone game session."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import queue
import threading
from typing import Optional, Callable

from ..game import GameSession, RoomSnapshot
from ..ollama_phone import OllamaPhoneError, chat

# ── Terminal palette ──────────────────────────────────────────────────────────
_BG     = "#010a01"
_BORDER = "#003300"
_FG     = "#00cc33"
_DIM    = "#005500"
_HDR_BG = "#001a00"


def _mk_btn(parent: tk.Widget, text: str, command, fg: str = _FG) -> tk.Button:
    return tk.Button(
        parent, text=text, bg=_BG, fg=fg,
        activebackground="#001a00", activeforeground=_FG,
        relief="flat", font=("Consolas", 8),
        cursor="hand2", command=command,
    )


class _Section(tk.Frame):
    """Thin-bordered box with optional header label and an .inner content frame."""

    def __init__(self, parent: tk.Widget, header: str = ""):
        super().__init__(parent, bg=_BG,
                         highlightthickness=1, highlightbackground=_BORDER)
        if header:
            tk.Label(self, text=f" {header} ", bg=_HDR_BG, fg=_DIM,
                     font=("Consolas", 7), anchor="w").pack(fill="x")
        self.inner = tk.Frame(self, bg=_BG)
        self.inner.pack(fill="x", padx=6, pady=(4, 4))


class GameSurface(tk.Frame):
    def __init__(self, master: tk.Misc, session: GameSession):
        super().__init__(master, bg=_BG)
        self.session = session
        self.command  = tk.StringVar()
        self.location = tk.StringVar()
        self.inventory_var = tk.StringVar()
        self._phone_results: queue.Queue = queue.Queue()
        self._phone_busy   = False
        self._request_serial = 0
        self._computer_cb: Optional[Callable] = None
        self._computer_window = None
        self._build()
        self.refresh_room()

    def set_computer_callback(self, cb: Callable) -> None:
        self._computer_cb = cb

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # ── Title bar ─────────────────────────────────────────────────
        top = tk.Frame(self, bg=_BG)
        top.pack(fill="x", padx=6, pady=(6, 4))
        self._title_lbl = tk.Label(
            top, text=self.session.world.get("name", "Adventure"),
            bg=_BG, fg=_FG, font=("Consolas", 14, "bold"), anchor="w",
        )
        self._title_lbl.pack(side="left")
        _mk_btn(top, "↺ Reload", self.reload_world, fg=_DIM).pack(side="right")

        # ── Body: main column + right sidebar ─────────────────────────
        body = tk.Frame(self, bg=_BG)
        body.pack(fill="both", expand=True)

        sidebar = tk.Frame(body, bg=_BG, width=200)
        sidebar.pack_propagate(False)
        sidebar.pack(side="right", fill="y", padx=(6, 4), pady=4)
        self._build_sidebar(sidebar)

        main = tk.Frame(body, bg=_BG)
        main.pack(side="left", fill="both", expand=True)

        self._main_col = main      # exposed: KleinAdventurePane injects image above _story_frame

        # ── Bottom-fixed sections (packed first so they always get space) ──
        actions_sec = _Section(main, "ACTIONS")
        actions_sec.pack(side="bottom", fill="x", padx=4, pady=(2, 4))
        self._actions_inner = actions_sec.inner

        cmd_sec = _Section(main, "COMMAND")
        cmd_sec.pack(side="bottom", fill="x", padx=4, pady=(2, 2))
        self.entry = tk.Entry(
            cmd_sec.inner, textvariable=self.command,
            bg=_BG, fg=_FG, insertbackground=_FG,
            font=("Consolas", 9), relief="flat",
            highlightthickness=1, highlightbackground=_BORDER,
            highlightcolor=_FG,
        )
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self._submit)
        tk.Button(
            cmd_sec.inner, text="Run",
            bg="#003300", fg=_FG,
            activebackground="#005500", activeforeground=_FG,
            relief="flat", font=("Consolas", 9, "bold"),
            cursor="hand2", command=self._submit,
        ).pack(side="left", padx=(6, 0))

        # ── Scrollable content area ────────────────────────────────────
        self._story_frame = tk.Frame(main, bg=_BG)  # anchor for image panel injection
        self._story_frame.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(self._story_frame, bg=_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self._story_frame, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._sections = tk.Frame(self._canvas, bg=_BG)
        self._win_id = self._canvas.create_window((0, 0), window=self._sections, anchor="nw")
        self._sections.bind("<Configure>", lambda _e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind("<Enter>",
            lambda _e: self._canvas.bind_all("<MouseWheel>", self._on_mwheel))
        self._canvas.bind("<Leave>",
            lambda _e: self._canvas.unbind_all("<MouseWheel>"))

        # ── Content sections ──────────────────────────────────────────
        self._desc_sec = _Section(self._sections)
        self._desc_sec.pack(fill="x", padx=4, pady=(4, 0))
        self._desc_lbl = tk.Label(
            self._desc_sec.inner, text="", bg=_BG, fg=_FG,
            font=("Consolas", 9), justify="left", anchor="nw", wraplength=380,
        )
        self._desc_lbl.pack(fill="x")

        self._atmo_sec = _Section(self._sections, "ATMOSPHERE")
        # packed dynamically

        self._objs_sec = _Section(self._sections, "OBJECTS")
        # packed dynamically

        self._actors_sec = _Section(self._sections, "PRESENT")
        # packed dynamically

        self._resp_sec = _Section(self._sections, ">")
        self._resp_sec.pack(fill="x", padx=4, pady=(3, 4))
        self._resp_lbl = tk.Label(
            self._resp_sec.inner, text="", bg=_BG, fg=_FG,
            font=("Consolas", 9), justify="left", anchor="nw", wraplength=380,
        )
        self._resp_lbl.pack(fill="x")

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self, sidebar: tk.Frame) -> None:
        def hdr(text: str) -> None:
            tk.Label(sidebar, text=text, bg=_BG, fg=_DIM,
                     font=("Consolas", 8, "bold"), anchor="w").pack(anchor="w", pady=(8, 1))

        hdr("EXITS")
        self.exit_frame = tk.Frame(sidebar, bg=_BG)
        self.exit_frame.pack(fill="x", pady=(0, 4))
        hdr("INVENTORY")
        tk.Label(sidebar, textvariable=self.inventory_var, bg=_BG, fg=_FG,
                 font=("Consolas", 9), anchor="w", justify="left",
                 wraplength=180).pack(anchor="w")

    # ── Canvas resize ─────────────────────────────────────────────────────────

    def _on_canvas_resize(self, event: tk.Event) -> None:
        self._canvas.itemconfig(self._win_id, width=event.width)
        wrap = max(150, event.width - 24)
        self._desc_lbl.configure(wraplength=wrap)
        self._resp_lbl.configure(wraplength=wrap)

    def _on_mwheel(self, event: tk.Event) -> None:
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── Room refresh ──────────────────────────────────────────────────────────

    def refresh_room(self) -> None:
        snap = self.session.room_snapshot()

        # Description
        self._desc_lbl.configure(text=snap.description)

        # Atmosphere — show only if populated
        self._clear(self._atmo_sec.inner)
        if snap.environment:
            for key, val in snap.environment:
                tk.Label(self._atmo_sec.inner, text=f"{key}: {val}",
                         bg=_BG, fg=_DIM, font=("Consolas", 9),
                         anchor="w").pack(fill="x")
            self._atmo_sec.pack(fill="x", padx=4, pady=(3, 0))
        else:
            self._atmo_sec.pack_forget()

        # Objects
        self._clear(self._objs_sec.inner)
        if snap.objects:
            wrap = max(80, self._canvas.winfo_width() - 194)
            for obj in snap.objects:
                self._make_expandable_row(
                    self._objs_sec.inner,
                    name=obj.name,
                    short_desc=obj.short_desc,
                    detail=obj.description,
                    wrap=wrap,
                )
            self._objs_sec.pack(fill="x", padx=4, pady=(3, 0))
        else:
            self._objs_sec.pack_forget()

        # Actors / NPCs
        self._clear(self._actors_sec.inner)
        if snap.actors:
            wrap = max(80, self._canvas.winfo_width() - 194)
            for actor in snap.actors:
                brief = actor.short_desc.split(".")[0].strip() if actor.short_desc else ""
                self._make_expandable_row(
                    self._actors_sec.inner,
                    name=actor.name,
                    short_desc=brief,
                    detail=actor.description,
                    wrap=wrap,
                )
            self._actors_sec.pack(fill="x", padx=4, pady=(3, 0))
        else:
            self._actors_sec.pack_forget()

        # Actions buttons
        self._refresh_actions(snap)

        # Sidebar
        self._sync(snap)

    def _make_expandable_row(
        self, parent: tk.Frame, *, name: str, short_desc: str, detail: str, wrap: int
    ) -> None:
        """A clickable header row that toggles a detail panel below it."""
        container = tk.Frame(parent, bg=_BG)
        container.pack(fill="x", pady=1)

        expanded = [False]

        detail_frame = tk.Frame(parent, bg=_BG)
        detail_lbl = tk.Label(
            detail_frame, text=detail or "(no description)",
            bg=_BG, fg=_FG, font=("Consolas", 9),
            justify="left", anchor="nw", wraplength=wrap,
        )
        detail_lbl.pack(fill="x", padx=(18, 0), pady=(2, 4))

        arrow_lbl = tk.Label(container, text="▶", bg=_BG, fg=_DIM,
                             font=("Consolas", 9), cursor="hand2")
        arrow_lbl.pack(side="left")

        name_lbl = tk.Label(container, text=name, bg=_BG, fg=_FG,
                            font=("Consolas", 9, "bold"), anchor="w",
                            width=20, cursor="hand2")
        name_lbl.pack(side="left")

        if short_desc:
            tk.Label(container, text=f"— {short_desc}", bg=_BG, fg=_DIM,
                     font=("Consolas", 9), anchor="w", justify="left",
                     wraplength=wrap, cursor="hand2").pack(side="left", fill="x", expand=True)

        def toggle(_event=None) -> None:
            if expanded[0]:
                detail_frame.pack_forget()
                arrow_lbl.configure(text="▶")
            else:
                detail_frame.pack(fill="x", after=container)
                arrow_lbl.configure(text="▼")
            expanded[0] = not expanded[0]

        def on_enter(_event=None) -> None:
            arrow_lbl.configure(fg=_FG)
            name_lbl.configure(fg="#00ff66")

        def on_leave(_event=None) -> None:
            arrow_lbl.configure(fg=_DIM)
            name_lbl.configure(fg=_FG)

        for w in (arrow_lbl, name_lbl, container):
            w.bind("<Button-1>", toggle)
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

    def _refresh_actions(self, snap: RoomSnapshot) -> None:
        self._clear(self._actions_inner)
        row1 = tk.Frame(self._actions_inner, bg=_BG)
        row1.pack(fill="x", pady=(0, 2))
        for caption, cmd in (("Look", "look"), ("Inventory", "inventory"), ("Help", "help")):
            _mk_btn(row1, f"[ {caption} ]", lambda c=cmd: self.run(c)).pack(side="left", padx=(0, 4))

        if snap.has_terminal or snap.has_cat or snap.has_ringing_phone:
            row2 = tk.Frame(self._actions_inner, bg=_BG)
            row2.pack(fill="x")
            if snap.has_ringing_phone:
                _mk_btn(row2, "[ Answer Phone ]",
                        lambda: self.run("answer phone")).pack(side="left", padx=(0, 4))
            if snap.has_terminal:
                _mk_btn(row2, "[ Use Computer ]",
                        self._open_computer).pack(side="left", padx=(0, 4))
            if snap.has_cat:
                _mk_btn(row2, "[ Pet ]",
                        lambda: self.run("pet cat")).pack(side="left", padx=(0, 4))

    def _show_response(self, text: str) -> None:
        self._resp_lbl.configure(text=text.strip())

    def _sync(self, snap: RoomSnapshot) -> None:
        loc = snap.room_name
        if snap.area:
            loc += f"\n{snap.area}"
        self.location.set(loc)
        inv_names = [str(obj.get("name") or obj.get("id", "?"))
                     for obj in self.session.inventory]
        self.inventory_var.set("\n".join(inv_names) if inv_names else "(empty)")
        self._clear(self.exit_frame)
        if not snap.exits:
            tk.Label(self.exit_frame, text="(none)", bg=_BG, fg=_DIM,
                     font=("Consolas", 8), anchor="w").pack(anchor="w")
        for direction in snap.exits:
            tk.Button(
                self.exit_frame, text=direction,
                bg=_BG, fg=_FG, activebackground="#001a00", activeforeground=_FG,
                relief="flat", font=("Consolas", 8), cursor="hand2",
                command=lambda d=direction: self.run(f"go {d}"),
            ).pack(fill="x", pady=1)

    @staticmethod
    def _clear(frame: tk.Frame) -> None:
        for w in frame.winfo_children():
            w.destroy()

    # ── Commands ──────────────────────────────────────────────────────────────

    def _submit(self, _event=None) -> None:
        cmd = self.command.get().strip()
        if not cmd:
            return
        self.command.set("")
        self.run(cmd)

    def run(self, command: str) -> None:
        normalized = command.strip().casefold()
        if self.session.on_phone:
            if normalized in {"hang up", "hangup"}:
                self._request_serial += 1
                self._phone_busy = False
                response = self.session.execute(command)
                self._show_response(f"> {command}\n{response}")
                self.refresh_room()
            elif self._phone_busy:
                self._show_response("The voice is still responding. You can 'hang up'.")
            else:
                speech = command[4:].strip() if normalized.startswith("say ") else command.strip()
                if speech:
                    self._show_response(f"> {speech}")
                    self._ask_phone(speech)
        else:
            response = self.session.execute(command)
            computer_request = self.session.consume_computer_request()
            self._show_response(f"> {command}\n{response}")
            if self.session.on_phone:
                self._ask_phone("Hello?")
            self.refresh_room()
            if computer_request is not None:
                self._open_computer()
                return
        self.entry.focus_set()

    def _open_computer(self) -> None:
        if self._computer_cb:
            self._computer_cb()
        else:
            self._open_computer_standalone()

    def _open_computer_standalone(self) -> None:
        from .computer import ComputerWindow
        win = self._computer_window
        if win is not None:
            try:
                if win.winfo_exists():
                    win.lift()
                    win.focus_set()
                    return
            except tk.TclError:
                pass
        try:
            self._computer_window = ComputerWindow(self.winfo_toplevel())
        except (tk.TclError, OSError, RuntimeError) as exc:
            self._show_response(f"[KleinOS unavailable] {exc}")

    # ── Phone ─────────────────────────────────────────────────────────────────

    def _ask_phone(self, speech: str) -> None:
        call_serial, model, messages = self.session.phone_payload(speech)
        self._request_serial += 1
        serial = self._request_serial
        self._phone_busy = True
        self._show_response(f"[Calling local Ollama: {model} ...]")

        def worker() -> None:
            try:
                reply = chat(model, messages)
                self._phone_results.put((serial, call_serial, speech, reply, None))
            except OllamaPhoneError as exc:
                self._phone_results.put((serial, call_serial, speech, None, str(exc)))
            except Exception as exc:
                self._phone_results.put((serial, call_serial, speech, None,
                                         f"Local Ollama error: {type(exc).__name__}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self._poll_phone)

    def _poll_phone(self) -> None:
        try:
            while True:
                serial, call_serial, speech, reply, error = self._phone_results.get_nowait()
                if serial != self._request_serial or not self.session.on_phone:
                    continue
                self._phone_busy = False
                if error:
                    self._show_response(f"[Telephone offline] {error}")
                elif self.session.finish_phone_reply(call_serial, speech, reply):
                    self._show_response(f"Voice: {reply}")
        except queue.Empty:
            pass
        if self._phone_busy and self.winfo_exists():
            self.after(100, self._poll_phone)

    def reload_world(self) -> None:
        self._request_serial += 1
        self._phone_busy = False
        try:
            self.session.restart()
        except Exception as exc:
            self._show_response(f"Cannot reload world: {exc}")
            return
        self.refresh_room()
        self._show_response("")
        self.entry.focus_set()
