"""KleinOS v0.1: a miniature desktop backed by the fixed Docker sandbox.

Files, Terminal, and Editor use ComputerBackend exclusively. Shell commands
execute inside Docker, not the host. This module does not touch game/world data.

Standalone smoke launch: python -m src.surfaces.computer
"""
from __future__ import annotations

import posixpath
import queue
import shlex
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from ..computer_backend import ComputerBackend, CommandResult, WORKSPACE
from ..ui_theme import FONT_MONO, style_dialog, style_text


def workspace_path(value: str, cwd: str = WORKSPACE) -> str:
    """Normalize navigation paths; never point the UI outside /workspace.

    ComputerBackend separately verifies canonical paths inside the container,
    including symlinks. This is only the UI's lexical path boundary.
    """
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise ValueError("Invalid workspace path")
    if value == "~":
        value = WORKSPACE
    if not cwd.startswith(WORKSPACE):
        raise ValueError("Invalid working directory")
    path = posixpath.normpath(posixpath.join(cwd, value))
    if path != WORKSPACE and not path.startswith(WORKSPACE + "/"):
        raise ValueError("Path is outside /workspace")
    return path


def valid_filename(name: str) -> bool:
    """Names entered in New File/New Folder are one safe path component."""
    return (isinstance(name, str) and bool(name) and name not in {".", ".."}
            and "/" not in name and "\\" not in name and "\x00" not in name
            and len(name.encode("utf-8")) <= 255)


class ComputerWindow(tk.Toplevel):
    """Independent computer window; closing it leaves the game and volume intact.

    Only one Docker operation runs at a time. The Tk event loop never calls
    Docker directly, so an 8-second command cannot freeze the game UI.
    """

    def __init__(self, parent: tk.Misc, backend: ComputerBackend | None = None,
                 *, autostart: bool = True) -> None:
        super().__init__(parent)
        style_dialog(self)
        self.title("KleinOS — Computer 01")
        self.geometry("920x650")
        self.minsize(640, 430)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.backend = backend if backend is not None else ComputerBackend()
        self.directory = WORKSPACE
        self.cwd = WORKSPACE
        self.editor_path: str | None = None
        self.editor_dirty = False
        self._ready = False
        self._busy = False
        self._closed = False
        self._poll_job: str | None = None
        self._results: queue.Queue[tuple[str, Any, Callable[[Any], None]]] = queue.Queue()
        self._items: dict[str, dict[str, Any]] = {}
        self._controls: list[ttk.Button | ttk.Entry] = []
        self.status_var = tk.StringVar(value="Connecting to KleinOS...")
        self.path_var = tk.StringVar(value=self.directory)
        self.cwd_var = tk.StringVar(value=self.cwd)
        self.editor_name = tk.StringVar(value="No file open")
        self._make_ui()
        self._poll_job = self.after(60, self._poll)
        if autostart:
            self._submit("Starting sandbox", self.backend.start, self._started)
        else:
            self._ready = True
            self.status_var.set("KleinOS ready")
            self.refresh_files()

    def _make_ui(self) -> None:
        header = ttk.Frame(self, padding=(12, 10))
        header.pack(fill="x")
        ttk.Label(header, text="KleinOS  •  Computer 01", style="Heading.TLabel").pack(side="left")
        ttk.Label(header, text="Files  /  Terminal  /  Editor", style="Muted.TLabel").pack(side="right")

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self.files_tab = ttk.Frame(self.tabs, padding=8)
        self.terminal_tab = ttk.Frame(self.tabs, padding=8)
        self.editor_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.files_tab, text="  Files  ")
        self.tabs.add(self.terminal_tab, text="  Terminal  ")
        self.tabs.add(self.editor_tab, text="  Editor  ")
        self._make_files()
        self._make_terminal()
        self._make_editor()

        footer = ttk.Frame(self, padding=(12, 6))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var, style="Muted.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Button(footer, text="Close Computer", command=self.close).pack(side="right")
        self._set_busy(False)

    def _make_files(self) -> None:
        toolbar = ttk.Frame(self.files_tab)
        toolbar.pack(fill="x", pady=(0, 8))
        self._button(toolbar, "Up", self.go_up)
        self._button(toolbar, "Refresh", self.refresh_files)
        self._button(toolbar, "New Folder", self.new_folder)
        self._button(toolbar, "New File", self.new_file)
        ttk.Label(self.files_tab, textvariable=self.path_var, style="Muted.TLabel").pack(anchor="w", pady=(0, 6))

        area = ttk.Frame(self.files_tab)
        area.pack(fill="both", expand=True)
        self.file_tree = ttk.Treeview(area, columns=("name", "type", "size"), show="headings", selectmode="browse")
        self.file_tree.heading("name", text="Name")
        self.file_tree.heading("type", text="Type")
        self.file_tree.heading("size", text="Bytes")
        self.file_tree.column("name", width=440, minwidth=180, stretch=True)
        self.file_tree.column("type", width=120, minwidth=70, stretch=False)
        self.file_tree.column("size", width=95, minwidth=70, stretch=False, anchor="e")
        scrollbar = ttk.Scrollbar(area, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        self.file_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.file_tree.bind("<Double-1>", self._open_selected)
        ttk.Label(self.files_tab, text="Double-click a folder to enter it, or a text file to edit it.",
                  style="Muted.TLabel").pack(anchor="w", pady=(6, 0))

    def _make_terminal(self) -> None:
        ttk.Label(self.terminal_tab,
                  text="Commands run in Docker. No interactive TTY; each command has a timeout.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        output_frame = ttk.Frame(self.terminal_tab)
        output_frame.pack(fill="both", expand=True)
        self.output = tk.Text(output_frame, wrap="word", state="disabled", height=16,
                              font=FONT_MONO)
        style_text(self.output)
        self.output.configure(state="disabled")
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.output.yview)
        self.output.configure(yscrollcommand=scrollbar.set)
        self.output.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        ttk.Label(self.terminal_tab, textvariable=self.cwd_var,
                  style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
        command_bar = ttk.Frame(self.terminal_tab)
        command_bar.pack(fill="x", pady=(4, 2))
        ttk.Label(command_bar, text="$ ").pack(side="left")
        self.command_entry = ttk.Entry(command_bar)
        self.command_entry.pack(side="left", fill="x", expand=True)
        self.command_entry.bind("<Return>", self.run_command)
        self._controls.append(self.command_entry)
        self._button(command_bar, "Run", self.run_command)
        self._append_output("KleinOS shell: type 'help' for a few examples.\n")

    def _make_editor(self) -> None:
        toolbar = ttk.Frame(self.editor_tab)
        toolbar.pack(fill="x", pady=(0, 6))
        ttk.Label(toolbar, textvariable=self.editor_name).pack(side="left", fill="x", expand=True)
        self._button(toolbar, "Save", self.save_file)
        editor_frame = ttk.Frame(self.editor_tab)
        editor_frame.pack(fill="both", expand=True)
        self.editor = tk.Text(editor_frame, undo=True, wrap="none", font=FONT_MONO)
        style_text(self.editor)
        scrollbar = ttk.Scrollbar(editor_frame, orient="vertical", command=self.editor.yview)
        self.editor.configure(yscrollcommand=scrollbar.set)
        self.editor.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.editor.bind("<<Modified>>", self._editor_changed)
        ttk.Label(self.editor_tab, text="UTF-8 text files, up to 256 KiB. Save writes only to /workspace.",
                  style="Muted.TLabel").pack(anchor="w", pady=(6, 0))

    def _button(self, parent: ttk.Frame, label: str, callback: Callable[..., Any]) -> ttk.Button:
        button = ttk.Button(parent, text=label, command=callback)
        button.pack(side="left", padx=(0, 6))
        self._controls.append(button)
        return button

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for widget in self._controls:
            widget.configure(state="disabled" if busy or not self._ready else "normal")

    def _submit(self, description: str, work: Callable[[], Any], on_success: Callable[[Any], None]) -> None:
        if self._busy or self._closed:
            return
        self._set_busy(True)
        self.status_var.set(description + "...")

        def worker() -> None:
            try:
                result = ("ok", work(), on_success)
            except Exception as exc:
                result = ("error", str(exc), on_success)
            self._results.put(result)

        threading.Thread(target=worker, daemon=True, name="KleinOS-Docker").start()

    def _poll(self) -> None:
        if self._closed:
            return
        try:
            while True:
                kind, result, callback = self._results.get_nowait()
                self._set_busy(False)
                if kind == "error":
                    self.status_var.set("KleinOS error: " + str(result))
                    self._append_output("\n[Error] " + str(result) + "\n")
                else:
                    try:
                        callback(result)
                    except (ValueError, OSError, KeyError, TypeError, tk.TclError) as exc:
                        self.status_var.set("KleinOS UI error: " + str(exc))
        except queue.Empty:
            pass
        self._poll_job = self.after(60, self._poll)

    def _started(self, _result: Any) -> None:
        self._ready = True
        self.status_var.set("Sandbox connected. Files persist between sessions.")
        self.refresh_files()

    def _append_output(self, value: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", value)
        self.output.see("end")
        self.output.configure(state="disabled")

    def refresh_files(self) -> None:
        if not self._ready or self._busy:
            return
        folder = self.directory
        self._submit("Reading " + folder,
                     lambda: self.backend.list_files(folder),
                     lambda entries: self._show_files(folder, entries))

    def _show_files(self, folder: str, entries: list[dict[str, Any]]) -> None:
        self.directory = folder
        self.path_var.set(folder)
        self._items.clear()
        self.file_tree.delete(*self.file_tree.get_children())
        for index, entry in enumerate(entries):
            key = f"entry-{index}"
            self._items[key] = entry
            is_dir = bool(entry.get("is_dir"))
            self.file_tree.insert("", "end", iid=key, values=(
                entry.get("name", "?"), "Folder" if is_dir else "File",
                "" if is_dir else entry.get("size", ""),
            ))
        self.status_var.set(f"{len(entries)} item(s) in {folder}")

    def go_up(self) -> None:
        if self._busy or self.directory == WORKSPACE:
            return
        self.directory = workspace_path("..", self.directory)
        self.refresh_files()

    def _open_selected(self, _event: tk.Event | None = None) -> None:
        if self._busy:
            return
        selected = self.file_tree.selection()
        if not selected:
            return
        entry = self._items.get(selected[0])
        if not entry:
            return
        path = workspace_path(str(entry["path"]))
        if entry.get("is_dir"):
            self.directory = path
            self.refresh_files()
        else:
            self.open_file(path)

    def _check_editor_replace(self) -> bool:
        if self.editor_dirty:
            messagebox.showinfo("Unsaved changes",
                                "Save the current file before opening another.", parent=self)
            return False
        return True

    def new_folder(self) -> None:
        if self._busy:
            return
        name = simpledialog.askstring("New Folder", "Folder name:", parent=self)
        if name is None:
            return
        if not valid_filename(name):
            messagebox.showerror("Invalid name", "Enter a single folder name.", parent=self)
            return
        folder = self.directory
        def make() -> None:
            result = self.backend.execute("mkdir -- " + shlex.quote(name), cwd=folder)
            if result.exit_code:
                raise RuntimeError(result.stderr.strip() or "Cannot create folder")
        self._submit("Creating folder", make, lambda _: self.refresh_files())

    def new_file(self) -> None:
        if self._busy or not self._check_editor_replace():
            return
        name = simpledialog.askstring("New File", "File name:", parent=self)
        if name is None:
            return
        if not valid_filename(name):
            messagebox.showerror("Invalid name", "Enter a single file name.", parent=self)
            return
        if any(item.get("name") == name for item in self._items.values()):
            messagebox.showerror("File already exists", "Open the existing file instead.", parent=self)
            return
        self._load_editor(workspace_path(name, self.directory), "", dirty=True)

    def open_file(self, path: str) -> None:
        if self._busy or not self._check_editor_replace():
            return
        path = workspace_path(path)
        self._submit("Opening " + path,
                     lambda: self.backend.read_file(path),
                     lambda content: self._load_editor(path, content, dirty=False))

    def _load_editor(self, path: str, content: str, *, dirty: bool) -> None:
        self.editor_path = path
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", content)
        self.editor.edit_modified(False)
        self.editor_dirty = dirty
        self._update_editor_title()
        self.tabs.select(self.editor_tab)
        self.status_var.set("Editing " + path)

    def _editor_changed(self, _event: tk.Event | None = None) -> None:
        if self.editor.edit_modified():
            self.editor_dirty = True
            self._update_editor_title()
            self.editor.edit_modified(False)

    def _update_editor_title(self) -> None:
        self.editor_name.set((self.editor_path or "No file open") + ("  *" if self.editor_dirty else ""))

    def save_file(self) -> None:
        if self._busy or not self.editor_path:
            self.status_var.set("Create or open a file first")
            return
        path = self.editor_path
        content = self.editor.get("1.0", "end-1c")
        self._submit("Saving " + path,
                     lambda: self.backend.write_file(path, content),
                     lambda _: self._saved(path, content))

    def _saved(self, path: str, saved_content: str) -> None:
        if self.editor_path == path and self.editor.get("1.0", "end-1c") == saved_content:
            self.editor_dirty = False
            self._update_editor_title()
        self.status_var.set("Saved " + path)
        self.refresh_files()

    def run_command(self, _event: tk.Event | None = None) -> None:
        if self._busy or not self._ready:
            return
        command = self.command_entry.get().strip()
        if not command:
            return
        self.command_entry.delete(0, "end")
        self._append_output(f"\n{self.cwd} $ {command}\n")
        self.tabs.select(self.terminal_tab)
        if command == "clear":
            self.output.configure(state="normal")
            self.output.delete("1.0", "end")
            self.output.configure(state="disabled")
            return
        if command == "help":
            self._append_output("Try: pwd, ls, mkdir notes, cat notes/file.txt, python --version, cd notes\n")
            return
        if command == "cd" or command.startswith("cd "):
            try:
                args = shlex.split(command)
                if len(args) > 2:
                    raise ValueError("Usage: cd [folder]")
                folder = workspace_path(args[1] if len(args) == 2 else WORKSPACE, self.cwd)
            except ValueError as exc:
                self._append_output(f"cd: {exc}\n")
                return
            self._submit("Changing directory", lambda: self.backend.list_files(folder),
                         lambda _entries: self._changed_directory(folder))
            return
        self._submit("Running command", lambda: self.backend.execute(command, cwd=self.cwd),
                     self._command_result)

    def _changed_directory(self, path: str) -> None:
        self.cwd = path
        self.cwd_var.set(path)
        self._append_output(f"Now in {path}\n")
        self.status_var.set("Terminal directory: " + path)

    def _command_result(self, result: CommandResult) -> None:
        if result.stdout:
            self._append_output(result.stdout + ("" if result.stdout.endswith("\n") else "\n"))
        if result.stderr:
            self._append_output(result.stderr + ("" if result.stderr.endswith("\n") else "\n"))
        if result.timed_out:
            self._append_output("[Command timed out]\n")
        elif result.truncated:
            self._append_output("[Output truncated]\n")
        elif result.exit_code:
            self._append_output(f"[Exit code {result.exit_code}]\n")
        self.status_var.set("Command finished (exit " + str(result.exit_code) + ")")

    def close(self) -> None:
        if self.editor_dirty and not messagebox.askyesno(
            "Unsaved changes", "Discard unsaved editor changes and close?", parent=self
        ):
            return
        self._shutdown()

    def _shutdown(self) -> None:
        """Cancel Tk callbacks before destroying this window."""
        if self._closed:
            return
        self._closed = True
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        # Do not stop Docker: the named volume/container are persistent.
        self.destroy()


def main() -> None:
    """Run the desktop on its own to test it before game integration."""
    from ..ui_theme import apply_theme

    root = tk.Tk()
    apply_theme(root)
    root.withdraw()
    computer = ComputerWindow(root)
    def close_standalone() -> None:
        computer.close()
        if computer._closed:
            root.destroy()

    computer.protocol("WM_DELETE_WINDOW", close_standalone)
    root.mainloop()


if __name__ == "__main__":
    main()
