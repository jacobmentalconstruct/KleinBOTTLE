# KleinBOTTLE

You are sitting at a desk. The monitor glows a steady green.  
Interact with the computer and it opens — a world inside itself.

---

## Run

```bat
setup_env.bat        # first time only — creates .venv, installs Pillow
run.bat              # start the game
```

Linux / macOS:

```sh
./setup_env.sh
./run.sh
```

Or directly: `python -m kleinos`

---

## What it is

KleinBOTTLE opens on a **title screen**, then drops you into a **text adventure** starting in a home office. Explore the house, yard, and looping woods. Interact with the PC on the desk to open **KleinOS** — a retro desktop that contains its own games and tools, including a text adventure of the same world.

### The house

Ten rooms connected in a loop:  
Hall → Living Room, Kitchen, Bedroom (en-suite Bathroom), Office  
Front door → Front Yard → Front Woods → Back Woods → Back Yard → Kitchen back door  
Both woodland paths loop — leaving one gate brings you back through the other.

### KleinOS PC

Opened by interacting with the computer in the office. Contains:

| Section | Items |
|---------|-------|
| Apps | World Builder, Ollama Chat, Notes |
| Games | MAHisLAND (survival), The Shack, KleinBOTTLE (text adventure), Space Invaders |

### MAHisLAND

Arcade survival game on a pixel island. Hotbar: **1** Fist (swing), **2** Hammer (place blueprint), **3** eat food. **R** opens the build menu, **RMB** interacts/opens. Gates toggle open on RMB. ESC → confirm exit with save. Scoring, high score, resume on restart.

---

## Room images

Each room gets a generated **320×240 retro pixel art background** (Sierra/LucasArts style), displayed in green phosphor monochrome above the transcript. Images are generated on first visit and cached to `data/rooms/<room_id>.png`.

**Requirements:** ComfyUI running at `http://127.0.0.1:8188` (Stability Matrix → Launch ComfyUI).

Pre-generate all rooms at once:

```bat
python scripts\gen_room_images.py
```

Pass `--regen` to overwrite existing images. The in-game **↺ regen** button regenerates the current room.

---

## World JSON

The world is defined in `data/world.json`. Edit it in the World Builder (inside KleinOS) or directly. Each room has `id`, `name`, `area`, `description`, `exits`, `objects`, `actors`. An object with `"kind": "terminal"` triggers the PC interaction hook.

---

## Telephone / Ollama (optional)

Install Ollama and run `ollama pull qwen2.5:3b`. Add an object with `"kind": "telephone"` to any room via the World Builder. In Play, type `answer phone` to call it.

---

## Architecture

```
kleinos/              KleinBOTTLE entry point and UI
  __main__.py         title screen → text adventure → KleinPC hook
  kb_surfaces.py      KleinAdventurePane (room image banner + GameSurface)
  room_panel.py       full-width room image panel, pipeline integration
  mahisland.py        MAHisLAND arcade survival game
  klein_pc.py         KleinOS desktop window
  ...

src/                  text adventure engine (world builder + game session)
  surfaces/game.py    transcript UI, command input
  surfaces/builder.py world editor UI
  game.py             parser, session state
  world_model.py      world JSON contract and validation

data/
  world.json          KleinBOTTLE house world
  splash.png          title screen art
  rooms/              cached room background images (generated)

scripts/
  gen_room_images.py  batch generate all room backgrounds
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `pillow` | Room images and splash screen (green phosphor tint) |
| `tkinter` | UI (stdlib) |
| ComfyUI | Local image generation (optional — game runs without it) |
| Ollama | Telephone NPC (optional) |
