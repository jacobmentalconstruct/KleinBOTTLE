"""
kleinos/adventure.py

Standalone text-adventure engine for KleinOS.

World format: data/worlds/<name>.json  (schema: kleinos-adventure-v1)
See data/worlds/shack.json for the reference world and full schema docs.

TheShack — the built-in demo world, registered as a KleinGame.
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

from kleinos.klein_app import KleinGame

_WORLDS_DIR = Path(__file__).resolve().parent.parent / "data" / "worlds"


# ── Direction aliases ────────────────────────────────────────────────

_DIR_ALIASES: dict[str, str] = {
    "n": "north", "s": "south", "e": "east", "w": "west",
    "u": "up",    "d": "down",
}


# ── Adventure engine ─────────────────────────────────────────────────

class AdventureEngine:
    """
    Interprets a kleinos-adventure-v1 world dict.

    Call start() once to get the opening room description, then feed
    each player command to process() which returns the response string.
    process() returns the sentinel "__QUIT__" when the player quits.

    World schema quick-ref
    ----------------------
    Room keys:
        id, name, description        — required
        dark: bool                   — requires oil_lantern in inventory to describe
        exits: {direction: room_id}  — static exits
        items: [item_id, ...]        — items placed here at game start
        first_visit: str             — extra text shown only on first entry
        unlock_exit:                 — special: using an item opens a new exit
            item, direction, destination, message, repeat

    Item keys:
        id, name, description        — required
        takeable: bool               — default true
        use_message: str             — shown when player 'use's this item
        key: item_id                 — this item unlocks the named container
        open_description: str        — replaces description after container is opened
        unlock_message: str          — shown when this container is first unlocked
    """

    def __init__(self, world: dict) -> None:
        self._rooms   = {r["id"]: r for r in world["rooms"]}
        self._items   = {i["id"]: i for i in world["items"]}
        self._loc     = world["start_room"]
        self._inv:    list[str] = []
        self._visited: set[str] = set()
        self._opened:  set[str] = set()          # containers that have been unlocked
        self._unlocked_exits: dict[str, dict[str, str]] = {}   # {room_id: {dir: dest}}
        # Mutable per-room item lists (items move as player takes/drops them)
        self._room_items: dict[str, list[str]] = {
            r["id"]: list(r.get("items", [])) for r in world["rooms"]
        }

    # ── Public interface ──────────────────────────────────────────────

    def start(self) -> str:
        """Mark start room visited and return its description."""
        first = self._loc not in self._visited
        self._visited.add(self._loc)
        return self._describe(first_visit=first)

    def process(self, raw: str) -> str:
        words = raw.strip().lower().split()
        if not words:
            return ""
        verb = words[0]
        rest = " ".join(words[1:])

        # Bare direction
        if verb in _DIR_ALIASES:
            return self._go(_DIR_ALIASES[verb])
        if verb in _DIR_ALIASES.values():
            return self._go(verb)

        if verb in ("go", "move", "walk"):
            return self._go(rest)
        if verb == "look" and rest.startswith("at "):
            return self._examine(rest[3:].strip())
        if verb in ("look", "l"):
            return self._describe()
        if verb in ("examine", "x", "inspect"):
            return self._examine(rest)
        if verb == "pick":
            # "pick up X"
            return self._take(rest.removeprefix("up").strip() if rest.startswith("up") else rest)
        if verb in ("take", "get"):
            return self._take(rest)
        if verb in ("drop", "leave"):
            return self._drop(rest)
        if verb in ("inventory", "inv", "i"):
            return self._inventory_cmd()
        if verb == "use":
            return self._use(rest)
        if verb in ("help", "?", "h"):
            return _HELP
        if verb in ("quit", "exit", "q"):
            return "__QUIT__"

        return f"I don't know how to '{raw.strip()}'."

    # ── Room description ──────────────────────────────────────────────

    def _exits(self, room_id: str) -> dict[str, str]:
        exits = dict(self._rooms[room_id].get("exits", {}))
        exits.update(self._unlocked_exits.get(room_id, {}))
        return exits

    def _is_dark(self) -> bool:
        return (self._rooms[self._loc].get("dark", False)
                and "oil_lantern" not in self._inv)

    def _describe(self, first_visit: bool = False) -> str:
        if self._is_dark():
            return "\n[Darkness]\nIt is pitch dark. You can't see a thing.\n(You need a light source.)"
        room  = self._rooms[self._loc]
        lines = [f"\n[{room['name']}]", room["description"]]
        if first_visit and "first_visit" in room:
            lines.append(room["first_visit"])
        # Items on the floor
        here = [self._items[i]["name"]
                for i in self._room_items[self._loc] if i in self._items]
        if here:
            lines.append("You see: " + ", ".join(here) + ".")
        # Exits
        ex = self._exits(self._loc)
        if ex:
            lines.append("Exits: " + ", ".join(ex) + ".")
        return "\n".join(lines)

    # ── Commands ──────────────────────────────────────────────────────

    def _go(self, direction: str) -> str:
        if not direction:
            return "Go where?"
        exits = self._exits(self._loc)
        if direction not in exits:
            avail = ", ".join(exits) if exits else "none"
            return f"You can't go {direction} from here.  (Available: {avail})"
        dest = exits[direction]
        self._loc = dest
        first = dest not in self._visited
        self._visited.add(dest)
        return self._describe(first_visit=first)

    def _examine(self, target: str) -> str:
        if not target or target in ("room", "here", "around", "surroundings"):
            if self._is_dark():
                return "You can't see a thing."
            return self._rooms[self._loc]["description"]
        iid = self._find(target)
        if not iid:
            return f"You don't see any {target} here."
        item = self._items[iid]
        if iid in self._opened and "open_description" in item:
            return item["open_description"]
        return item["description"]

    def _take(self, target: str) -> str:
        if not target:
            return "Take what?"
        iid = self._find(target, where="room")
        if not iid:
            return f"There's no {target} here to take."
        item = self._items[iid]
        if not item.get("takeable", True):
            return f"The {item['name']} isn't something you can carry."
        self._room_items[self._loc].remove(iid)
        self._inv.append(iid)
        return f"You take the {item['name']}."

    def _drop(self, target: str) -> str:
        if not target:
            return "Drop what?"
        iid = self._find(target, where="inv")
        if not iid:
            return f"You're not carrying any {target}."
        self._inv.remove(iid)
        self._room_items[self._loc].append(iid)
        return f"You set down the {self._items[iid]['name']}."

    def _inventory_cmd(self) -> str:
        if not self._inv:
            return "You are empty-handed."
        names = [self._items[i]["name"] for i in self._inv if i in self._items]
        return "Carrying: " + ", ".join(names) + "."

    def _use(self, target: str) -> str:
        # Strip optional "on <X>" — only the item name matters for lookup
        name = target.split(" on ")[0].strip() if " on " in target else target
        if not name:
            return "Use what?"

        iid = self._find(name, where="inv")
        if not iid:
            return f"You're not carrying any {name}."

        item = self._items[iid]
        room = self._rooms[self._loc]

        # Room unlock_exit
        unlock = room.get("unlock_exit")
        if unlock and unlock.get("item") == iid:
            direction = unlock["direction"]
            already   = self._unlocked_exits.get(self._loc, {}).get(direction)
            if already:
                return unlock.get("repeat", "Nothing more to do here.")
            self._unlocked_exits.setdefault(self._loc, {})[direction] = unlock["destination"]
            msg = unlock["message"]
            exits = self._exits(self._loc)
            return f"{msg}\n\nExits now: {', '.join(exits)}."

        # Generic use_message (e.g. lighting a lantern)
        if "use_message" in item:
            return item["use_message"]

        # Key — look for a matching locked container in this room
        for rid in self._room_items[self._loc]:
            if rid not in self._items:
                continue
            target_item = self._items[rid]
            if target_item.get("key") == iid:
                if rid in self._opened:
                    return f"The {target_item['name']} is already open."
                self._opened.add(rid)
                return target_item.get("unlock_message",
                                       f"You unlock the {target_item['name']}.")

        return f"Nothing happens when you use the {item['name']} here."

    # ── Item lookup ───────────────────────────────────────────────────

    def _find(self, name: str, where: str = "both") -> Optional[str]:
        """Return item id whose name contains `name`, or None.
        where: 'inv' | 'room' | 'both'
        """
        pool: list[str] = []
        if where in ("inv", "both"):
            pool += self._inv
        if where in ("room", "both"):
            pool += self._room_items[self._loc]
        name_lc = name.lower()
        for iid in pool:
            if iid not in self._items:
                continue
            if name_lc in self._items[iid]["name"] or name_lc == iid:
                return iid
        return None


_HELP = """\
Commands:
  look  (l)             — describe current room
  go <direction>        — move  |  or just: north / n, south / s, up, down, in, out
  examine <thing>  (x)  — look closely at something
  take <item>           — pick something up
  drop <item>           — put something down
  inventory  (i)        — what you're carrying
  use <item>            — use an item (context-sensitive)
  quit  (q)             — return to KleinOS"""


# ── TheShack — built-in demo world ───────────────────────────────────

class TheShack(KleinGame):
    title       = "The Shack"
    description = "An abandoned shack in the woods. Something is hidden beneath it."

    def create(self, parent: tk.Widget, on_exit: Callable[[], None]) -> tk.Widget:
        from kleinos.terminal_pane import TerminalPane

        world_path = _WORLDS_DIR / "shack.json"
        try:
            world = json.loads(world_path.read_text(encoding="utf-8"))
        except Exception as exc:
            frame = tk.Frame(parent, bg="#010a01")
            tk.Label(
                frame, text=f"Could not load world:\n{exc}",
                bg="#010a01", fg="#00dd33", font=("Consolas", 9),
                justify="left", wraplength=400,
            ).pack(padx=16, pady=16, anchor="nw")
            return frame

        engine = AdventureEngine(world)
        intro  = world.get("intro", "")
        started = [False]

        def executor(cmd: str) -> str:
            if not started[0]:
                started[0] = True
                opening = engine.start()
                return (intro + "\n\n" + opening) if intro else opening
            result = engine.process(cmd)
            if result == "__QUIT__":
                parent.after(0, on_exit)
                return "Returning to KleinOS..."
            return result

        pane = TerminalPane(parent, executor=executor, prompt="> ", header="")

        _TITLE = (
            "\n"
            "  ╔══════════════════════════════════════╗\n"
            "  ║            T H E   S H A C K         ║\n"
            "  ║   An abandoned shack in the woods.   ║\n"
            "  ║   Something is hidden beneath it.    ║\n"
            "  ╚══════════════════════════════════════╝\n"
            "\n"
        )

        def _auto_start() -> None:
            pane.write(_TITLE)
            opening = executor("")
            pane.write(opening + "\n")

        pane.after(80, _auto_start)
        return pane
