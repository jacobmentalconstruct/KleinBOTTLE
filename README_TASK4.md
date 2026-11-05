# KleinBOTTLE — KleinOS Task 4: In-world computer

**Status:** code prepared and validated in a local test harness; not installed into your workstation yet.

## Installation

1. Back up or commit your working project. Close KleinBOTTLE before replacing files.
2. Extract this ZIP into the root of `C:\Jacob\_GameDESIGN\_KleinBOTTLE`, preserving paths.
3. Two existing files are replaced:
   - `src/game.py` — domain command `use computer` and visible terminal recognition.
   - `src/surfaces/game.py` — opens the Task 3 KleinOS desktop window.
4. One new file is added:
   - `tests/test_computer_integration.py` — domain/UI integration tests.
5. Keep your existing `src/computer_backend.py`, `src/surfaces/computer.py`, Dockerfile, world data, and phone files. This ZIP doesn't include or alter those.

The two replacement files were based on the inspected GitHub `main` blobs:
- `src/game.py` Git blob SHA `ecd6178530c5fddc9e70318270e20527aa77276e`
- `src/surfaces/game.py` Git blob SHA `f266a2c987eadcd14f4c125dc869beee2f02369e`

If your local versions have changed after that baseline, do not blindly replace them; compare first.

## Test

```powershell
python -m compileall -q src tests
python -m unittest discover -s tests -v
```

You can run the Docker integration test again (optional; Docker Desktop must be running):

```powershell
$env:KLEINOS_DOCKER_INTEGRATION = "1"
python -m unittest discover -s tests -p "test_computer*.py" -v
Remove-Item Env:\KLEINOS_DOCKER_INTEGRATION
```

## Create an in-world computer

Start KleinBOTTLE. In the World Builder, select the room (e.g. your Entrance Hall or Study) and **Add Object**:

- Object ID: `desk_computer`
- Name: `Desk Computer`
- Kind: `terminal` (exactly this word, not `computer`)
- Description: `A compact computer sits beside a humming monitor.`

Click **Apply to Room**, then **Save Room**. Switch to **Play** (or Reload World), type `look`, then `use computer`.

The equivalent object in a room's `objects` array:

```json
{
  "id": "desk_computer",
  "name": "Desk Computer",
  "kind": "terminal",
  "description": "A compact computer sits beside a humming monitor.",
  "portable": false
}
```

One terminal uses the fixed Task 1/2 Docker sandbox. Close the KleinOS window to return to Play; persistent files remain in the named Docker volume.

## Scope and stop conditions

- `use computer`, `use terminal`, `use pc`, or `use desk computer` works when a visible `kind: "terminal"` object is present.
- The computer opens the existing Task 3 desktop. If it's already open, bring that window forward instead of creating another.
- Play's current room and inventory remain unchanged when the window opens or closes.
- Existing telephone logic and world data are untouched.
- Do not implement world publishing, multiple sandbox identities, or a persistent interactive TTY in Task 4.

## Validation performed before delivery

Syntax compilation passed. A combined test harness (world/editor/game/telephone/computer backend/desktop/new integration) ran **59 tests: 58 passed, 1 live Docker test skipped** in this environment. The live Docker test was separately passed on your workstation in Task 2. In-game launch remains to be tested on your machine.
