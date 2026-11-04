"""Single-file persistence; no UI or project-sidecar dependencies."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .world_model import blank_world, normalize_world, pretty, WorldValidationError


class WorldStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            return blank_world()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorldValidationError(f"Cannot read {self.path}: {exc}") from exc
        return normalize_world(raw)

    def save(self, world: dict) -> None:
        valid = normalize_world(world)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent,
                                             suffix=".tmp", delete=False) as file:
                tmp = Path(file.name)
                file.write(pretty(valid))
                file.flush()
                os.fsync(file.fileno())
            os.replace(tmp, self.path)
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
