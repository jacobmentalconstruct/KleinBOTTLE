"""T6 — critical workflow regression tests.

Covers the five workflows flagged as untested in audit finding F11:

  1. world_library.validate_for_promotion  (pure logic)
  2. world_library.promote_to_main         (file I/O)
  3. MAHisLAND _save_game / _load_game     (save-state roundtrip)
  4. KleinPC._set_sidebar_enabled          (sidebar lifecycle)
  5. KleinAdventurePane._poll_room cancel  (T1 regression guard)
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from kleinos.world_library import (
    WorldLibraryError,
    promote_to_main,
    validate_for_promotion,
)


# ── Helpers ───────────────────────────────────────────────────────────

def _valid_world() -> dict:
    """Minimal world that passes validate_for_promotion."""
    return {
        "version": 1,
        "name": "Test World",
        "start_room": "entrance",
        "rooms": [
            {
                "id": "entrance",
                "name": "Entrance",
                "area": "Zone",
                "description": "",
                "exits": {"north": "terminal_room"},
                "objects": [],
            },
            {
                "id": "terminal_room",
                "name": "Terminal Room",
                "area": "Zone",
                "description": "",
                "exits": {},
                "objects": [{"id": "pc", "name": "KleinOS", "kind": "terminal"}],
            },
        ],
    }


# ─────────────────────────────────────────────────────────────────────
# 1 + 2 — world_library
# ─────────────────────────────────────────────────────────────────────

class ValidateForPromotionTests(unittest.TestCase):

    def test_no_start_room_raises(self):
        world = _valid_world()
        world["start_room"] = None
        with self.assertRaises(WorldLibraryError):
            validate_for_promotion(world)

    def test_unresolved_exit_raises(self):
        world = _valid_world()
        world["rooms"][0]["exits"]["east"] = "nowhere"
        with self.assertRaises(WorldLibraryError):
            validate_for_promotion(world)

    def test_no_reachable_terminal_raises(self):
        world = _valid_world()
        world["rooms"][1]["objects"] = []  # remove terminal
        with self.assertRaises(WorldLibraryError):
            validate_for_promotion(world)

    def test_valid_world_passes(self):
        validate_for_promotion(_valid_world())  # must not raise

    def test_terminal_behind_unreachable_room_raises(self):
        """Terminal in a room that has no path from start → still fails."""
        world = _valid_world()
        world["rooms"][0]["exits"] = {}       # cut path to terminal_room
        with self.assertRaises(WorldLibraryError):
            validate_for_promotion(world)


class PromoteToMainTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def test_valid_world_replaces_main(self):
        source = self.base / "candidate.json"
        main   = self.base / "world.json"
        lib    = self.base / "library"

        source.write_text(json.dumps(_valid_world()), encoding="utf-8")
        # Pre-existing Main that should be backed up
        main.write_text(
            json.dumps({"version": 1, "name": "Old", "start_room": None, "rooms": []}),
            encoding="utf-8",
        )

        with patch("kleinos.world_library.MAIN_WORLD", main), \
             patch("kleinos.world_library.LIBRARY_DIR", lib):
            promote_to_main(source)

        promoted = json.loads(main.read_text(encoding="utf-8"))
        self.assertEqual(promoted["start_room"], "entrance")
        # Old Main backed up as a snapshot
        self.assertTrue(any(lib.glob("*.json")), "backup snapshot not created")

    def test_invalid_world_does_not_modify_main(self):
        source = self.base / "bad.json"
        main   = self.base / "world.json"
        lib    = self.base / "library"

        source.write_text(json.dumps({"version": 1, "name": "Bad", "start_room": None,
                                      "rooms": []}), encoding="utf-8")
        original = b"original"
        main.write_bytes(original)

        with patch("kleinos.world_library.MAIN_WORLD", main), \
             patch("kleinos.world_library.LIBRARY_DIR", lib):
            with self.assertRaises(WorldLibraryError):
                promote_to_main(source)

        self.assertEqual(main.read_bytes(), original)


# ─────────────────────────────────────────────────────────────────────
# 3 — MAHisLAND save/load roundtrip
# ─────────────────────────────────────────────────────────────────────

class MAHisLANDPersistTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.save_path = Path(self.tmp.name) / "mahisland_save.json"

    def _make_fake_pane(self):
        """Minimal object satisfying _PersistMixin's attribute contract."""
        from kleinos.mahisland_persist import _PersistMixin

        class FakePane(_PersistMixin):
            def _reset_world(inner_self):
                # Minimal defaults so _load_game can overwrite them
                inner_self._state     = "play"
                inner_self._grid      = []
                inner_self._nodes     = {}
                inner_self._px        = 0.0
                inner_self._py        = 0.0
                inner_self._angle     = 0.0
                inner_self._hp        = 10
                inner_self._hunger    = 10
                inner_self._inv       = []
                inner_self._gear      = set()
                inner_self._structs   = []
                inner_self._score     = 0
                inner_self._high_score = 0
                inner_self._spawn_acc  = 0.0
                inner_self._fuel_acc   = 0.0
                inner_self._hunger_acc = 0.0
                inner_self._camx      = 0.0
                inner_self._camy      = 0.0
                inner_self._vw        = 100.0
                inner_self._vh        = 100.0

        pane = FakePane()
        pane._reset_world()
        return pane

    def test_save_load_roundtrip(self):
        pane = self._make_fake_pane()
        pane._px        = 42.5
        pane._py        = 99.0
        pane._hp        = 7
        pane._hunger    = 3
        pane._score     = 1500
        pane._high_score = 1000
        pane._gear      = {"axe", "helm"}
        pane._inv       = [{"id": "wood", "qty": 5}]

        with patch("kleinos.mahisland_persist._SAVE_PATH", self.save_path):
            pane._save_game()

        self.assertTrue(self.save_path.exists(), "save file not created")

        loader = self._make_fake_pane()
        with patch("kleinos.mahisland_persist._SAVE_PATH", self.save_path):
            loader._load_game()

        self.assertAlmostEqual(loader._px, 42.5)
        self.assertAlmostEqual(loader._py, 99.0)
        self.assertEqual(loader._hp, 7)
        self.assertEqual(loader._hunger, 3)
        self.assertEqual(loader._score, 1500)
        self.assertEqual(loader._high_score, 1500)  # max(old_high, score)
        self.assertEqual(loader._gear, {"axe", "helm"})
        self.assertEqual(loader._inv[0]["id"], "wood")

    def test_corrupt_save_resets_world(self):
        """Corrupt save file must not raise — _reset_world runs instead."""
        self.save_path.write_text("not valid json", encoding="utf-8")
        pane = self._make_fake_pane()
        pane._px = 999.0
        with patch("kleinos.mahisland_persist._SAVE_PATH", self.save_path):
            pane._load_game()
        # After failed load, _reset_world ran → px back to 0
        self.assertEqual(pane._px, 0.0)


# ─────────────────────────────────────────────────────────────────────
# 4 — KleinPC sidebar lifecycle (no Tkinter needed)
# ─────────────────────────────────────────────────────────────────────

class KleinPCSidebarTests(unittest.TestCase):

    def _make_fake_pc(self):
        """Duck-type object covering KleinPC._set_sidebar_enabled."""
        from kleinos.klein_pc import KleinPC

        class FakePC:
            def __init__(inner_self):
                inner_self._btn_terminal = MagicMock()
                inner_self._btn_settings = MagicMock()
                inner_self._btn_back     = None   # exercises the None guard
                inner_self._item_btns    = {
                    "item_a": MagicMock(),
                    "item_b": MagicMock(),
                }
                inner_self._layout = {
                    "categories": [
                        {"_toggle_btn": MagicMock()},
                        {},           # exercises missing _toggle_btn guard
                    ]
                }

            def _set_sidebar_enabled(inner_self, enabled: bool):
                KleinPC._set_sidebar_enabled(inner_self, enabled)

        return FakePC()

    def test_disable_sets_state_disabled(self):
        pc = self._make_fake_pc()
        pc._set_sidebar_enabled(False)
        pc._btn_terminal.configure.assert_called_with(state="disabled")
        pc._btn_settings.configure.assert_called_with(state="disabled")
        for btn in pc._item_btns.values():
            btn.configure.assert_called_with(state="disabled")
        pc._layout["categories"][0]["_toggle_btn"].configure.assert_called_with(state="disabled")

    def test_enable_sets_state_normal(self):
        pc = self._make_fake_pc()
        pc._set_sidebar_enabled(True)
        pc._btn_terminal.configure.assert_called_with(state="normal")
        pc._btn_settings.configure.assert_called_with(state="normal")

    def test_disable_then_enable_roundtrip(self):
        pc = self._make_fake_pc()
        pc._set_sidebar_enabled(False)
        pc._set_sidebar_enabled(True)
        # Last call must be "normal"
        pc._btn_terminal.configure.assert_called_with(state="normal")
        pc._btn_settings.configure.assert_called_with(state="normal")

    def test_game_launch_disables_sidebar_exit_restores(self):
        """_select_item with KleinGame: sidebar disabled on launch, re-enabled on exit."""
        from kleinos.klein_app import KleinGame
        from kleinos.klein_pc import KleinPC

        sidebar_states: list[bool] = []

        class FakePC2:
            _content      = None
            _item_btns    = {}
            _layout       = {"categories": []}
            _btn_terminal = None
            _btn_settings = None
            _btn_back     = None

            def _set_sidebar_enabled(inner_self, en: bool) -> None:
                sidebar_states.append(en)

            def _set_active(inner_self, btn, title=None) -> None:
                pass

            def _select_terminal(inner_self) -> None:
                pass

            def _swap(inner_self, factory) -> None:
                factory()  # call immediately to trigger game.create

        class FakeGame(KleinGame):
            title = "FakeGame"

            def create(inner_self, parent, *, on_exit=None):
                inner_self._exit_callback = on_exit
                return object()

        pc   = FakePC2()
        game = FakeGame()
        KleinPC._select_item(pc, game)

        self.assertEqual(sidebar_states, [False], "sidebar not disabled on launch")

        game._exit_callback()
        self.assertIn(True, sidebar_states, "sidebar not re-enabled on exit")


# ─────────────────────────────────────────────────────────────────────
# 5 — KleinAdventurePane._poll_room cancel-on-destroy (T1 regression)
# ─────────────────────────────────────────────────────────────────────

class PollRoomCancelTests(unittest.TestCase):

    def test_on_destroy_cancels_pending_poll(self):
        """T1 fix: _on_destroy must call after_cancel with the stored poll id."""
        from kleinos.kb_surfaces import KleinAdventurePane

        cancelled = []

        class FakePane:
            _poll_id = "after#42"
            _session = None
            _surface = None

            def after_cancel(inner_self, id_):
                cancelled.append(id_)
                inner_self._poll_id = None

            def _on_destroy(inner_self, event):
                KleinAdventurePane._on_destroy(inner_self, event)

        pane = FakePane()
        pane._on_destroy(None)

        self.assertEqual(cancelled, ["after#42"])
        self.assertIsNone(pane._poll_id)

    def test_on_destroy_no_poll_id_is_safe(self):
        """_on_destroy with _poll_id=None must not raise."""
        from kleinos.kb_surfaces import KleinAdventurePane

        class FakePaneNoPoll:
            _poll_id = None

            def after_cancel(inner_self, id_):
                raise AssertionError("after_cancel called with None")

            def _on_destroy(inner_self, event):
                KleinAdventurePane._on_destroy(inner_self, event)

        FakePaneNoPoll()._on_destroy(None)  # must not raise


if __name__ == "__main__":
    unittest.main()
