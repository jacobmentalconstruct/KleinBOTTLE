import json
from pathlib import Path
import tempfile
import unittest

from src.game import GameSession
from src.world_builder import WorldBuilder
from src.world_store import WorldStore


class GameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "world.json"
        self.store = WorldStore(self.path)
        fixture = Path(__file__).resolve().parents[1] / "examples" / "rooms.json"
        builder = WorldBuilder(self.store)
        builder.import_json(fixture.read_text(encoding="utf-8"), mode="replace")
        self.original_bytes = self.path.read_bytes()
        self.game = GameSession(self.store)

    def test_start_and_look(self):
        self.assertEqual(self.game.view().room_id, "hall")
        self.assertIn("Oak Table", self.game.execute("look"))
        self.assertIn("Rain on the roof", self.game.execute("l"))
        self.assertIn("north", self.game.execute("look"))

    def test_movement_and_enter_leave(self):
        self.assertIn("Study", self.game.execute("go north"))
        self.assertEqual(self.game.view().room_id, "study")
        self.assertIn("Inside Wardrobe", self.game.execute("enter wardrobe"))
        self.assertEqual(self.game.view().room_id, "wardrobe")
        self.assertIn("Study", self.game.execute("leave"))
        self.assertEqual(self.game.view().room_id, "study")
        self.assertIn("Entrance Hall", self.game.execute("south"))

    def test_take_drop_and_inspect(self):
        self.game.execute("north")
        self.game.execute("inside")
        self.assertIn("small iron key", self.game.execute("look at key"))
        self.assertIn("Taken: Iron Key", self.game.execute("pick up key"))
        self.assertIn("Iron Key", self.game.execute("inventory"))
        self.assertNotIn("You see:", self.game.execute("look"))
        self.game.execute("outside")
        self.assertIn("Iron Key", self.game.execute("i"))
        self.assertIn("Dropped: Iron Key", self.game.execute("drop iron key"))
        self.assertIn("Iron Key", self.game.execute("look"))
        self.assertIn("empty", self.game.execute("inventory"))

    def test_furniture_not_portable(self):
        self.assertIn("can't take", self.game.execute("take table"))
        self.assertIn("scarred oak table", self.game.execute("inspect table"))

    def test_restart_uses_saved_world_not_session_state(self):
        self.game.execute("north")
        self.game.execute("inside")
        self.game.execute("take key")
        self.assertEqual(self.path.read_bytes(), self.original_bytes)
        self.game.restart()
        self.assertEqual(self.game.view().room_id, "hall")
        self.assertEqual(self.game.inventory, [])
        self.game.execute("north")
        self.game.execute("inside")
        self.assertIn("Iron Key", self.game.look())

    def test_reloading_editor_changes(self):
        builder = WorldBuilder(self.store)
        builder.save_room({"id": "attic", "name": "Attic", "exits": {"down": "hall"}})
        hall = builder.room("hall")
        hall["exits"]["up"] = "attic"
        builder.save_room(hall, original_id="hall")
        self.game.restart()
        self.assertIn("Attic", self.game.execute("go up"))

    def test_unknown_exit_and_commands(self):
        self.assertIn("No exit", self.game.execute("go west"))
        self.assertIn("Unknown command", self.game.execute("dance"))
        self.assertIn("Commands:", self.game.execute("help"))
        self.assertEqual(self.game.view().room_id, "hall")

    def test_unresolved_exit_graceful(self):
        builder = WorldBuilder(self.store)
        hall = builder.room("hall")
        hall["exits"]["east"] = "does_not_exist"
        builder.save_room(hall, original_id="hall")
        self.game.restart()
        self.assertIn("missing room", self.game.execute("east"))
        self.assertEqual(self.game.view().room_id, "hall")

    def test_empty_world(self):
        WorldBuilder(self.store).import_json(json.dumps({"rooms": []}), mode="replace")
        self.game.restart()
        self.assertIn("no starting room", self.game.look())
        self.assertIn("no starting room", self.game.execute("go north"))

    def test_ambiguous_object_name(self):
        builder = WorldBuilder(self.store)
        hall = builder.room("hall")
        hall["objects"].append({"id": "dining_table", "name": "Pine Table", "kind": "furniture"})
        builder.save_room(hall, original_id="hall")
        self.game.restart()
        # An exact object ID wins over partial name matches.
        self.assertIn("scarred oak", self.game.execute("inspect table"))
        self.assertIn("Pine Table", self.game.execute("inspect pine"))
        hall = builder.room("hall")
        hall["objects"].append({"id": "desk_a", "name": "Red Desk"})
        hall["objects"].append({"id": "desk_b", "name": "Blue Desk"})
        builder.save_room(hall, original_id="hall")
        self.game.restart()
        self.assertIn("Which one?", self.game.execute("inspect desk"))

    def test_hidden_objects_not_exposed(self):
        builder = WorldBuilder(self.store)
        hall = builder.room("hall")
        hall["objects"].append({"id": "secret", "name": "Secret", "kind": "item", "hidden": True})
        builder.save_room(hall, original_id="hall")
        self.game.restart()
        self.assertNotIn("Secret", self.game.look())
        self.assertIn("don't see", self.game.execute("take secret"))

    def test_explicit_portability_override(self):
        builder = WorldBuilder(self.store)
        hall = builder.room("hall")
        hall["objects"].append({"id": "boulder", "name": "Boulder", "kind": "item", "portable": False})
        hall["objects"].append({"id": "vase", "name": "Vase", "kind": "furniture", "portable": True})
        builder.save_room(hall, original_id="hall")
        self.game.restart()
        self.assertIn("can't take", self.game.execute("take boulder"))
        self.assertIn("Taken", self.game.execute("take vase"))


if __name__ == "__main__":
    unittest.main()
