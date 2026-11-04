import json
from pathlib import Path
import tempfile
import unittest

from src.world_builder import WorldBuilder
from src.world_model import WorldValidationError
from src.world_store import WorldStore


def room(room_id, exits=None):
    return {"id": room_id, "name": room_id.capitalize(), "area": "House", "exits": exits or {}}


class WorldBuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "data" / "world.json"
        self.builder = WorldBuilder(WorldStore(self.path))

    def test_create_and_reload(self):
        self.builder.save_room(room("hall"))
        other = WorldBuilder(WorldStore(self.path))
        self.assertEqual(other.world["start_room"], "hall")
        self.assertEqual(other.room("hall")["name"], "Hall")

    def test_import_list_and_merge_duplicates(self):
        self.builder.save_room(room("hall"))
        changed, skipped = self.builder.import_json(json.dumps([room("hall"), room("study")]))
        self.assertEqual((changed, skipped), (1, 1))
        self.assertEqual(len(self.builder.rooms()), 2)

    def test_import_replace_one_and_keep_other(self):
        self.builder.import_json(json.dumps([room("hall"), room("study")]))
        new_study = {**room("study"), "name": "Library", "secrets": [{"id": "panel"}]}
        changed, skipped = self.builder.import_json(json.dumps(new_study), mode="update")
        self.assertEqual((changed, skipped), (1, 0))
        self.assertEqual(self.builder.room("study")["name"], "Library")
        self.assertEqual(len(self.builder.rooms()), 2)
        self.assertEqual(self.builder.room("study")["secrets"][0]["id"], "panel")

    def test_import_world_and_room_map(self):
        source = {"version": 1, "name": "Example", "start_room": "room_a", "rooms": {"room_a": {"name": "A"}}}
        self.builder.import_json(json.dumps(source), mode="replace")
        self.assertEqual(self.builder.world["name"], "Example")
        self.assertEqual(self.builder.world["start_room"], "room_a")

    def test_unresolved_exits_warn_not_block(self):
        self.builder.save_room(room("hall", {"north": "study"}))
        self.assertEqual(len(self.builder.warnings()), 1)
        self.builder.save_room(room("study"))
        self.assertEqual(self.builder.warnings(), [])

    def test_delete_referenced_room_blocked(self):
        self.builder.save_room(room("hall", {"north": "study"}))
        self.builder.save_room(room("study"))
        with self.assertRaises(WorldValidationError):
            self.builder.delete_room("study")
        self.assertEqual(len(self.builder.rooms()), 2)

    def test_bad_import_does_not_change_file(self):
        self.builder.save_room(room("hall"))
        old = self.path.read_bytes()
        with self.assertRaises(WorldValidationError):
            self.builder.import_json('[{"id":"new","name":"Ok"},{"id":"new","name":"Duplicate"}]')
        self.assertEqual(self.path.read_bytes(), old)

    def test_extra_properties_survive_form_style_update(self):
        incoming = {**room("hall"), "visual_fx": {"fog": True}, "actors": [{"id": "keeper"}]}
        self.builder.save_room(incoming)
        updated = self.builder.room("hall")
        updated["description"] = "Edited"
        self.builder.save_room(updated, original_id="hall")
        self.assertEqual(self.builder.room("hall")["visual_fx"], {"fog": True})
        self.assertEqual(self.builder.room("hall")["actors"][0]["id"], "keeper")

    def test_room_id_immutable(self):
        self.builder.save_room(room("hall"))
        with self.assertRaises(WorldValidationError):
            self.builder.save_room(room("new_id"), original_id="hall")


if __name__ == "__main__":
    unittest.main()
