"""Tiny stateful text-adventure engine. No UI, filesystem writes, or sidecars.

A GameSession loads a snapshot of a world definition. Movement and items alter
only this in-memory play session, never the builder's source JSON.
"""
from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass

from .world_store import WorldStore
from .ollama_phone import DEFAULT_MODEL

# ── Cat reaction table (50/50 purr vs meow, one picked at random per bucket) ──
_CAT_PURRS = [
    "The cat purrs like a small engine.",
    "A deep rumble fills the shelf. Prrrrrrr.",
    "The cat's eyes close to satisfied slits. Purrr.",
    "Vibrations. Pure, contented vibrations.",
]
_CAT_MEOWS = [
    "Mrrrow.",
    "The cat meows once, sharply, then looks away.",
    "A short, indignant meow. It had a point.",
    "The cat opens its mouth. A tiny, offended sound emerges.",
]

DEFAULT_PHONE_PROMPT = (
    "You are a mysterious voice reached by telephone in a text adventure. "
    "Stay in character. Respond conversationally and briefly (1-3 sentences). "
    "You only speak through the telephone; do not narrate player actions."
)


@dataclass(frozen=True)
class GameView:
    world_name: str
    room_id: str | None
    room_name: str
    area: str
    exits: tuple[str, ...]
    inventory: tuple[str, ...]


@dataclass(frozen=True)
class ObjectInfo:
    id: str
    name: str
    short_desc: str
    kind: str


@dataclass(frozen=True)
class ActorInfo:
    id: str
    name: str
    short_desc: str


@dataclass(frozen=True)
class RoomSnapshot:
    room_id: str | None
    room_name: str
    area: str
    description: str
    environment: tuple[tuple[str, str], ...]
    objects: tuple[ObjectInfo, ...]
    actors: tuple[ActorInfo, ...]
    exits: tuple[str, ...]
    has_terminal: bool
    has_cat: bool
    has_ringing_phone: bool


def _name(value: dict) -> str:
    return str(value.get("name") or value.get("id") or "Unnamed").strip()


def _matches(value: dict, query: str) -> bool:
    query = query.casefold().strip()
    if query.startswith("the "):
        query = query[4:]
    names = (str(value.get("id", "")), _name(value))
    return any(item.casefold() == query for item in names)


def _find(values: list[dict], query: str) -> tuple[dict | None, str | None]:
    """Resolve exact ID/name first, then a unique name fragment."""
    exact = [value for value in values if _matches(value, query)]
    matches = exact or [value for value in values if query.casefold().strip() in _name(value).casefold()]
    if len(matches) > 1:
        return None, "Which one? " + ", ".join(_name(value) for value in matches)
    return (matches[0], None) if matches else (None, None)


class GameSession:
    def __init__(self, store: WorldStore):
        self.store = store
        self.world: dict = {}
        self.room_id: str | None = None
        self.inventory: list[dict] = []
        self.phone: dict | None = None
        self.phone_history: list[dict] = []
        self.call_serial = 0
        self._computer_request: dict | None = None
        self.restart()

    def restart(self) -> str:
        """Reload the editor's saved world and begin a fresh play session."""
        self.world = deepcopy(self.store.load())
        self.inventory = []
        self.phone = None
        self.phone_history = []
        self._computer_request = None
        self.call_serial += 1  # invalidate any in-flight replies after restart
        rooms = self.world["rooms"]
        self.room_id = self.world["start_room"] or (rooms[0]["id"] if rooms else None)
        return self.look()

    def _room(self) -> dict | None:
        return next((r for r in self.world["rooms"] if r["id"] == self.room_id), None)

    def view(self) -> GameView:
        room = self._room()
        return GameView(
            world_name=self.world["name"], room_id=self.room_id,
            room_name=room["name"] if room else "No room",
            area=room["area"] if room else "",
            exits=tuple(room["exits"]) if room else (),
            inventory=tuple(_name(obj) for obj in self.inventory),
        )

    def look(self) -> str:
        room = self._room()
        if room is None:
            return "This world has no starting room. Create a room in Builder, then click Reload World."
        lines = [room["name"] + (f" — {room['area']}" if room.get("area") else "")]
        if room.get("description"):
            lines.append(str(room["description"]))
        env = room.get("environment", {})
        for key in ("weather", "light", "sound"):
            if env.get(key):
                lines.append(f"{key.capitalize()}: {env[key]}")
        objects = [obj for obj in room.get("objects", []) if not obj.get("hidden", False)]
        if objects:
            lines.append("You see: " + ", ".join(_name(obj) for obj in objects) + ".")
        if any(str(obj.get("kind", "")).casefold() == "telephone" and obj.get("ringing")
               for obj in objects):
            lines.append("A telephone rings relentlessly. You could 'answer phone'.")
        if any(str(obj.get("kind", "")).casefold() == "terminal" for obj in objects):
            lines.append("A computer terminal is available. Try 'use computer'.")
        actors = [actor for actor in room.get("actors", []) if not actor.get("hidden", False)]
        if actors:
            lines.append("Present: " + ", ".join(_name(actor) for actor in actors) + ".")
        exits = room.get("exits", {})
        lines.append("Exits: " + (", ".join(exits) if exits else "none") + ".")
        return "\n".join(lines)

    def move(self, direction: str) -> str:
        room = self._room()
        if room is None:
            return self.look()
        exits = room["exits"]
        direction = direction.strip().casefold()
        # Accept a direction, destination ID, or destination name (when unique).
        found = [key for key, target in exits.items() if key.casefold() == direction]
        if not found:
            destinations = {r["id"]: r for r in self.world["rooms"]}
            found = [key for key, target in exits.items() if target.casefold() == direction or
                     (target in destinations and destinations[target]["name"].casefold() == direction)]
        if not found:
            return f"No exit '{direction}' from here. Available exits: {', '.join(exits) or 'none'}."
        if len(found) > 1:
            return "Ambiguous destination. Choose an exit: " + ", ".join(found)
        target = exits[found[0]]
        if not any(r["id"] == target for r in self.world["rooms"]):
            return f"Exit '{found[0]}' points to a missing room ('{target}')."
        self.room_id = target
        return self.look()

    def inspect(self, query: str) -> str:
        room = self._room()
        if room is None:
            return self.look()
        if query.casefold().strip() in {"room", "here", "around"}:
            return self.look()
        candidates = ([obj for obj in room.get("objects", []) if not obj.get("hidden", False)]
                      + [actor for actor in room.get("actors", []) if not actor.get("hidden", False)]
                      + self.inventory)
        obj, ambiguity = _find(candidates, query)
        if ambiguity:
            return ambiguity
        if obj is None:
            return f"You don't see '{query}' here."
        description = f"{_name(obj)}\n{obj.get('description') or 'Nothing unusual stands out.'}"
        if str(obj.get("kind", "")).casefold() == "telephone" and obj.get("ringing"):
            description += "\nIt keeps ringing. Try 'answer phone'."
        if str(obj.get("kind", "")).casefold() == "terminal":
            description += "\nYou can operate it. Try 'use computer'."
        return description

    @staticmethod
    def _portable(obj: dict) -> bool:
        # An explicit portable/takeable flag overrides the item kind.
        if "portable" in obj:
            return obj["portable"] is True
        if "takeable" in obj:
            return obj["takeable"] is True
        return str(obj.get("kind", "")).casefold() == "item"

    def take(self, query: str) -> str:
        room = self._room()
        if room is None:
            return self.look()
        objects = [obj for obj in room.get("objects", []) if not obj.get("hidden", False)]
        obj, ambiguity = _find(objects, query)
        if ambiguity:
            return ambiguity
        if obj is None:
            return f"You don't see '{query}' here."
        if not self._portable(obj):
            return f"You can't take {_name(obj)}. (Make it an item or set portable: true.)"
        room["objects"].remove(obj)
        self.inventory.append(obj)
        return f"Taken: {_name(obj)}."

    def drop(self, query: str) -> str:
        room = self._room()
        if room is None:
            return self.look()
        obj, ambiguity = _find(self.inventory, query)
        if ambiguity:
            return ambiguity
        if obj is None:
            return f"You aren't carrying '{query}'."
        self.inventory.remove(obj)
        room["objects"].append(obj)
        return f"Dropped: {_name(obj)}."

    def inventory_text(self) -> str:
        return "You're carrying: " + ", ".join(_name(obj) for obj in self.inventory) + "." if self.inventory else "Your inventory is empty."

    @property
    def on_phone(self) -> bool:
        return self.phone is not None

    def answer_phone(self, query: str = "phone") -> str:
        if self.on_phone:
            return "You're already on the telephone. Type 'hang up' to end the call."
        room = self._room()
        if room is None:
            return self.look()
        phones = [obj for obj in room.get("objects", [])
                  if not obj.get("hidden", False) and
                  str(obj.get("kind", "")).casefold() == "telephone"]
        if not phones:
            return "There is no telephone here."
        if query.casefold().strip() in {"", "phone", "telephone", "receiver"}:
            if len(phones) != 1:
                return "Which telephone? " + ", ".join(_name(obj) for obj in phones)
            obj = phones[0]
        else:
            obj, ambiguity = _find(phones, query)
            if ambiguity:
                return ambiguity
            if obj is None:
                return f"No telephone named '{query}' is here."
        self.phone = obj
        self.phone_history = []
        self.call_serial += 1
        obj["ringing"] = False  # in-memory only; builder's world never changes
        return f"You pick up {_name(obj)}. The ringing stops. A line clicks open..."

    def hang_up(self) -> str:
        if not self.on_phone:
            return "You're not on a call."
        self.phone = None
        self.phone_history = []
        self.call_serial += 1
        return "You hang up the receiver."

    def phone_payload(self, speech: str) -> tuple[int, str, list[dict]]:
        """Prepare one local inference request; commits only after a successful reply."""
        if self.phone is None:
            raise ValueError("No active phone call")
        settings = self.phone.get("ollama")
        settings = settings if isinstance(settings, dict) else {}
        model = settings.get("model") or DEFAULT_MODEL
        system = settings.get("system") or DEFAULT_PHONE_PROMPT
        # Keep a small, bounded history for the 3B model.
        history = self.phone_history[-12:]
        messages = [{"role": "system", "content": str(system)}, *history,
                    {"role": "user", "content": speech}]
        return self.call_serial, model, messages

    def finish_phone_reply(self, serial: int, speech: str, reply: str) -> bool:
        """Ignore late model responses after hangup or world reload."""
        if not self.on_phone or self.call_serial != serial:
            return False
        self.phone_history.extend(({"role": "user", "content": speech},
                                   {"role": "assistant", "content": reply}))
        return True

    def use_computer(self, query: str) -> str:
        """Resolve a visible terminal object; the UI handles its window."""
        room = self._room()
        if room is None:
            return self.look()
        terminals = [obj for obj in room.get("objects", [])
                     if not obj.get("hidden", False) and
                     str(obj.get("kind", "")).casefold() == "terminal"]
        if not terminals:
            return "There is no computer terminal here."
        target = query.casefold().strip()
        if target.startswith("the "):
            target = target[4:]
        if target in {"computer", "terminal", "pc"}:
            if len(terminals) != 1:
                return "Which computer? " + ", ".join(_name(obj) for obj in terminals)
            obj = terminals[0]
        else:
            obj, ambiguity = _find(terminals, query)
            if ambiguity:
                return ambiguity
            if obj is None:
                return f"No computer named '{query}' is here."
        self._computer_request = obj
        return f"You switch on {_name(obj)}. The KleinOS desktop appears."

    def _pet(self, query: str) -> str:
        """Pet an animal in the room (currently: cat)."""
        room = self._room()
        if room is None:
            return self.look()
        cats = [obj for obj in room.get("objects", [])
                if not obj.get("hidden", False) and
                str(obj.get("kind", "")).casefold() == "cat"]
        if not cats:
            return "There's nothing here worth petting."
        bucket = _CAT_PURRS if random.random() < 0.5 else _CAT_MEOWS
        return random.choice(bucket)

    def room_snapshot(self) -> RoomSnapshot:
        room = self._room()
        if room is None:
            return RoomSnapshot(
                room_id=None, room_name="No Room", area="", description="",
                environment=(), objects=(), actors=(), exits=(),
                has_terminal=False, has_cat=False, has_ringing_phone=False,
            )
        visible_objects = [o for o in room.get("objects", []) if not o.get("hidden", False)]
        visible_actors  = [a for a in room.get("actors", [])  if not a.get("hidden", False)]
        env = tuple(
            (k.capitalize(), str(v))
            for k, v in room.get("environment", {}).items() if v
        )
        objects = tuple(ObjectInfo(
            id=str(o.get("id", "")),
            name=_name(o),
            short_desc=str(o.get("short_desc") or ""),
            kind=str(o.get("kind", "")),
        ) for o in visible_objects)
        actors = tuple(ActorInfo(
            id=str(a.get("id", "")),
            name=_name(a),
            short_desc=str(a.get("short_desc") or a.get("description") or ""),
        ) for a in visible_actors)
        kinds = {o.kind.casefold() for o in objects}
        has_ringing = any(
            str(o.get("kind", "")).casefold() == "telephone" and o.get("ringing")
            for o in visible_objects
        )
        return RoomSnapshot(
            room_id=self.room_id,
            room_name=room["name"],
            area=room.get("area", ""),
            description=room.get("description", ""),
            environment=env,
            objects=objects,
            actors=actors,
            exits=tuple(room.get("exits", {}).keys()),
            has_terminal="terminal" in kinds,
            has_cat="cat" in kinds,
            has_ringing_phone=has_ringing,
        )

    def consume_computer_request(self) -> dict | None:
        """Return one pending UI action, at most once."""
        obj = self._computer_request
        self._computer_request = None
        return obj

    def execute(self, raw: str) -> str:
        self._computer_request = None
        command = raw.strip()
        if not command:
            return "Enter a command, or type 'help'."
        verb, _, arg = command.partition(" ")
        verb, arg = verb.casefold(), arg.strip()
        room = self._room()
        if command.casefold() in {"hang up", "hangup"}:
            return self.hang_up()
        if self.on_phone:
            return "You're on the telephone. Say something or 'hang up'."
        if verb == "answer":
            return self.answer_phone(arg)
        if verb == "use":
            return self.use_computer(arg) if arg else "Use what?"
        if verb == "pet":
            return self._pet(arg)
        if command.casefold() in {"pick up phone", "pick up telephone", "pick up receiver"}:
            return self.answer_phone()
        if verb in {"help", "?"}:
            return ("Commands:\n"
                    "  look (l) — describe current room\n"
                    "  inspect <object> (x, examine, look at)\n"
                    "  go <exit> — travel; exit names also work alone\n"
                    "  enter <exit/room>, leave — travel through named exits\n"
                    "  take <item> (get, pick up)\n"
                    "  drop <item>\n"
                    "  inventory (i, inv)\n"
                    "  answer phone — local Ollama conversation\n"
                    "  hang up — end telephone call\n"
                    "  use computer — operate a terminal in this room\n"
                    "  help (?)\n"
                    "  Reload World — restart from the builder's saved JSON")
        if verb in {"l", "look"} and not arg:
            return self.look()
        if verb in {"i", "inv", "inventory"}:
            return self.inventory_text()
        if command.casefold().startswith("look at "):
            return self.inspect(command[8:].strip())
        if command.casefold().startswith("pick up "):
            return self.take(command[8:].strip())
        if verb in {"inspect", "examine", "x"} or (verb == "look" and arg):
            return self.inspect(arg) if arg else "Inspect what?"
        if verb in {"take", "get"}:
            return self.take(arg) if arg else "Take what?"
        if verb == "drop":
            return self.drop(arg) if arg else "Drop what?"
        if verb in {"go", "move", "walk", "enter"}:
            return self.move(arg) if arg else "Go where?"
        if verb == "leave":
            if room and "outside" in room["exits"]:
                return self.move("outside")
            if room and "out" in room["exits"]:
                return self.move("out")
            return "There's no obvious way to leave by that command. Try 'go <exit>'."
        if room and any(key.casefold() == command.casefold() for key in room["exits"]):
            return self.move(command)
        return f"Unknown command: {command}. Type 'help' for commands."
