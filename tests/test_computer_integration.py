"""KleinOS v0.1: one in-world terminal opens the existing desktop."""
from __future__ import annotations

from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from src.game import GameSession
from src.world_store import WorldStore
from src.ui_theme import apply_theme


class TerminalGameTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "world.json"
        self.store = WorldStore(self.path)
        self.store.save({
            "version": 1,
            "name": "Terminal Fixture",
            "start_room": "study",
            "rooms": [
                {"id": "study", "name": "Study", "exits": {"out": "hall"},
                 "objects": [
                     {"id": "station_01", "name": "Retro Station", "kind": "terminal",
                      "description": "An old computer ready to be used.", "portable": False},
                     {"id": "phone", "name": "Black Phone", "kind": "telephone"},
                 ]},
                {"id": "hall", "name": "Hall", "exits": {"in": "study"}, "objects": []},
            ],
        })
        self.original_bytes = self.path.read_bytes()
        self.game = GameSession(self.store)

    def test_look_inspect_help_show_terminal(self) -> None:
        self.assertIn("use computer", self.game.execute("look"))
        self.assertIn("use computer", self.game.execute("inspect retro station"))
        self.assertIn("use computer", self.game.execute("help"))

    def test_use_computer_yields_one_window_request(self) -> None:
        self.assertIn("KleinOS desktop", self.game.execute("use computer"))
        obj = self.game.consume_computer_request()
        self.assertEqual(obj["id"], "station_01")
        self.assertIsNone(self.game.consume_computer_request())
        self.assertEqual(self.game.view().room_id, "study")
        self.assertEqual(self.path.read_bytes(), self.original_bytes)

    def test_aliases_and_named_selection(self) -> None:
        for command in ("use pc", "use terminal", "use the computer", "use retro station"):
            self.assertIn("KleinOS desktop", self.game.execute(command))
            self.assertEqual(self.game.consume_computer_request()["id"], "station_01")

    def test_empty_missing_and_wrong_kind(self) -> None:
        self.assertIn("Use what?", self.game.execute("use"))
        self.assertIsNone(self.game.consume_computer_request())
        self.assertIn("No computer named", self.game.execute("use phone"))
        self.assertIsNone(self.game.consume_computer_request())
        self.game.execute("go out")
        self.assertIn("no computer terminal", self.game.execute("use computer"))
        self.assertIsNone(self.game.consume_computer_request())

    def test_hidden_terminal_not_usable(self) -> None:
        self.game.world["rooms"][0]["objects"][0]["hidden"] = True
        self.assertNotIn("use computer", self.game.look())
        self.assertIn("no computer terminal", self.game.execute("use computer"))
        self.assertIsNone(self.game.consume_computer_request())

    def test_multiple_terminals_are_disambiguated(self) -> None:
        self.game.world["rooms"][0]["objects"].append({
            "id": "station_02", "name": "Blue Station", "kind": "terminal",
        })
        self.assertIn("Which computer?", self.game.execute("use computer"))
        self.assertIsNone(self.game.consume_computer_request())
        self.assertIn("KleinOS desktop", self.game.execute("use blue station"))
        self.assertEqual(self.game.consume_computer_request()["id"], "station_02")

    def test_pending_request_is_cleared_by_new_command_and_reload(self) -> None:
        self.game.execute("use computer")
        self.game.execute("look")
        self.assertIsNone(self.game.consume_computer_request())
        self.game.execute("use computer")
        self.game.restart()
        self.assertIsNone(self.game.consume_computer_request())

    def test_phone_still_handles_its_commands(self) -> None:
        self.assertIn("line clicks open", self.game.execute("answer phone"))
        self.assertTrue(self.game.on_phone)
        self.assertIsNone(self.game.consume_computer_request())
        self.assertIn("on the telephone", self.game.execute("use computer"))
        self.assertIsNone(self.game.consume_computer_request())
        self.assertIn("hang up", self.game.execute("hang up"))
        self.assertFalse(self.game.on_phone)
        self.assertIn("KleinOS desktop", self.game.execute("use computer"))


class TerminalPlaySurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        from src.surfaces.game import GameSurface
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.addCleanup(self.root.destroy)
        apply_theme(self.root)
        self.root.withdraw()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        store = WorldStore(Path(self.tmp.name) / "world.json")
        store.save({"version": 1, "name": "Window Fixture", "start_room": "office",
                    "rooms": [{"id": "office", "name": "Office", "objects": [
                        {"id": "desk_pc", "name": "Desk Computer", "kind": "terminal"}
                    ], "exits": {}}]})
        self.session = GameSession(store)
        self.surface = GameSurface(self.root, self.session)
        self.surface.pack()
        self.addCleanup(self.surface.destroy)

    def test_one_popup_and_no_play_restart(self) -> None:
        with patch("src.surfaces.game.ComputerWindow") as popup:
            window = popup.return_value
            window.winfo_exists.return_value = True
            self.surface.run("use computer")
            popup.assert_called_once_with(self.root)
            self.assertEqual(self.session.room_id, "office")
            self.surface.run("use computer")
            popup.assert_called_once()
            window.lift.assert_called_once()
            window.focus_set.assert_called_once()
            window.winfo_exists.return_value = False
            self.surface.run("use computer")
            self.assertEqual(popup.call_count, 2)

    def test_missing_terminal_never_opens_popup(self) -> None:
        self.session.world["rooms"][0]["objects"].clear()
        with patch("src.surfaces.game.ComputerWindow") as popup:
            self.surface.run("use computer")
            popup.assert_not_called()
            self.assertIn("no computer terminal", self.surface.transcript.get("1.0", "end"))

    def test_computer_creation_error_is_reported(self) -> None:
        with patch("src.surfaces.game.ComputerWindow", side_effect=RuntimeError("test startup fault")):
            self.surface.run("use computer")
        self.assertIn("test startup fault", self.surface.transcript.get("1.0", "end"))


if __name__ == "__main__":
    unittest.main()
