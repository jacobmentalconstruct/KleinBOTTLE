"""
scripts/gen_room_images.py

Pre-generate room background images for all rooms in data/world.json.
Run this once after starting ComfyUI (Stability Matrix → Launch ComfyUI).

    python scripts/gen_room_images.py

Images are saved to data/rooms/<room_id>.png and displayed with a green
phosphor tint inside the KleinBOTTLE text adventure.

Pass --regen to overwrite any existing images.
"""

import argparse
import json
import sys
import uuid
from pathlib import Path

_KB_ROOT = Path(__file__).resolve().parent.parent
_PIPELINE_ROOT = Path(r"C:\Jacob\Apps & Tools\image-generation-pipeline")
_ROOMS_DIR = _KB_ROOT / "data" / "rooms"
_WORLD_FILE = _KB_ROOT / "data" / "world.json"

sys.path.insert(0, str(_PIPELINE_ROOT))

from pipeline.client import collect_images, queue_prompt, wait_for_completion  # type: ignore[import]
from pipeline.styles import build_workflow  # type: ignore[import]


def _prompt(room: dict) -> str:
    name = room["name"]
    desc = room["description"].split(".")[0].strip()
    area = room.get("area", "")
    scene_type = "exterior" if area.lower() in ("outside",) else "interior"
    return (
        f"R3TR0, {name}, {desc}, "
        f"point and click adventure game background, {scene_type}, Sierra style"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--regen", action="store_true",
                        help="Overwrite existing images")
    args = parser.parse_args()

    world = json.loads(_WORLD_FILE.read_text(encoding="utf-8"))
    rooms = world["rooms"]
    _ROOMS_DIR.mkdir(parents=True, exist_ok=True)

    for room in rooms:
        rid = room["id"]
        dest = _ROOMS_DIR / f"{rid}.png"

        if dest.exists() and not args.regen:
            print(f"[skip]  {rid}  (exists)")
            continue

        print(f"[gen]   {rid}: {room['name']} ...", end=" ", flush=True)
        try:
            prompt = _prompt(room)
            workflow, _ = build_workflow(prompt, "default")
            pid = queue_prompt(workflow, str(uuid.uuid4()))
            result = wait_for_completion(pid, timeout=300.0)

            tmp_dir = _ROOMS_DIR / "_tmp"
            tmp_dir.mkdir(exist_ok=True)
            saved = collect_images(result, tmp_dir)
            if saved:
                import shutil
                shutil.move(str(saved[0]), str(dest))
                print("ok")
            else:
                print("FAILED (no image returned)")
        except Exception as exc:
            print(f"ERROR: {exc}")

    print("Done.")


if __name__ == "__main__":
    main()
