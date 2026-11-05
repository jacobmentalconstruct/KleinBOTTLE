"""KleinOS desktop tests. Fake backend; no Docker or game-world changes.

Tk tests run when a graphical display is available, and otherwise skip.
"""
from __future__ import annotations

import time
import gc
import tkinter as tk
import unittest

from src.computer_backend import CommandResult
from src.surfaces.computer import ComputerWindow, valid_filename, workspace_path
from src.ui_theme import apply_theme
from unittest.mock import patch


class WorkspacePathTests(unittest.TestCase):
    def test_navigation_stays_inside_workspace(self):
        self.assertEqual(workspace_path("notes", "/workspace"), "/workspace/notes")
        self.assertEqual(workspace_path("..", "/workspace/notes"), "/workspace")
        self.assertEqual(workspace_path("/workspace/a/../b"), "/workspace/b")
        self.assertEqual(workspace_path("~"), "/workspace")
        for value in ("/etc/passwd", "../etc", "../../work", "\\windows", "x\x00y"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                workspace_path(value)

    def test_new_names_are_single_components(self):
        for name in ("notes", "room.json", "a b.txt", "📝.txt"):
            self.assertTrue(valid_filename(name))
        for name in ("", ".", "..", "a/b", "a\\b", "a\x00b", "x" * 256):
            self.assertFalse(valid_filename(name))


class FakeBackend:
    def __init__(self):
        self.started = False
        self.executed: list[tuple[str, str]] = []
        self.files: dict[str, str] = {"/workspace/hello.txt": "Hello from Docker\n"}
        self.dirs = {"/workspace", "/workspace/notes"}

    def start(self):
        self.started = True

    def list_files(self, folder="/workspace"):
        if folder not in self.dirs:
            raise ValueError("Not a folder")
        entries = []
        for directory in sorted(self.dirs):
            if directory != folder and directory.rpartition("/")[0] == folder:
                entries.append({"name": directory.rsplit("/", 1)[-1], "path": directory.removeprefix("/workspace/"),
                                "is_dir": True, "size": None})
        for path, content in sorted(self.files.items()):
            if path.rpartition("/")[0] == folder:
                entries.append({"name": path.rsplit("/", 1)[-1], "path": path.removeprefix("/workspace/"),
                                "is_dir": False, "size": len(content.encode("utf-8"))})
        return entries

    def read_file(self, path):
        return self.files[path]

    def write_file(self, path, content):
        if path.rpartition("/")[0] not in self.dirs:
            raise ValueError("Missing parent folder")
        self.files[path] = content

    def execute(self, command, *, cwd="/workspace"):
        self.executed.append((command, cwd))
        if command.startswith("mkdir -- "):
            self.dirs.add(cwd + "/" + command[len("mkdir -- "):])
        return CommandResult(0, cwd + "\n", "")


class DesktopGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"No Tk display: {exc}") from exc
        apply_theme(cls.root)
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        gc.collect()
        cls.root.destroy()
        gc.collect()

    def setUp(self):
        self.backend = FakeBackend()
        self.window = ComputerWindow(self.root, backend=self.backend)
        self.window.withdraw()
        self.pump_until(lambda: not self.window._busy and self.window._ready)

    def tearDown(self):
        self.window._shutdown()
        self.root.update()
        gc.collect()

    def pump_until(self, condition, seconds=4):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.root.update()
            if condition():
                return
            time.sleep(0.02)
        self.fail(f"GUI background operation did not finish: {self.window.status_var.get()}")

    def test_initial_files_are_loaded(self):
        self.assertTrue(self.backend.started)
        self.assertEqual(self.window.path_var.get(), "/workspace")
        self.assertIn("hello.txt", [obj["name"] for obj in self.window._items.values()])
        self.assertIn("notes", [obj["name"] for obj in self.window._items.values()])

    def test_folder_browsing_and_up(self):
        key = next(key for key, obj in self.window._items.items() if obj["name"] == "notes")
        self.window.file_tree.selection_set(key)
        self.window._open_selected()
        self.pump_until(lambda: not self.window._busy)
        self.assertEqual(self.window.directory, "/workspace/notes")
        self.window.go_up()
        self.pump_until(lambda: not self.window._busy)
        self.assertEqual(self.window.directory, "/workspace")

    def test_open_modify_and_save_file(self):
        self.window.open_file("/workspace/hello.txt")
        self.pump_until(lambda: not self.window._busy)
        self.assertEqual(self.window.editor_path, "/workspace/hello.txt")
        self.assertEqual(self.window.editor.get("1.0", "end-1c"), "Hello from Docker\n")
        self.window.editor.insert("end", "Edited!\n")
        self.root.update()
        self.assertTrue(self.window.editor_dirty)
        self.window.save_file()
        self.pump_until(lambda: not self.window._busy)
        self.assertEqual(self.backend.files["/workspace/hello.txt"], "Hello from Docker\nEdited!\n")
        self.assertFalse(self.window.editor_dirty)

    def test_terminal_exec_and_cd_are_container_backend_only(self):
        self.window.command_entry.insert(0, "python --version")
        self.window.run_command()
        self.pump_until(lambda: not self.window._busy)
        self.assertEqual(self.backend.executed, [("python --version", "/workspace")])
        self.assertIn("/workspace", self.window.output.get("1.0", "end"))
        self.window.command_entry.insert(0, "cd notes")
        self.window.run_command()
        self.pump_until(lambda: not self.window._busy)
        self.assertEqual(self.window.cwd, "/workspace/notes")
        self.assertEqual(len(self.backend.executed), 1)
        self.window.command_entry.insert(0, "cd ..")
        self.window.run_command()
        self.pump_until(lambda: not self.window._busy)
        self.assertEqual(self.window.cwd, "/workspace")

    def test_new_file_and_folder_use_workspace_only(self):
        with patch("src.surfaces.computer.simpledialog.askstring", return_value="newroom.json"):
            self.window.new_file()
        self.assertEqual(self.window.editor_path, "/workspace/newroom.json")
        self.window.editor.insert("1.0", '{"name": "New Room"}')
        self.window.save_file()
        self.pump_until(lambda: not self.window._busy)
        self.assertIn("/workspace/newroom.json", self.backend.files)
        with patch("src.surfaces.computer.simpledialog.askstring", return_value="levels"):
            self.window.new_folder()
        self.pump_until(lambda: not self.window._busy)
        self.assertIn("/workspace/levels", self.backend.dirs)
        self.assertEqual(self.backend.executed[-1], ("mkdir -- levels", "/workspace"))

    def test_timeout_result_is_reported(self):
        self.window._command_result(CommandResult(124, "", "", timed_out=True))
        self.assertIn("timed out", self.window.output.get("1.0", "end"))


if __name__ == "__main__":
    unittest.main()
