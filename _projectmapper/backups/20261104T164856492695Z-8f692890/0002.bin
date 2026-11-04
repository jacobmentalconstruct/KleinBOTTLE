"""Tkinter play surface: transcript + commands over the standalone game session."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..game import GameSession
from ..world_model import WorldValidationError
from ..ui_theme import ACCENT, FONT_HEADING, FONT_STORY, style_text


class GameSurface(ttk.Frame):
    def __init__(self, master: tk.Misc, session: GameSession):
        super().__init__(master, padding=12)
        self.session = session
        self.command = tk.StringVar()
        self.location = tk.StringVar()
        self.inventory = tk.StringVar()
        self._build()
        self._render_initial()

    def _build(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Play", style="Heading.TLabel").pack(side="left")
        ttk.Button(top, text="Reload World / Restart", command=self.reload_world).pack(side="right")
        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True)
        main = ttk.Frame(body)
        sidebar = ttk.Frame(body, padding=(10, 0, 0, 0))
        body.add(main, weight=4)
        body.add(sidebar, weight=1)

        story = ttk.Frame(main)
        story.pack(fill="both", expand=True)
        self.transcript = tk.Text(story, wrap="word", state="disabled",
                                  padx=10, pady=10, spacing3=6)
        style_text(self.transcript, font=FONT_STORY)
        self.transcript.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(story, orient="vertical", command=self.transcript.yview)
        scrollbar.pack(side="right", fill="y")
        self.transcript.configure(yscrollcommand=scrollbar.set)
        self.transcript.tag_configure("command", foreground=ACCENT, spacing1=10)
        self.transcript.tag_configure("title", font=FONT_HEADING)
        cmd_row = ttk.Frame(main)
        cmd_row.pack(fill="x", pady=(10, 0))
        ttk.Label(cmd_row, text="Command:").pack(side="left", padx=(0, 5))
        self.entry = ttk.Entry(cmd_row, textvariable=self.command)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self._submit)
        ttk.Button(cmd_row, text="Run", style="Accent.TButton", command=self._submit).pack(side="left", padx=(5, 0))
        quick = ttk.Frame(main)
        quick.pack(fill="x", pady=(8, 0))
        for caption, command in (("Look", "look"), ("Inventory", "inventory"), ("Help", "help")):
            ttk.Button(quick, text=caption, command=lambda c=command: self.run(c)).pack(side="left", padx=(0, 6))

        ttk.Label(sidebar, text="Location", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(sidebar, textvariable=self.location, wraplength=195, justify="left").pack(anchor="w", pady=(4, 16))
        ttk.Label(sidebar, text="Exits", style="Heading.TLabel").pack(anchor="w")
        self.exit_frame = ttk.Frame(sidebar)
        self.exit_frame.pack(fill="x", pady=(4, 16))
        ttk.Label(sidebar, text="Inventory", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(sidebar, textvariable=self.inventory, wraplength=195, justify="left").pack(anchor="w", pady=(4, 0))

    def _append(self, message: str, tag: str | None = None) -> None:
        self.transcript.configure(state="normal")
        self.transcript.insert("end", message.rstrip() + "\n\n", tag)
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def _sync(self) -> None:
        view = self.session.view()
        self.location.set(f"{view.room_name}\n{view.area}" if view.area else view.room_name)
        self.inventory.set("\n".join(view.inventory) if view.inventory else "(empty)")
        for child in self.exit_frame.winfo_children():
            child.destroy()
        if not view.exits:
            ttk.Label(self.exit_frame, text="(none)").pack(anchor="w")
        for direction in view.exits:
            ttk.Button(self.exit_frame, text=direction,
                       command=lambda d=direction: self.run(f"go {d}")).pack(fill="x", pady=2)

    def _render_initial(self) -> None:
        self._append(self.session.world["name"], "title")
        self._append(self.session.look())
        self._sync()

    def _submit(self, _event=None) -> None:
        command = self.command.get().strip()
        if not command:
            return
        self.command.set("")
        self.run(command)

    def run(self, command: str) -> None:
        self._append("> " + command, "command")
        self._append(self.session.execute(command))
        self._sync()
        self.entry.focus_set()

    def reload_world(self) -> None:
        try:
            first_description = self.session.restart()
        except (WorldValidationError, OSError) as exc:
            messagebox.showerror("Cannot reload world", str(exc), parent=self)
            return
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")
        self._append(self.session.world["name"], "title")
        self._append(first_description)
        self._sync()
        self.entry.focus_set()
