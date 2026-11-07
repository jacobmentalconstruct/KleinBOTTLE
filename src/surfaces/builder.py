"""Tkinter world-builder surface. It depends on the builder use cases, not a game engine."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from typing import Callable, Optional

from ..world_builder import WorldBuilder
from ..world_model import ID_PATTERN, WorldValidationError, pretty
from ..ui_theme import FONT_UI, style_dialog, style_text


class BuilderSurface(ttk.Frame):
    def __init__(self, master: tk.Tk, builder: WorldBuilder):
        super().__init__(master, padding=12)
        self.builder = builder
        self.selected_id: str | None = None
        self._base: dict = {}
        self._saved_signature: tuple = ()
        self._refreshing = False
        self.vars = {key: tk.StringVar() for key in
                     ("id", "name", "area", "weather", "light", "sound")}
        self.world_name = tk.StringVar(value=builder.world["name"])
        self.start_room = tk.StringVar(value=builder.world["start_room"] or "")
        self.on_room_changed: Optional[Callable] = None
        self.generate_btn_callback: Optional[Callable[[str], None]] = None
        self.generate_all_callback: Optional[Callable[[], None]] = None
        self._auto_id = False
        self._pending_attach: tuple[str, str] | None = None   # (parent_id, back_direction)
        # A surface is hosted by the application shell (Notebook); do not pack it here.
        self._build()
        self.refresh_tree()
        self.new_room(ask=False)

    def _build(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="World:").pack(side="left")
        ttk.Entry(header, textvariable=self.world_name, width=30).pack(side="left", padx=6)
        ttk.Label(header, text="Start room:").pack(side="left", padx=(14, 3))
        self.start_combo = ttk.Combobox(header, textvariable=self.start_room, width=20, state="readonly")
        self.start_combo.pack(side="left", padx=4)
        ttk.Button(header, text="Save World Settings", command=self.save_settings).pack(side="left", padx=8)
        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True)
        nav = ttk.Frame(body, padding=4)

        # Scrollable right panel ──────────────────────────────────────
        right = ttk.Frame(body)
        body.add(nav, weight=1)
        body.add(right, weight=3)

        # Sticky footer — always visible below the scrollable form
        footer = ttk.Frame(right)
        footer.pack(side="bottom", fill="x", padx=4, pady=(2, 2))
        ttk.Button(footer, text="Fill All ✦", command=self._gen_all_fields).pack(side="right", padx=(4, 0))
        ttk.Button(footer, text="Save Room", style="Accent.TButton", command=self.save_room).pack(side="right")

        _canvas = tk.Canvas(right, highlightthickness=0)
        _vsb = ttk.Scrollbar(right, orient="vertical", command=_canvas.yview)
        _canvas.configure(yscrollcommand=_vsb.set)
        _vsb.pack(side="right", fill="y")
        _canvas.pack(side="left", fill="both", expand=True)

        content = ttk.Frame(_canvas, padding=6)
        _cwin  = _canvas.create_window((0, 0), window=content, anchor="nw")

        content.bind("<Configure>",
                     lambda _e: _canvas.configure(scrollregion=_canvas.bbox("all")))
        _canvas.bind("<Configure>",
                     lambda e: _canvas.itemconfigure(_cwin, width=e.width))
        _canvas.bind("<MouseWheel>",
                     lambda e: _canvas.yview_scroll(int(-e.delta / 120), "units"))
        content.bind("<MouseWheel>",
                     lambda e: _canvas.yview_scroll(int(-e.delta / 120), "units"))
        self._editor_canvas = _canvas   # saved so child-scroll helper can reach it

        ttk.Label(nav, text="Areas / Rooms", style="Heading.TLabel").pack(anchor="w", pady=(0, 5))
        self.tree = ttk.Treeview(nav, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select_room)
        self.tree.bind("<Button-3>", self._show_tree_menu)
        self.tree.bind("<MouseWheel>", lambda e: self.tree.yview_scroll(int(-e.delta / 120), "units"))
        controls = ttk.Frame(nav)
        controls.pack(fill="x", pady=7)
        ttk.Button(controls, text="New Room", command=self.new_room).pack(side="left", padx=2)
        ttk.Button(controls, text="Delete", style="Danger.TButton", command=self.delete_room).pack(side="left", padx=2)
        ttk.Button(nav, text="Import / Paste JSON...", command=self.import_dialog).pack(fill="x", pady=3)
        ttk.Button(nav, text="Export World JSON...", command=self.export_world).pack(fill="x", pady=3)

        ttk.Label(content, text="Room Editor", style="Heading.TLabel").pack(anchor="w", pady=(0, 9))
        top = ttk.Frame(content)
        top.pack(fill="x", pady=2)
        for index, (key, label, size) in enumerate((("id", "Room ID", 19), ("name", "Name", 32), ("area", "Area", 24))):
            part = ttk.Frame(top)
            part.pack(side="left", padx=(0, 12))
            ttk.Label(part, text=label).pack(anchor="w")
            entry = ttk.Entry(part, textvariable=self.vars[key], width=size)
            entry.pack(anchor="w")
            if key == "id":
                self.id_entry = entry
                entry.bind("<Key>", lambda _e: setattr(self, "_auto_id", False))
            if key == "name":
                self.vars["name"].trace_add("write", self._on_name_changed)
                ttk.Button(part, text="✦", width=3,
                           command=lambda: self._gen_field("name")).pack(anchor="w", pady=(2, 0))
        desc_hdr = ttk.Frame(content)
        desc_hdr.pack(fill="x", pady=(7, 2))
        ttk.Label(desc_hdr, text="Description").pack(side="left")
        ttk.Button(desc_hdr, text="✦", width=3,
                   command=lambda: self._gen_field("description")).pack(side="left", padx=4)
        self.description = tk.Text(content, height=4, wrap="word", undo=True)
        style_text(self.description, font=FONT_UI)
        self.description.pack(fill="x")
        self.description.bind("<MouseWheel>", lambda e: self.description.yview_scroll(int(-e.delta / 120), "units"))
        ttk.Label(content, text="Exits — one per line: direction:room_id").pack(anchor="w", pady=(9, 2))
        self.exits = tk.Text(content, height=4, wrap="none", undo=True)
        style_text(self.exits)
        self.exits.pack(fill="x")
        self.exits.bind("<MouseWheel>", lambda e: self.exits.yview_scroll(int(-e.delta / 120), "units"))

        environment = ttk.LabelFrame(content, text="Environment — optional text values")
        environment.pack(fill="x", pady=(9, 2))
        for key, title in (("weather", "Weather"), ("light", "Light"), ("sound", "Sound")):
            part = ttk.Frame(environment)
            part.pack(side="left", padx=6, pady=5)
            ttk.Label(part, text=title).pack(anchor="w")
            ttk.Entry(part, textvariable=self.vars[key], width=22).pack()
            ttk.Button(part, text="✦", width=3,
                       command=lambda k=key: self._gen_field(k)).pack(anchor="w", pady=(2, 0))

        obj_hdr = ttk.Frame(content)
        obj_hdr.pack(fill="x", pady=(8, 2))
        ttk.Label(obj_hdr, text="Objects — JSON array (or use Add Object)").pack(side="left")
        ttk.Button(obj_hdr, text="✦", width=3,
                   command=lambda: self._gen_field("objects")).pack(side="left", padx=4)
        self.objects = tk.Text(content, height=7, wrap="none", undo=True)
        style_text(self.objects)
        self.objects.pack(fill="both", expand=True)
        self.objects.bind("<MouseWheel>", lambda e: self.objects.yview_scroll(int(-e.delta / 120), "units"))
        row = ttk.Frame(content)
        row.pack(fill="x", pady=(8, 3))
        ttk.Button(row, text="Add Object...", command=self.add_object).pack(side="left")
        ttk.Button(row, text="Edit Object...", command=self.edit_object).pack(side="left", padx=8)
        ttk.Button(row, text="Full Room JSON...", command=self.edit_room_json).pack(side="left", padx=8)
        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, anchor="w", style="Status.TLabel").pack(fill="x", pady=(8, 0))

        # Propagate scroll from frames/labels inside content to the canvas
        self._wire_scroll(content)

    def _form_signature(self) -> tuple:
        return (tuple(self.vars[k].get() for k in ("id", "name", "area", "weather", "light", "sound")),
                self.description.get("1.0", "end-1c"), self.exits.get("1.0", "end-1c"),
                self.objects.get("1.0", "end-1c"))

    def _guard_unsaved(self) -> bool:
        if self._form_signature() == self._saved_signature:
            return True
        return messagebox.askyesno("Unsaved room edits", "Discard unsaved edits to this room?", parent=self)

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.edit_modified(False)

    def _populate(self, room: dict, existing: bool) -> None:
        self._base = deepcopy(room)
        for key in ("id", "name", "area"):
            self.vars[key].set(room.get(key, ""))
        if existing:
            self.id_entry.configure(state="readonly")
            self._auto_id = False
        else:
            self.id_entry.configure(state="disabled")
            self._auto_id = True
        self._set_text(self.description, room.get("description", ""))
        self._set_text(self.exits, "\n".join(f"{key}:{value}" for key, value in room.get("exits", {}).items()))
        env = room.get("environment", {})
        for key in ("weather", "light", "sound"):
            self.vars[key].set(str(env.get(key, "")))
        self._set_text(self.objects, pretty(room.get("objects", [])).rstrip("\n"))
        self._saved_signature = self._form_signature()

    def refresh_tree(self, focus: str | None = None) -> None:
        self._refreshing = True
        self.tree.delete(*self.tree.get_children())
        rooms = sorted(self.builder.rooms(), key=lambda r: (r["area"].lower(), r["name"].lower()))
        areas = {}
        for room in rooms:
            area = room["area"]
            if area not in areas:
                areas[area] = self.tree.insert("", "end", text=area, open=True)
            node = self.tree.insert(areas[area], "end", iid=f"room:{room['id']}", text=room["name"])
            if room["id"] == focus:
                self.tree.selection_set(node)
                self.tree.see(node)
        self.start_combo["values"] = [""] + [room["id"] for room in rooms]
        self.start_room.set(self.builder.world["start_room"] or "")
        self.world_name.set(self.builder.world["name"])
        warnings = self.builder.warnings()
        self.status.set(f"{len(rooms)} rooms. {len(warnings)} unresolved exit reference(s).")
        self._refreshing = False

    def _select_room(self, _event=None) -> None:
        if self._refreshing:
            return
        selection = self.tree.selection()
        if not selection or not selection[0].startswith("room:"):
            return
        new_id = selection[0].removeprefix("room:")
        if new_id == self.selected_id:
            return
        if not self._guard_unsaved():
            self._refreshing = True
            if self.selected_id is not None and self.tree.exists(f"room:{self.selected_id}"):
                self.tree.selection_set(f"room:{self.selected_id}")
            else:
                self.tree.selection_remove(*self.tree.selection())
            self._refreshing = False
            return
        self.selected_id = new_id
        self._pending_attach = None
        self._populate(self.builder.room(new_id), existing=True)
        if self.on_room_changed:
            self.on_room_changed()

    def new_room(self, ask: bool = True) -> None:
        if ask and not self._guard_unsaved():
            return
        self._pending_attach = None
        self.selected_id = None
        self._refreshing = True
        self.tree.selection_remove(*self.tree.selection())
        self._refreshing = False
        self._populate({"id": "", "name": "", "area": "Ungrouped", "description": "",
                        "exits": {}, "environment": {}, "objects": []}, existing=False)
        self.vars["name"].set("")
        self._saved_signature = self._form_signature()
        self.id_entry.focus_set()

    def _read_form(self) -> dict:
        room = deepcopy(self._base)
        for key in ("id", "name", "area"):
            room[key] = self.vars[key].get().strip()
        room["description"] = self.description.get("1.0", "end-1c")
        exits = {}
        for number, line in enumerate(self.exits.get("1.0", "end-1c").splitlines(), 1):
            if not line.strip():
                continue
            if ":" not in line:
                raise WorldValidationError(f"Exit line {number} needs direction:room_id")
            direction, target = (part.strip() for part in line.split(":", 1))
            if not direction or not target or direction in exits:
                raise WorldValidationError(f"Invalid or duplicate direction on exit line {number}")
            exits[direction] = target
        room["exits"] = exits
        env = deepcopy(room.get("environment", {}))
        for key in ("weather", "light", "sound"):
            value = self.vars[key].get().strip()
            if value:
                env[key] = value
            else:
                env.pop(key, None)
        room["environment"] = env
        try:
            room["objects"] = json.loads(self.objects.get("1.0", "end-1c") or "[]")
        except json.JSONDecodeError as exc:
            raise WorldValidationError(f"Objects JSON: {exc}") from exc
        return room

    def save_room(self) -> None:
        try:
            room = self._read_form()
            self.builder.save_room(room, original_id=self.selected_id)
        except (WorldValidationError, OSError) as exc:
            messagebox.showerror("Cannot save room", str(exc), parent=self)
            return
        new_id = room["id"]
        self.selected_id = new_id
        # Auto-wire the forward exit on the parent when saving an attached room.
        attach_note = ""
        if self._pending_attach is not None:
            parent_id, back_dir = self._pending_attach
            self._pending_attach = None
            fwd_dir = self._OPPOSITE.get(back_dir)
            if fwd_dir:
                try:
                    parent = self.builder.room(parent_id)
                    if fwd_dir not in parent.get("exits", {}):
                        parent.setdefault("exits", {})[fwd_dir] = new_id
                        self.builder.save_room(parent, original_id=parent_id)
                        attach_note = f"; added '{fwd_dir}' exit to '{parent_id}'"
                except (WorldValidationError, OSError):
                    pass  # non-fatal — the new room is already saved
        self.refresh_tree(focus=self.selected_id)
        self._populate(self.builder.room(self.selected_id), existing=True)
        self.status.set(f"Saved room '{self.selected_id}'{attach_note}")

    def delete_room(self) -> None:
        if self.selected_id is None or not self._guard_unsaved():
            return
        if not messagebox.askyesno("Delete room", f"Delete '{self.selected_id}'?", parent=self):
            return
        try:
            self.builder.delete_room(self.selected_id)
        except (WorldValidationError, OSError) as exc:
            messagebox.showerror("Cannot delete room", str(exc), parent=self)
            return
        self.selected_id = None
        self.refresh_tree()
        self.new_room(ask=False)

    def save_settings(self) -> None:
        try:
            self.builder.settings(self.world_name.get().strip(), self.start_room.get() or None)
        except (WorldValidationError, OSError) as exc:
            messagebox.showerror("Cannot save settings", str(exc), parent=self)
            return
        self.status.set("World settings saved")

    def _object_list(self) -> list[dict]:
        try:
            objects = json.loads(self.objects.get("1.0", "end-1c") or "[]")
        except json.JSONDecodeError as exc:
            raise WorldValidationError(f"Objects JSON: {exc}") from exc
        if not isinstance(objects, list) or not all(isinstance(item, dict) for item in objects):
            raise WorldValidationError("Objects must be a JSON array of objects")
        return objects

    def add_object(self) -> None:
        try:
            objects = self._object_list()
        except WorldValidationError as exc:
            messagebox.showerror("Objects JSON", str(exc), parent=self)
            return
        self._object_dialog(objects, None)

    def edit_object(self) -> None:
        try:
            objects = self._object_list()
        except WorldValidationError as exc:
            messagebox.showerror("Objects JSON", str(exc), parent=self)
            return
        if not objects:
            messagebox.showinfo("Edit Object", "Add an object first.", parent=self)
            return
        window = tk.Toplevel(self)
        style_dialog(window)
        window.title("Select Object")
        window.transient(self.winfo_toplevel())
        window.resizable(False, False)
        choices = [f"{obj.get('name', '(unnamed)')} [{obj.get('id', i)}]"
                   for i, obj in enumerate(objects)]
        choice = ttk.Combobox(window, state="readonly", values=choices, width=48)
        choice.current(0)
        ttk.Label(window, text="Choose an object to edit:").pack(anchor="w", padx=12, pady=(10, 5))
        choice.pack(fill="x", padx=12)
        def open_selected() -> None:
            index = choice.current()
            window.destroy()
            if index >= 0:
                self._object_dialog(objects, index)
        ttk.Button(window, text="Edit", style="Accent.TButton", command=open_selected).pack(anchor="e", padx=12, pady=12)

    def _object_dialog(self, objects: list[dict], index: int | None) -> None:
        """Create or edit an object in the current room form; Save Room persists it."""
        existing = objects[index] if index is not None else {}
        window = tk.Toplevel(self)
        style_dialog(window)
        window.title("Edit Object" if index is not None else "Add Object")
        window.geometry("640x560")
        window.transient(self.winfo_toplevel())
        window.grab_set()
        fields: dict[str, tk.StringVar] = {}
        for row, (key, label, default) in enumerate((
            ("id", "Object ID", ""), ("name", "Name", ""),
            ("kind", "Kind (use telephone for the phone)", "item"),
            ("description", "Description", ""),
        )):
            ttk.Label(window, text=label).grid(row=row, column=0, padx=12, pady=7, sticky="e")
            fields[key] = tk.StringVar(value=str(existing.get(key, default)))
            entry = ttk.Entry(window, textvariable=fields[key], width=49)
            entry.grid(row=row, column=1, padx=12, pady=7, sticky="ew")
            if key == "id" and index is not None:
                entry.configure(state="readonly")
        phone = existing.get("ollama") if isinstance(existing.get("ollama"), dict) else {}
        ttk.Separator(window, orient="horizontal").grid(row=4, columnspan=2, sticky="ew", padx=12, pady=(12, 6))
        ttk.Label(window, text="Telephone / local Ollama (only used when kind = telephone)").grid(
            row=5, columnspan=2, sticky="w", padx=12)
        model = tk.StringVar(value=str(phone.get("model", "qwen2.5:3b")))
        ttk.Label(window, text="Model").grid(row=6, column=0, sticky="e", padx=12, pady=7)
        ttk.Entry(window, textvariable=model, width=49).grid(row=6, column=1, padx=12, sticky="ew")
        ttk.Label(window, text="System prompt").grid(row=7, column=0, sticky="ne", padx=12, pady=7)
        system = tk.Text(window, height=7, width=48, wrap="word", undo=True)
        style_text(system, font=FONT_UI)
        system.grid(row=7, column=1, padx=12, pady=7, sticky="nsew")
        system.insert("1.0", str(phone.get("system", "")))
        ringing = tk.BooleanVar(value=existing.get("ringing", True) is True)
        ttk.Checkbutton(window, text="Ringing when the world starts", variable=ringing).grid(
            row=8, column=1, sticky="w", padx=12, pady=6)
        ttk.Label(window, text="Requests always use 127.0.0.1:11434; no cloud endpoint.",
                  style="Muted.TLabel").grid(row=9, columnspan=2, sticky="w", padx=12)
        window.grid_columnconfigure(1, weight=1)
        window.grid_rowconfigure(7, weight=1)

        def save() -> None:
            obj = deepcopy(existing)
            for key, var in fields.items():
                obj[key] = var.get().strip()
            if not ID_PATTERN.fullmatch(obj["id"]) or not obj["name"]:
                messagebox.showerror("Cannot save object", "Object ID and name are required; IDs cannot contain spaces", parent=window)
                return
            if any(i != index and other.get("id") == obj["id"] for i, other in enumerate(objects)):
                messagebox.showerror("Cannot save object", "Object ID already exists in this room", parent=window)
                return
            if obj["kind"].casefold() == "telephone":
                obj["ollama"] = {"model": model.get().strip() or "qwen2.5:3b",
                                  "system": system.get("1.0", "end-1c")}
                obj["ringing"] = ringing.get()
                obj["portable"] = False
            # Leave non-telephone extra properties unchanged on edit.
            if index is None:
                objects.append(obj)
            else:
                objects[index] = obj
            self._set_text(self.objects, pretty(objects).rstrip("\n"))
            self.status.set("Object updated in form. Click Save Room to persist it.")
            window.destroy()

        ttk.Button(window, text="Apply to Room", style="Accent.TButton", command=save).grid(
            row=10, column=1, sticky="e", padx=12, pady=12)
        window.bind("<Escape>", lambda _event: window.destroy())

    def edit_room_json(self) -> None:
        if self.selected_id is None:
            messagebox.showinfo("Select a room", "Save the new room before editing its full JSON.", parent=self)
            return
        if not self._guard_unsaved():
            return
        window = tk.Toplevel(self)
        style_dialog(window)
        window.title(f"Room JSON — {self.selected_id}")
        window.geometry("750x610")
        window.transient(self.winfo_toplevel())
        editor = tk.Text(window, wrap="none", undo=True)
        style_text(editor)
        editor.pack(fill="both", expand=True, padx=10, pady=10)
        self._set_text(editor, pretty(self.builder.room(self.selected_id)))

        def apply() -> None:
            try:
                raw = json.loads(editor.get("1.0", "end-1c"))
                self.builder.save_room(raw, original_id=self.selected_id)
            except (ValueError, WorldValidationError, OSError) as exc:
                messagebox.showerror("Cannot apply JSON", str(exc), parent=window)
                return
            room_id = self.selected_id
            self.refresh_tree(focus=room_id)
            self._populate(self.builder.room(room_id), existing=True)
            window.destroy()
        ttk.Button(window, text="Apply JSON", style="Accent.TButton", command=apply).pack(anchor="e", padx=10, pady=(0, 10))

    def import_dialog(self) -> None:
        if not self._guard_unsaved():
            return
        window = tk.Toplevel(self)
        style_dialog(window)
        window.title("Import / Paste Rooms or World JSON")
        window.geometry("830x610")
        window.transient(self.winfo_toplevel())
        ttk.Label(window, text="Paste a room object, list of rooms, or a {rooms: [...]} world document.").pack(anchor="w", padx=10, pady=5)
        editor = tk.Text(window, wrap="none", undo=True)
        style_text(editor)
        editor.pack(fill="both", expand=True, padx=10, pady=5)
        mode = tk.StringVar(value="add")
        options = ttk.Frame(window)
        options.pack(fill="x", padx=10, pady=5)
        for value, label in (("add", "Add new (skip existing IDs)"),
                             ("update", "Update matching IDs"), ("replace", "Replace whole world")):
            ttk.Radiobutton(options, text=label, variable=mode, value=value).pack(side="left", padx=6)

        def load_file() -> None:
            path = filedialog.askopenfilename(parent=window, filetypes=[("JSON", "*.json"), ("All files", "*.*")])
            if path:
                try:
                    self._set_text(editor, Path(path).read_text(encoding="utf-8"))
                except OSError as exc:
                    messagebox.showerror("Cannot load file", str(exc), parent=window)

        def apply() -> None:
            if mode.get() == "replace" and not messagebox.askyesno(
                "Replace whole world", "All existing rooms will be replaced. Continue?", parent=window
            ):
                return
            try:
                changed, skipped = self.builder.import_json(editor.get("1.0", "end-1c"), mode=mode.get())
            except (ValueError, WorldValidationError, OSError) as exc:
                messagebox.showerror("Import failed", str(exc), parent=window)
                return
            self.selected_id = None
            self.refresh_tree()
            self.new_room(ask=False)
            messagebox.showinfo("Import complete", f"Imported or updated: {changed}\nSkipped: {skipped}\n"
                                f"Unresolved exits: {len(self.builder.warnings())}", parent=self)
            window.destroy()
        actions = ttk.Frame(window)
        actions.pack(fill="x", padx=10, pady=10)
        ttk.Button(actions, text="Load JSON File...", command=load_file).pack(side="left")
        ttk.Button(actions, text="Import", style="Accent.TButton", command=apply).pack(side="right")

    # ── Task 4: AI assistant hooks ────────────────────────────────────

    def get_form_snapshot(self) -> dict:
        """Return current form values (may be unsaved)."""
        return {
            "id":          self.vars["id"].get(),
            "name":        self.vars["name"].get(),
            "area":        self.vars["area"].get(),
            "description": self.description.get("1.0", "end-1c"),
            "exits":       self.exits.get("1.0", "end-1c"),
            "environment": {
                "weather": self.vars["weather"].get(),
                "light":   self.vars["light"].get(),
                "sound":   self.vars["sound"].get(),
            },
            "objects": self.objects.get("1.0", "end-1c"),
        }

    def apply_ai_updates(self, updates: dict) -> None:
        """Apply a partial update dict from the AI assistant to the live form."""
        allowed = {"name", "description", "environment", "objects"}
        changed = False
        for key, value in updates.items():
            if key not in allowed:
                continue
            if key == "name":
                self.vars["name"].set(str(value))
                changed = True
            elif key == "description":
                self._set_text(self.description, str(value))
                changed = True
            elif key == "environment" and isinstance(value, dict):
                for sub in ("weather", "light", "sound"):
                    if sub in value:
                        self.vars[sub].set(str(value[sub]))
                        changed = True
            elif key == "objects" and isinstance(value, list):
                self._set_text(self.objects, pretty(value).rstrip("\n"))
                changed = True
        if changed:
            self.status.set("AI updated form. Click Save Room to persist.")

    def area_rooms(self) -> list:
        """Return all rooms in the same area as the currently selected room."""
        area = self.vars["area"].get()
        return [r for r in self.builder.rooms() if r.get("area") == area]

    def all_rooms(self) -> list:
        """Return all rooms in the world."""
        return self.builder.rooms()

    # ── Tree context menu ─────────────────────────────────────────────

    _DIRECTIONS = [
        "north", "south", "east", "west",
        "up", "down", "in", "out",
        "northeast", "northwest", "southeast", "southwest",
    ]
    _OPPOSITE = {
        "north": "south",     "south": "north",
        "east":  "west",      "west":  "east",
        "up":    "down",      "down":  "up",
        "in":    "out",       "out":   "in",
        "northeast": "southwest", "southwest": "northeast",
        "northwest": "southeast", "southeast": "northwest",
    }

    def _show_tree_menu(self, event: tk.Event) -> None:
        item = self.tree.identify_row(event.y)
        if not item or not item.startswith("room:"):
            return
        room_id = item.removeprefix("room:")
        try:
            room = self.builder.room(room_id)
        except Exception:
            return
        name = room.get("name", room_id)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label=f"Add room off \"{name}\"",
            command=lambda: self._pick_exit_direction(room_id, room),
        )
        menu.add_separator()
        menu.add_command(label="Delete room", command=self.delete_room)
        menu.tk_popup(event.x_root, event.y_root)

    def _pick_exit_direction(self, parent_id: str, parent_room: dict) -> None:
        """Show a direction picker dialog, then blank the form for a new connected room."""
        taken     = set(parent_room.get("exits", {}).keys())
        available = [d for d in self._DIRECTIONS if d not in taken]
        name      = parent_room.get("name", parent_id)

        window = tk.Toplevel(self)
        from src.ui_theme import style_dialog  # noqa: PLC0415
        style_dialog(window)
        window.title(f"Add room off: {name}")
        window.resizable(False, False)
        window.transient(self.winfo_toplevel())
        window.grab_set()

        ttk.Label(window, text=f"Exit direction from new room back to \"{name}\":").pack(
            anchor="w", padx=12, pady=(12, 4))

        if taken:
            ttk.Label(window, text=f"Already used: {', '.join(sorted(taken))}",
                      style="Muted.TLabel").pack(anchor="w", padx=12, pady=(0, 6))

        chosen = tk.StringVar(value=available[0] if available else "")

        grid = ttk.Frame(window)
        grid.pack(padx=12, pady=4)
        for i, d in enumerate(available):
            ttk.Radiobutton(grid, text=d, variable=chosen,
                            value=d).grid(row=i // 4, column=i % 4,
                                          sticky="w", padx=8, pady=2)

        ttk.Separator(window, orient="horizontal").pack(fill="x", padx=12, pady=(10, 4))
        ttk.Label(window, text="Custom direction:").pack(anchor="w", padx=12)
        custom_var = tk.StringVar()
        custom_entry = ttk.Entry(window, textvariable=custom_var, width=24)
        custom_entry.pack(anchor="w", padx=12, pady=(2, 8))

        def _apply() -> None:
            direction = custom_var.get().strip() or chosen.get().strip()
            if not direction:
                return
            window.destroy()
            self._add_room_off(parent_id, parent_room, direction)

        ttk.Button(window, text="Create Room", style="Accent.TButton",
                   command=_apply).pack(anchor="e", padx=12, pady=(0, 12))
        window.bind("<Return>", lambda _: _apply())
        window.bind("<Escape>", lambda _: window.destroy())

    def _add_room_off(self, parent_id: str, parent_room: dict, direction: str) -> None:
        """Blank the form for a new room pre-wired back to parent_id via direction."""
        if not self._guard_unsaved():
            return
        self._pending_attach = (parent_id, direction)
        self.selected_id = None
        self._refreshing = True
        self.tree.selection_remove(*self.tree.selection())
        self._refreshing = False
        area = parent_room.get("area", "Ungrouped")
        self._populate({
            "id": "", "name": "", "area": area, "description": "",
            "exits": {}, "environment": {}, "objects": [],
        }, existing=False)
        self._set_text(self.exits, f"{direction}:{parent_id}")
        self._saved_signature = self._form_signature()
        parent_name = parent_room.get("name", parent_id)
        self.status.set(
            f"New room — type an ID above; exit '{direction}' leads back to '{parent_name}'"
        )
        self.id_entry.focus_set()
        if self.on_room_changed:
            self.on_room_changed()

    # ── Scroll propagation ────────────────────────────────────────────

    def _wire_scroll(self, widget: tk.Widget) -> None:
        """Recursively bind MouseWheel on non-Text widgets to scroll the editor canvas."""
        if not isinstance(widget, tk.Text):
            widget.bind("<MouseWheel>",
                        lambda e: self._editor_canvas.yview_scroll(
                            int(-e.delta / 120), "units"))
        for child in widget.winfo_children():
            self._wire_scroll(child)

    # ── Auto-derive room ID from name ─────────────────────────────────

    def _derive_id(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
        if not slug:
            return ""
        existing = {r["id"] for r in self.builder.rooms()}
        n = 1
        while True:
            candidate = f"{slug}-{n:02d}"
            if candidate not in existing:
                return candidate
            n += 1

    def _on_name_changed(self, *_) -> None:
        if not self._auto_id:
            return
        name = self.vars["name"].get()
        derived = self._derive_id(name)
        self.vars["id"].set(derived)
        self.id_entry.configure(state="normal" if derived else "disabled")

    # ── AI field-generation hooks ─────────────────────────────────────

    def _gen_field(self, field_name: str) -> None:
        if self.generate_btn_callback:
            self.generate_btn_callback(field_name)

    def _gen_all_fields(self) -> None:
        if self.generate_all_callback:
            self.generate_all_callback()

    def export_world(self) -> None:
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json", filetypes=[("JSON", "*.json")],
                                            initialfile="world-export.json")
        if path:
            try:
                Path(path).write_text(self.builder.export_json(), encoding="utf-8")
                self.status.set(f"Exported {path}")
            except OSError as exc:
                messagebox.showerror("Export failed", str(exc), parent=self)
