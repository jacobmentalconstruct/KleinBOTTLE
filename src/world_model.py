"""World JSON contract: ordinary editable data, independent of any UI."""
from __future__ import annotations

from copy import deepcopy
import json
import re

VERSION = 1
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class WorldValidationError(ValueError):
    pass


def blank_world() -> dict:
    return {"version": VERSION, "name": "Untitled World", "start_room": None, "rooms": []}


def normalize_room(value: object) -> dict:
    if not isinstance(value, dict):
        raise WorldValidationError("A room must be a JSON object")
    room = deepcopy(value)
    room_id = room.get("id")
    if not isinstance(room_id, str) or not ID_PATTERN.fullmatch(room_id):
        raise WorldValidationError("Room id is required (letters, digits, dots, underscores, hyphens)")
    name = room.get("name")
    if not isinstance(name, str) or not name.strip():
        raise WorldValidationError(f"Room '{room_id}' needs a name")
    for key, default in (("area", "Ungrouped"), ("description", "")):
        room.setdefault(key, default)
        if not isinstance(room[key], str):
            raise WorldValidationError(f"Room '{room_id}': {key} must be text")
    room["name"] = name.strip()
    room["area"] = room["area"].strip() or "Ungrouped"
    for key in ("exits", "environment"):
        room.setdefault(key, {})
        if not isinstance(room[key], dict):
            raise WorldValidationError(f"Room '{room_id}': {key} must be an object")
    for direction, target in room["exits"].items():
        if not isinstance(direction, str) or not direction.strip() or not isinstance(target, str) or not target.strip():
            raise WorldValidationError(f"Room '{room_id}': exits must map directions to room IDs")
    for key in ("objects", "actors", "secrets"):
        room.setdefault(key, [])
        if not isinstance(room[key], list) or not all(isinstance(item, dict) for item in room[key]):
            raise WorldValidationError(f"Room '{room_id}': {key} must be an array of objects")
    return room


def parse_rooms(payload: object) -> tuple[list[dict], dict | None]:
    """Accept a room, room list, {rooms:[...]}, or a complete world document."""
    source = payload
    world_meta = None
    if isinstance(payload, dict) and "rooms" in payload:
        source = payload["rooms"]
        world_meta = {k: deepcopy(v) for k, v in payload.items() if k != "rooms"}
    elif isinstance(payload, dict) and "id" in payload:
        source = [payload]
    if isinstance(source, dict):
        source = [{**item, "id": item.get("id", key)} if isinstance(item, dict) else item
                  for key, item in source.items()]
    if not isinstance(source, list):
        raise WorldValidationError("Expected one room, a list of rooms, or an object with 'rooms'")
    rooms = [normalize_room(room) for room in source]
    ids = [room["id"] for room in rooms]
    if len(ids) != len(set(ids)):
        raise WorldValidationError("Duplicate room IDs in imported data")
    return rooms, world_meta


def normalize_world(payload: object) -> dict:
    if not isinstance(payload, dict) or "rooms" not in payload:
        raise WorldValidationError("World file must contain 'rooms'")
    rooms, meta = parse_rooms(payload)
    assert meta is not None
    if meta.get("version", VERSION) != VERSION:
        raise WorldValidationError(f"Unsupported world version (expected {VERSION})")
    name = meta.get("name", "Untitled World")
    if not isinstance(name, str) or not name.strip():
        raise WorldValidationError("World name must be nonempty text")
    start = meta.get("start_room")
    if start is not None and start not in {room["id"] for room in rooms}:
        raise WorldValidationError("start_room must reference an existing room")
    return {**meta, "version": VERSION, "name": name.strip(), "start_room": start, "rooms": rooms}


def exit_warnings(world: dict) -> list[str]:
    ids = {room["id"] for room in world["rooms"]}
    return [f"{room['id']}: {direction} points to missing room '{target}'"
            for room in world["rooms"] for direction, target in room["exits"].items()
            if target not in ids]


def pretty(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"
