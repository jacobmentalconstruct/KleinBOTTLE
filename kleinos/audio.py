"""
kleinos/audio.py

Retro beep audio via winsound (Windows).  No-op on other platforms.
All calls are non-blocking — each beep runs on a daemon thread.
"""

from __future__ import annotations

import sys
import threading

_enabled = True
_sounds: dict[str, bool] = {
    "shoot":      True,
    "hit":        True,
    "explosion":  True,
    "player_hit": True,
    "death":      True,
    "tick":       True,
}


def configure(cfg: dict) -> None:
    """Apply the 'audio' section of kleinos_config at startup."""
    global _enabled
    audio = cfg.get("audio", {})
    _enabled = bool(audio.get("enabled", True))
    sounds = audio.get("sounds", {})
    for k in _sounds:
        _sounds[k] = bool(sounds.get(k, True))


def _beep(freq: int, ms: int) -> None:
    if sys.platform != "win32":
        return
    try:
        import winsound
        winsound.Beep(max(37, min(32767, freq)), max(1, ms))
    except Exception:  # SAFE: winsound.Beep can fail (device busy, driver issue)
        pass


def _play(name: str, freq: int, ms: int) -> None:
    if not _enabled or not _sounds.get(name, True):
        return
    threading.Thread(target=_beep, args=(freq, ms), daemon=True).start()


# ── Sound effects ────────────────────────────────────────────────────

def shoot() -> None:
    _play("shoot", 800, 40)

def hit() -> None:
    _play("hit", 440, 60)

def explosion() -> None:
    _play("explosion", 220, 120)

def player_hit() -> None:
    _play("player_hit", 180, 200)

def death() -> None:
    _play("death", 150, 350)

def tick(alive_count: int) -> None:
    # Pitch climbs as fewer invaders remain — classic rising urgency
    freq = 160 + (40 - min(40, alive_count)) * 3
    _play("tick", freq, 25)


# ── Live control (called from Settings pane) ─────────────────────────

def set_enabled(val: bool) -> None:
    global _enabled
    _enabled = val

def set_sound(name: str, val: bool) -> None:
    _sounds[name] = val

def get_config() -> dict:
    return {"enabled": _enabled, "sounds": dict(_sounds)}
