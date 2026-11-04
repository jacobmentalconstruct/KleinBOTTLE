"""Tiny stateful text-adventure engine. No UI, filesystem writes, or sidecars.

A GameSession loads a snapshot of a world definition. Movement and items alter
only this in-memory play session, never the builder's source JSON.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .world_store import WorldStore


@dataclass(frozen=True)
class GameView:
    world_name: str
    room_id: str | None
    room_name: str
    area: str
    exits: tuple[str, ...]
    inventory: tuple[str, ...]


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
        self.restart()

    def restart(self) -> str:
        """Reload the editor's saved world and begin a fresh play session."""
        self.world = deepcopy(self.store.load())
        self.inventory = []
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
        return f"{_name(obj)}\n{obj.get('description') or 'Nothing unusual stands out.'}"

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

    def execute(self, raw: str) -> str:
        command = raw.strip()
        if not command:
            return "Enter a command, or type 'help'."
        verb, _, arg = command.partition(" ")
        verb, arg = verb.casefold(), arg.strip()
        room = self._room()
        if verb in {"help", "?"}:
            return ("Commands:\n"
                    "  look (l) — describe current room\n"
                    "  inspect <object> (x, examine, look at)\n"
                    "  go <exit> — travel; exit names also work alone\n"
                    "  enter <exit/room>, leave — travel through named exits\n"
                    "  take <item> (get, pick up)\n"
                    "  drop <item>\n"
                    "  inventory (i, inv)\n"
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
