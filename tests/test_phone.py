"""Telephone lifecycle and local transport, without a running Ollama service."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import json

from src.game import GameSession
from src.ollama_phone import chat, OllamaPhoneError
from src.world_builder import WorldBuilder
from src.world_store import WorldStore


class PhoneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        store = WorldStore(Path(self.tmp.name) / "world.json")
        builder = WorldBuilder(store)
        builder.import_json((Path(__file__).resolve().parents[1] / "examples" / "rooms.json").read_text("utf-8"), mode="replace")
        self.original = store.path.read_bytes()
        self.game = GameSession(store)
        self.store = store

    def test_phone_visible_and_answers(self):
        self.assertIn("no telephone", self.game.execute("answer phone"))
        self.game.execute("north")
        self.assertIn("rings relentlessly", self.game.look())
        self.assertIn("The ringing stops", self.game.execute("answer phone"))
        self.assertTrue(self.game.on_phone)
        self.assertNotIn("rings relentlessly", self.game.look())
        serial, model, messages = self.game.phone_payload("Hello?")
        self.assertEqual(model, "qwen2.5:3b")
        self.assertEqual(messages[-1], {"role":"user","content":"Hello?"})
        self.assertTrue(self.game.finish_phone_reply(serial, "Hello?", "Who is this?"))
        self.assertEqual(self.game.phone_payload("Hello again")[2][-2]["content"], "Who is this?")
        self.assertIn("hang up", self.game.execute("hang up"))
        self.assertFalse(self.game.on_phone)
        self.assertFalse(self.game.finish_phone_reply(serial, "Hello?", "late reply"))
        self.assertEqual(self.store.path.read_bytes(), self.original)

    def test_world_reload_cancels_in_flight_reply(self):
        self.game.execute("north")
        self.game.execute("answer phone")
        serial, _, _ = self.game.phone_payload("Hello")
        self.game.restart()
        self.assertFalse(self.game.finish_phone_reply(serial,"Hello","Reply"))
        self.game.execute("north")
        self.assertIn("rings relentlessly",self.game.look())

    @patch("src.ollama_phone.http.client.HTTPConnection")
    def test_ollama_requests_only_loopback(self, fake):
        instance = fake.return_value
        response = instance.getresponse.return_value
        response.status = 200
        response.read.return_value = json.dumps({"message":{"role":"assistant","content":"Hello, caller."}}).encode()
        self.assertEqual(chat("qwen2.5:3b",[{"role":"user","content":"Hello"}]), "Hello, caller.")
        fake.assert_called_once_with("127.0.0.1",11434,timeout=60)
        args,kwargs = instance.request.call_args
        self.assertEqual(args[:2],("POST","/api/chat"))
        body = json.loads(kwargs["body"])
        self.assertEqual(body["model"],"qwen2.5:3b")
        self.assertFalse(body["stream"])

    @patch("src.ollama_phone.http.client.HTTPConnection")
    def test_offline_ollama_failure(self, fake):
        fake.return_value.request.side_effect = ConnectionRefusedError()
        with self.assertRaisesRegex(OllamaPhoneError,"Cannot reach local Ollama"):
            chat("qwen2.5:3b",[])

    @patch("src.ollama_phone.http.client.HTTPConnection")
    def test_missing_local_model(self, fake):
        fake.return_value.getresponse.return_value.status = 404
        fake.return_value.getresponse.return_value.read.return_value = b'{}'
        with self.assertRaisesRegex(OllamaPhoneError,"ollama pull"):
            chat("qwen2.5:3b",[])

if __name__ == "__main__":
    unittest.main()
