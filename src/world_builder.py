"""World-builder use cases, independent from the editor widgets."""
from __future__ import annotations

from copy import deepcopy
import json

from .world_model import (
    WorldValidationError, exit_warnings, normalize_room, normalize_world, parse_rooms, pretty
)
from .world_store import WorldStore


class WorldBuilder:
    def __init__(self, store: WorldStore):
        self.store = store
        self.world = store.load()

    def rooms(self) -> list[dict]:
        return deepcopy(self.world["rooms"])

    def room(self, room_id: str) -> dict:
        for room in self.world["rooms"]:
            if room["id"] == room_id:
                return deepcopy(room)
        raise WorldValidationError(f"Room not found: {room_id}")

    def save_room(self, raw: dict, original_id: str | None = None) -> None:
        room = normalize_room(raw)
        room_id = room["id"]
        if original_id is not None and room_id != original_id:
            raise WorldValidationError("Room IDs cannot be renamed in this version")
        existing = {item["id"]: i for i, item in enumerate(self.world["rooms"])}
        if original_id is None and room_id in existing:
            raise WorldValidationError(f"Room ID already exists: {room_id}")
        draft = deepcopy(self.world)
        if room_id in existing:
            draft["rooms"][existing[room_id]] = room
        else:
            draft["rooms"].append(room)
        if draft["start_room"] is None:
            draft["start_room"] = room_id
        self._commit(draft)

    def delete_room(self, room_id: str) -> None:
        self.room(room_id)
        refs = [(r["id"], direction) for r in self.world["rooms"] if r["id"] != room_id
                for direction, target in r["exits"].items() if target == room_id]
        if refs:
            raise WorldValidationError(f"Remove exits pointing to '{room_id}' first: {refs}")
        draft = deepcopy(self.world)
        draft["rooms"] = [r for r in draft["rooms"] if r["id"] != room_id]
        if draft["start_room"] == room_id:
            draft["start_room"] = draft["rooms"][0]["id"] if draft["rooms"] else None
        self._commit(draft)

    def settings(self, name: str, start_room: str | None) -> None:
        draft = deepcopy(self.world)
        draft["name"] = name
        draft["start_room"] = start_room or None
        self._commit(draft)

    def import_json(self, source_text: str, mode: str = "add") -> tuple[int, int]:
        if mode not in ("add", "update", "replace"):
            raise ValueError("mode must be add, update or replace")
        try:
            payload = json.loads(source_text)
        except json.JSONDecodeError as exc:
            raise WorldValidationError(f"Invalid JSON: {exc}") from exc
        incoming, metadata = parse_rooms(payload)
        draft = deepcopy(self.world)
        if mode == "replace":
            draft["rooms"] = incoming
            if metadata is not None:
                draft.update(metadata)
            draft["start_room"] = (
                draft["start_room"] if draft.get("start_room") in {r["id"] for r in incoming}
                else (incoming[0]["id"] if incoming else None)
            )
            added, skipped = len(incoming), 0
        else:
            existing = {r["id"]: i for i, r in enumerate(draft["rooms"])}
            added, skipped = 0, 0
            for room in incoming:
                idx = existing.get(room["id"])
                if idx is not None and mode == "add":
                    skipped += 1
                    continue
                if idx is not None:
                    draft["rooms"][idx] = room
                else:
                    existing[room["id"]] = len(draft["rooms"])
                    draft["rooms"].append(room)
                added += 1
            if draft["start_room"] is None and draft["rooms"]:
                draft["start_room"] = draft["rooms"][0]["id"]
        if added > 0 or mode == "replace":
            self._commit(draft)
        return added, skipped

    def warnings(self) -> list[str]:
        return exit_warnings(self.world)

    def export_json(self) -> str:
        return pretty(self.world)

    def _commit(self, draft: dict) -> None:
        clean = normalize_world(draft)
        self.store.save(clean)
        self.world = clean
