"""Tests for world_library snapshot management operations."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kleinos.world_library import (
    WorldLibraryError,
    delete_snapshot,
    list_library,
    rename_snapshot,
    save_snapshot,
)

_WORLD = {"version": 1, "name": "Test", "start_room": "a", "rooms": []}


class DuplicateNameTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wip = Path(self.tmp.name) / "wip.json"
        self.lib = Path(self.tmp.name) / "lib"
        self.wip.write_text(json.dumps(_WORLD), encoding="utf-8")

    def _save(self, name: str) -> Path:
        with patch("kleinos.world_library.WIP_WORLD", self.wip), \
             patch("kleinos.world_library.LIBRARY_DIR", self.lib):
            return save_snapshot(name, source=self.wip)

    def _list(self):
        with patch("kleinos.world_library.LIBRARY_DIR", self.lib):
            return list_library()

    def test_first_save_keeps_name(self):
        self._save("Alpha")
        entries = self._list()
        self.assertEqual(entries[0]["name"], "Alpha")

    def test_duplicate_gets_suffix(self):
        self._save("Alpha")
        self._save("Alpha")
        names = {e["name"] for e in self._list()}
        self.assertIn("Alpha", names)
        self.assertIn("Alpha_01", names)

    def test_third_duplicate_increments(self):
        self._save("Beta")
        self._save("Beta")
        self._save("Beta")
        names = {e["name"] for e in self._list()}
        self.assertIn("Beta", names)
        self.assertIn("Beta_01", names)
        self.assertIn("Beta_02", names)

    def test_different_names_unaffected(self):
        self._save("Gamma")
        self._save("Delta")
        names = {e["name"] for e in self._list()}
        self.assertEqual(names, {"Gamma", "Delta"})


class RenameSnapshotTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lib = Path(self.tmp.name) / "lib"
        self.lib.mkdir()
        self.snap = self.lib / "snap_20240101_120000.json"
        self.snap.write_text(json.dumps(_WORLD), encoding="utf-8")

    def test_rename_updates_name_field(self):
        rename_snapshot(self.snap, "New Name")
        data = json.loads(self.snap.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "New Name")

    def test_empty_name_raises(self):
        with self.assertRaises(WorldLibraryError):
            rename_snapshot(self.snap, "   ")


class DeleteSnapshotTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lib = Path(self.tmp.name) / "lib"
        self.lib.mkdir()
        self.snap = self.lib / "snap_20240101_120000.json"
        self.snap.write_text(json.dumps(_WORLD), encoding="utf-8")

    def test_delete_removes_file(self):
        delete_snapshot(self.snap)
        self.assertFalse(self.snap.exists())


if __name__ == "__main__":
    unittest.main()
