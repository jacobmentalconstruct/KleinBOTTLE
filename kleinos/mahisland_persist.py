"""
kleinos/mahisland_persist.py

MAHisLAND persistence mixin — save/load game state and high score.
"""

from __future__ import annotations

import json
import sys

from kleinos.mahisland_world import _SAVE_PATH


class _PersistMixin:

    def _save_game(self) -> None:
        data = {
            "high_score": max(self._high_score, self._score),
            "game": {
                "grid":       self._grid,
                "nodes":      self._nodes,
                "px": self._px, "py": self._py,
                "angle":      self._angle,
                "hp":         self._hp,
                "hunger":     self._hunger,
                "inv":        self._inv,
                "gear":       list(self._gear),
                "structs":    self._structs,
                "score":      self._score,
                "spawn_acc":  self._spawn_acc,
                "fuel_acc":   self._fuel_acc,
                "hunger_acc": self._hunger_acc,
            }
        }
        try:
            _SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _SAVE_PATH.write_text(json.dumps(data))
        except Exception as exc:
            print(f"[mahisland] _save_game failed: {exc}", file=sys.stderr)

    def _load_game(self) -> None:
        try:
            data = json.loads(_SAVE_PATH.read_text())
            self._reset_world()     # seed all fields; state → "play"
            g = data["game"]
            self._grid        = g["grid"]
            self._nodes       = g["nodes"]
            self._px          = g["px"]
            self._py          = g["py"]
            self._angle       = g["angle"]
            self._hp          = g["hp"]
            self._hunger      = g["hunger"]
            self._inv         = g["inv"]
            self._gear        = set(g["gear"])
            self._structs     = g["structs"]
            self._score       = g.get("score", 0)
            self._spawn_acc   = g.get("spawn_acc", 0.0)
            self._fuel_acc    = g.get("fuel_acc", 0.0)
            self._hunger_acc  = g.get("hunger_acc", 0.0)
            self._high_score  = data.get("high_score", self._high_score)
            self._camx = self._px - self._vw / 2
            self._camy = self._py - self._vh / 2
        except Exception:  # MEDIUM: corrupt save → reset world (intentional recovery, no log)
            self._reset_world()

    def _load_high_score(self) -> int:
        try:
            return json.loads(_SAVE_PATH.read_text()).get("high_score", 0)
        except Exception:  # SAFE: file absent on first run
            return 0

    def _update_high_score(self) -> None:
        if self._score > self._high_score:
            self._high_score = self._score

    def _clear_save(self) -> None:
        try:
            if _SAVE_PATH.exists():
                _SAVE_PATH.unlink()
        except Exception:  # SAFE: file may already be gone (concurrent delete)
            pass
