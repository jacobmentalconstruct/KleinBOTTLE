# Adventure — World Builder + Play (v1)

A small, standalone Python text adventure: edit rooms in a **World Builder** tab and explore the same JSON world in a **Play** tab. Standard-library Python and Tkinter only; no development-sidecar, network, model, or third-party package requirements.

## Run

- Windows: double-click `run.bat` (requires Python with the `py` launcher).
- Linux/macOS: `./run.sh` (Linux may need `sudo apt install python3-tk`).
- Or: `python -m src.app` from the project root.

Your editable world definition is stored at `data/world.json`.

**Upgrading an existing installation:** use the separate *upgrade* ZIP and extract its contents into the project root. It contains only source, tests, and README; it **does not contain `data/world.json`** and will not overwrite your world. You can make a backup of your project before upgrading.

## World Builder tab

1. Click **New Room**. Enter a stable `id`, a name, an area, and a description.
2. Define exits one per line, like `north:study` or `inside:wardrobe`.
3. Enter environment values and objects. **Add Object** creates a basic object from a form. **Full Room JSON** exposes additional properties.
4. Click **Save Room**. Changes are written to `data/world.json` immediately. Select a start room and save world settings.
5. Paste generated JSON through **Import / Paste JSON**, or load a `.json` file. To explore the built-in test world, import `examples/rooms.json`.
6. **Export World JSON** saves a copy of the world.

## Play tab

Switch to **Play** to start at the world's configured start room (or its first room if a start room wasn't chosen). The left panel is the command transcript. The right panel contains your location, clickable exits, and carried inventory.

### Commands

| Command | Aliases / notes |
| --- | --- |
| `look` | `l` — describe room, visible objects/actors, environment, exits |
| `inspect <object>` | `x`, `examine`, `look at` — inspect a visible object, actor, or carried item |
| `go <exit>` | `move`, `walk`, or type an exit name like `north` directly |
| `enter <exit or room>` | Move through a connected exit, e.g. `enter wardrobe` |
| `leave` | Follow an `outside` or `out` exit if present |
| `take <item>` | `get`, `pick up` — take a portable object |
| `drop <item>` | Drop carried item in current room |
| `inventory` | `i`, `inv` — see what you're carrying |
| `help` | `?` — list commands |

Example walkthrough after importing `examples/rooms.json`:

1. `look` → Entrance Hall
2. `go north` → Study
3. `inspect wardrobe` → see wardrobe description
4. `enter wardrobe` → Inside Wardrobe
5. `take key` → Iron Key enters inventory
6. `leave` → back to Study, carrying the key

**Reload World / Restart** reads the latest saved `data/world.json` and starts a new session. **Switching back to the Play tab also restarts play**, to make newly saved edits immediately testable. Unsaved changes still sitting in the builder form are not included: click **Save Room** or **Save World Settings** first.

Gameplay state (the player's current room and inventory, plus moved objects) is **in-memory only**. The world builder's JSON is never changed by playing, and there are no saved games yet.

## World JSON contract

Worlds have `version: 1`, `name`, `start_room`, and `rooms` (array). Each room has:

- Required: `id` (stable unique room identifier), `name`
- Common: `area`, `description`, `exits` (`exit-name` → destination room ID), `environment` (object), `objects`/`actors`/`secrets` (arrays of objects)
- Optional extra properties are preserved during editor saves/imports; runtime behavior is implemented only for the subset listed below.

For game objects, use `id`, `name`, `description`, `kind`, and optionally `portable: true/false` or `takeable: true/false`. Only `kind: "item"` is portable by default; other kinds like furniture stay in the room unless explicitly marked portable. An object with `hidden: true` is excluded from ordinary Look, Inspect, and Take. **There is no reveal-secrets command yet.**

Enterable interiors are regular rooms with named exits (`inside:wardrobe`, `outside:study`). The `interior_of` field is retained as metadata; the actual movement always follows an exit. Environment values are displayed as text, not rendered as sound/light/weather effects.

Import accepts an individual room, list of rooms, or a world document containing `rooms` as a list or object keyed by room ID. Options:

- **Add new** — skip already-present IDs.
- **Update matching** — replace matching rooms and add new ones.
- **Replace whole world** — replace rooms and world metadata, after confirmation.

Room IDs cannot be renamed through the form (to protect exit references). Deleting a referenced room is blocked. Unresolved exits generate editor warnings and, in Play, a friendly missing-room message.

## Architecture


## Telephone / local Ollama (optional)

Install Ollama on the same computer and run `ollama pull qwen2.5:3b`.
Ollama must be running at `127.0.0.1:11434`. No cloud service or API key is used.

In the World Builder, open a room, choose **Add Object** or **Edit Object**,
set **Kind** to `telephone`, and set its local **Model**, **System prompt**, and
**Ringing** checkbox. Click **Apply to Room**, then **Save Room**. The model
and persona are stored inside that object's JSON as `ollama.model` and
`ollama.system`. The phone does not depend on either development sidecar.

In Play, type `answer phone` while in the room. A `Hello?` starts the call;
type natural dialogue (or `say hello`) until `hang up`. Each call keeps its
own brief in-memory conversation; no call logs are saved to world JSON.
The interface remains responsive during inference and an Ollama failure
shows an offline message rather than breaking the game.

The example world contains a ringing phone in the Study. This patch intentionally
does not change `data/world.json`: bring your own phone into any room using
the object editor.

```text
src/app.py                    thin app shell; Tk root and two surface tabs
src/surfaces/builder.py       editor surface / forms
src/world_builder.py         editor-domain orchestrator
src/surfaces/game.py          play surface / transcript and command input
src/game.py                   game-domain orchestrator / parser / session state
src/world_model.py           shared world JSON contract and validation
src/world_store.py           shared JSON file manager (atomic writes)
```

Neither surface calls the other. The editor writes the world JSON; a game session loads it and owns a separate mutable copy. Future surfaces can share `world_model` and `world_store` without reusing either UI.

## Deliberately not included yet

No action-rule system, `use`/`open` behavior, container traversal, secret discovery, dialogue, NPC intelligence, combat, audio playback, persistent save games, networking or AI inference. Objects, actors, secrets, and extra metadata can already be authored through Full Room JSON and imports; runtime support can be added one behavior at a time.

Run tests: `python -m unittest discover -s tests -v`.
