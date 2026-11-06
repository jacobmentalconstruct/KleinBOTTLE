"""
kleinos/config.py

Persistent config for KleinOS — data/kleinos_config.json.
Loaded once at startup; written on any settings change.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "data" / "kleinos_config.json"

_PC_SIZES = {
    "small":  0.65,
    "medium": 1.0,
    "large":  1.3,
}

_DEFAULTS: dict = {
    "palette": "green",
    "pc_size": "medium",
    "audio": {
        "enabled": True,
        "sounds": {
            "shoot":      True,
            "hit":        True,
            "explosion":  True,
            "player_hit": True,
            "death":      True,
            "tick":       True,
        },
    },
}


def _merge(target: dict, defaults: dict) -> None:
    """Recursively add missing keys from defaults into target."""
    for k, v in defaults.items():
        if k not in target:
            target[k] = copy.deepcopy(v)
        elif isinstance(v, dict) and isinstance(target[k], dict):
            _merge(target[k], v)


def load() -> dict:
    try:
        cfg = json.loads(_PATH.read_text(encoding="utf-8"))
        _merge(cfg, _DEFAULTS)
        return cfg
    except FileNotFoundError:
        cfg = copy.deepcopy(_DEFAULTS)
        save(cfg)
        return cfg
    except Exception:
        return copy.deepcopy(_DEFAULTS)


def save(cfg: dict) -> None:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass
