"""
kleinos/world_library.py

World-file management for the KleinBOTTLE builder workflow.

Paths:
  data/world.json       — Main (active world, read by the game)
  data/world_wip.json   — WIP (what WorldBuilder edits; never the Main)
  data/world_library/   — named JSON snapshots

Public API:
  ensure_wip()              copy Main → WIP if WIP is missing
  save_snapshot(name, src)  save a world file as a named library entry
  list_library()            [{name, path, mtime}] newest-first
  validate_for_promotion()  raises WorldLibraryError with reason on failure
  promote_to_main(path)     validate + backup old Main + atomic replace
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

_KB_ROOT = Path(__file__).resolve().parent.parent
if str(_KB_ROOT) not in sys.path:
    sys.path.insert(0, str(_KB_ROOT))

_DATA = _KB_ROOT / "data"

MAIN_WORLD  = _DATA / "world.json"
WIP_WORLD   = _DATA / "world_wip.json"
LIBRARY_DIR = _DATA / "world_library"


class WorldLibraryError(ValueError):
    pass


# ── Task 1: WIP isolation ─────────────────────────────────────────────

def ensure_wip() -> None:
    """Copy Main → WIP if WIP does not exist yet."""
    if not WIP_WORLD.exists() and MAIN_WORLD.exists():
        shutil.copy2(MAIN_WORLD, WIP_WORLD)


# ── Library snapshots ─────────────────────────────────────────────────

def save_snapshot(name: str, source: Path = WIP_WORLD) -> Path:
    """Save source world file as a timestamped snapshot. Returns the new path."""
    if not source.exists():
        raise WorldLibraryError(f"Source world not found: {source}")
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w\- ]", "", name).strip().replace(" ", "_") or "snapshot"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = LIBRARY_DIR / f"{safe}_{ts}.json"
    shutil.copy2(source, dest)
    try:
        data = json.loads(dest.read_text(encoding="utf-8"))
        data["name"] = name.strip() or safe
        dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except (json.JSONDecodeError, OSError, KeyError) as exc:
        print(f"[world_library] save_snapshot: could not update name in {dest.name}: {exc}",
              file=sys.stderr)
    return dest


def list_library() -> list[dict]:
    """Return [{name, path, mtime}] for all valid library snapshots, newest first."""
    if not LIBRARY_DIR.exists():
        return []
    entries = []
    for p in LIBRARY_DIR.glob("*.json"):
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            entries.append({
                "name": raw.get("name", p.stem),
                "path": p,
                "mtime": p.stat().st_mtime,
            })
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[world_library] list_library: skipping {p.name}: {exc}", file=sys.stderr)
    return sorted(entries, key=lambda e: e["mtime"], reverse=True)


# ── Task 3: Promotion validation ──────────────────────────────────────

def _has_reachable_terminal(world: dict) -> bool:
    """BFS from start_room; return True if any reachable room has kind=terminal."""
    rooms = {r["id"]: r for r in world["rooms"]}
    start = world.get("start_room")
    if not start or start not in rooms:
        return False
    visited: set[str] = set()
    queue = [start]
    while queue:
        rid = queue.pop()
        if rid in visited:
            continue
        visited.add(rid)
        room = rooms[rid]
        objects = room.get("objects", [])
        if any(str(obj.get("kind", "")).casefold() == "terminal" for obj in objects):
            return True
        for target in room.get("exits", {}).values():
            if target not in visited and target in rooms:
                queue.append(target)
    return False


def validate_for_promotion(world: dict) -> None:
    """Raise WorldLibraryError with a user-readable reason if world cannot be promoted."""
    from src.world_model import exit_warnings  # noqa: PLC0415

    if not world.get("start_room"):
        raise WorldLibraryError(
            "World has no start room set.\n"
            "Set one in Builder → World Settings before promoting."
        )
    warns = exit_warnings(world)
    if warns:
        sample = "\n".join(warns[:5])
        more = f"\n… and {len(warns) - 5} more" if len(warns) > 5 else ""
        raise WorldLibraryError(f"Unresolved exits:\n{sample}{more}")
    if not _has_reachable_terminal(world):
        raise WorldLibraryError(
            "No terminal (kind=terminal) is reachable from the start room.\n"
            "The KleinBOTTLE PC must be reachable from the starting room."
        )


def promote_to_main(source: Path) -> None:
    """Validate source world, snapshot old Main, then atomically replace Main."""
    from src.world_store import WorldStore  # noqa: PLC0415

    store = WorldStore(source)
    world = store.load()          # raises WorldValidationError if JSON is broken
    validate_for_promotion(world)  # raises WorldLibraryError if logic fails

    # Snapshot old Main so it can be recovered
    if MAIN_WORLD.exists():
        try:
            save_snapshot("pre_promotion_backup", source=MAIN_WORLD)
        except Exception:
            pass  # a failed snapshot must not block promotion

    WorldStore(MAIN_WORLD).save(world)
