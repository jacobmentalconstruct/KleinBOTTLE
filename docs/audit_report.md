# KleinBOTTLE — Consolidation & Hardening Audit Report

**Date:** 2026-11-07  
**Branch:** `main` (commit `843f428`)  
**Scope:** Read-only architecture audit. No structural changes made.

---

## 1. Architecture Map

### Entry Point
| File | Lines | Role |
|------|-------|------|
| `kleinos/__main__.py` | 242 | Root. `TitleScreen` canvas → `_show_adventure` → `KleinAdventurePane` → `_patch_pc` wires `KleinPC` |
| `src/app.py` | 45 | **DEPRECATED.** Old Notebook entry-point. Docstring: "Do not use it." |

### Orchestrator
| File | Lines | Role |
|------|-------|------|
| `kleinos/klein_pc.py` | 665 | Builds sidebar + CRT bezel content area. Hosts all `KleinApp`s and `KleinGame`s. Owns layout config callbacks. |
| `kleinos/klein_app.py` | 75 | Base classes: `KleinApp`, `KleinGame`, `KleinChat`. Zero Tkinter imports. |

### Games
| File | Lines | Role |
|------|-------|------|
| `kleinos/mahisland.py` | 1484 | MAHisLAND survival game. Single `MAHisLANDPane(tk.Canvas)` god object. |
| `kleinos/game_pane.py` | 553 | NULL Invaders (`SpaceInvadersPane`). Accepts `scale: float` parameter. |
| `kleinos/adventure.py` | 339 | The Shack text adventure. `AdventureEngine` + `TheShack(KleinGame)`. |

### Apps / Adapters
| File | Lines | Role |
|------|-------|------|
| `kleinos/kb_surfaces.py` | 499 | Bridges `src/` domain to KleinOS. `KleinBuilderPane`, `KleinAdventurePane`, `TextAdventure`, `WorldBuilder`. **Monkey-patches `src.ui_theme` globals at import.** |
| `kleinos/settings_pane.py` | 731 | 4-tab settings UI. Receives layout mutation callbacks from `KleinPC`. Calls `_config.load()`/`save()` from widget methods. |
| `kleinos/room_assist.py` | 420 | AI-assisted room generation. Ollama HTTP via daemon threads + `self.after(0, ...)`. |
| `kleinos/terminal_pane.py` | — | `TerminalPane` — reusable terminal widget consumed by `TheShack`, `TextAdventure`. |
| `kleinos/app_pane.py` | — | `AppPane` — generic wrapper for `KleinApp.create()`. |
| `kleinos/chat_pane.py` | — | `ChatPane` — base for `KleinChat` subclasses. |
| `kleinos/room_panel.py` | — | Room editor widget embedded in `KleinBuilderPane`. |

### Infrastructure
| File | Lines | Role |
|------|-------|------|
| `kleinos/config.py` | 78 | Persistent config (`data/kleinos_config.json`). `_PC_SIZES`, palette, audio, image pipeline. |
| `kleinos/world_library.py` | 150 | World file management. `ensure_wip`, `save_snapshot`, `list_library`, `validate_for_promotion`, `promote_to_main`. |
| `kleinos/audio.py` | — | Sound playback. |

### Domain (`src/`)
| File | Lines | Role |
|------|-------|------|
| `src/world_model.py` | 95 | Pure domain model. `blank_world`, `normalize_room`, `normalize_world`, `exit_warnings`. Zero Tkinter imports. |
| `src/world_store.py` | 40 | File persistence. Atomic write via `tempfile` + `os.replace`. |
| `src/world_builder.py` | 80+ | Use-case layer. `WorldBuilder` CRUD over `WorldStore`. No Tkinter. |
| `src/ui_theme.py` | 107 | Midnight Blue ttk theme. Module-level color constants. `apply_theme(root)`, `style_text(widget)`, `style_dialog(window)`. |
| `src/surfaces/builder.py` | 729 | `BuilderSurface(ttk.Frame)` — the full world-editor UI. |
| `src/surfaces/game.py` | — | `GameSurface` — legacy game surface. |
| `src/ollama_phone.py` | — | Ollama telephone integration. |
| `src/computer_backend.py` | 338 | Docker sandbox. `--network none`, `--read-only`, `--cap-drop ALL`. |

### Tests (`tests/`)
| File | Covers |
|------|--------|
| `tests/test_phone.py` | Phone/Ollama integration |
| `tests/test_world_builder.py` | WorldBuilder CRUD |
| `tests/test_game.py` | Likely NULL Invaders/game surface |
| `tests/test_computer.py` | ComputerBackend |
| `tests/test_computer_surface.py` | Computer surface |
| `tests/test_computer_integration.py` | End-to-end computer |

**Not covered:** KleinPC lifecycle, MAHisLAND, settings_pane, room_assist, world_library.

### Dependency flow (observed)
```
kleinos/__main__.py
  └─ kleinos/klein_pc.py        ← orchestrator
       ├─ kleinos/kb_surfaces.py   ← imports src.ui_theme, patches its globals
       │    └─ src/world_builder.py → src/world_store.py → src/world_model.py
       ├─ kleinos/mahisland.py
       ├─ kleinos/game_pane.py
       ├─ kleinos/adventure.py
       ├─ kleinos/settings_pane.py → kleinos/config.py
       └─ kleinos/room_assist.py
```

Domain boundary check (`domain_boundary_audit.py`): 0 files over threshold.  
7 violations found, all trivial `self._text.config(...)` 3-chain attribute patterns.  
`src/` module: **zero Tkinter imports** — boundary is clean.

---

## 2. Prioritized Findings

### F1 — CRITICAL: mahisland.py is a 1484-line god object

**File:** `kleinos/mahisland.py`  
**Severity:** High — maintainability and scalability blocker.

`MAHisLANDPane` contains everything: module-level terrain constants, island world generation, game loop (`after(16,...)`), player physics, build mechanics, mob AI, inventory system, persistence (`_save_game`/`_load_game`), HUD rendering, full canvas draw pipeline. All 1484 lines are a single `tk.Canvas` subclass.

`module_decomp_planner` identified 15 sections, 10 safe to extract:
- World reset / terrain generation
- Resize handler
- Game loop
- Input handling
- Physics update
- Action dispatch
- Mob AI
- Persistence (save/load)
- HUD helpers
- Draw pipeline

**Impact:** Any scaling, physics, or AI change requires navigating the full class. `TILE = 20` is a module constant (see F4).

---

### F2 — CRITICAL: `KleinAdventurePane._poll_room()` is an uncancelled loop

**File:** `kleinos/kb_surfaces.py` (approx. line 190)  
**Severity:** High — resource leak.

```python
def _poll_room(self) -> None:
    ...
    self.after(400, self._poll_room)  # never cancelled
```

`self.after()` reschedules unconditionally. When `KleinAdventurePane` is destroyed (user navigates away), Tk silently continues firing the callback against the destroyed widget, eventually raising `TclError` or keeping the Python object alive indefinitely.

**Impact:** Memory and CPU leak for every adventure session started. Compounds over long sessions.

---

### F3 — HIGH: kb_surfaces.py monkey-patches `src.ui_theme` module globals

**File:** `kleinos/kb_surfaces.py:76–91`  
**Severity:** High — fragile coupling, import-order sensitive.

```python
def _patch_ui_theme() -> None:
    import src.ui_theme as _t
    _t.BACKGROUND = "#010a01"   # overwrite module globals
    _t.SURFACE = "#002200"
    ...
```

`_ui_patched` module-level flag prevents double-patching. This means:
1. Any code that imports `src.ui_theme` **before** `kb_surfaces` gets the original Midnight Blue theme.
2. Any code that imports `src.ui_theme` **after** `kb_surfaces` gets the patched green phosphor theme.
3. Reload (hot-reload tools, test isolation) breaks state.

The intent (green phosphor for KleinOS, midnight blue for the builder) is valid — but the mechanism is import-order coupling masquerading as encapsulation.

---

### F4 — HIGH: Bare `except: pass` silences failures in 14+ locations

**Files:** mahisland.py, config.py, kb_surfaces.py, builder.py, room_assist.py, world_library.py, __main__.py, and others.

Dangerous instances:

| File | Function | Risk |
|------|----------|------|
| `kleinos/config.py:save()` | `except Exception: pass` | Silent config loss — user changes never persist |
| `kleinos/mahisland.py:_save_game()` | `except Exception: pass` | Silent save failure — progress lost |
| `kleinos/world_library.py:save_snapshot()` | `except Exception: pass` | Silently corrupts snapshot name in JSON |
| `kleinos/world_library.py:list_library()` | `except Exception: pass` | Silently skips broken snapshots |
| `kleinos/world_library.py:promote_to_main()` | `except Exception: pass` | Pre-promotion backup failure swallowed (noted in comment) |
| `kleinos/__main__.py` | `except Exception: pass` | Splash photo error hidden |
| `kleinos/room_assist.py:_roll_window()` | `except Exception: pass` | Summarization failure hidden |

Total: 14 bare `except/pass` identified across all application files.

---

### F5 — MEDIUM: settings_pane.py (731 lines) mixes display and config I/O

**File:** `kleinos/settings_pane.py`  
**Severity:** Medium — Orchestrator→Component boundary violation.

`SettingsPane` directly calls `_config.load()` and `_config.save()` from widget handlers. It also receives mutable layout callbacks from `KleinPC` (`add_category`, `delete_category`, `rename_category`, `get_layout`) — the UI component owns a reference to the orchestrator's layout mutation API.

Per the architectural mandate, UI must not secretly own persistence. Config I/O belongs in the orchestrator layer, not in a leaf widget.

---

### F6 — MEDIUM: builder.py (729 lines) is a monolith with no decomposable boundaries

**File:** `src/surfaces/builder.py`  
**Severity:** Medium — maintainability.

`module_decomp_planner` output: 6 sections detected, all inside a `__preamble__` spanning 517 lines. The class is effectively unstructured — room-linking rules, ID validation, exit wiring, AI callback hooks, and all dialog code live as methods on a single `BuilderSurface(ttk.Frame)` class with no internal grouping.

Domain logic (exit wiring, ID generation, room validation) duplicates what `src/world_builder.py` and `src/world_model.py` already provide, rather than delegating to them.

---

### F7 — MEDIUM: Ollama config hardcoded as module constants in room_assist.py

**File:** `kleinos/room_assist.py:1–20`  
**Severity:** Medium — operability.

```python
_OLLAMA_HOST  = "127.0.0.1"
_OLLAMA_PORT  = 11434
_NARR_MODEL   = "qwen2.5:7b"
_FIELD_MODEL  = "qwen2.5:3b"
```

Changing host, port, or model requires editing source. `kleinos/config.py` already has an `image_pipeline` section with host/port/path fields — the same pattern should cover Ollama.

---

### F8 — MEDIUM: `TILE = 20` is unscalable

**File:** `kleinos/mahisland.py` (module-level constant)  
**Severity:** Medium — scaling blocker.

`TILE` is used in every physics calculation, hitbox, spawn distance, and camera offset. It is not an instance attribute and cannot be changed per-scale. `docs/scaling_notes.md` documents this explicitly as one of three scaling blockers alongside NULL Invaders' hardcoded `W`/`H` and unscaled font sizes throughout.

**Impact:** Cannot implement the Phase 2 canvas scaling without first converting `TILE` to a scale-derived instance attribute.

---

### F9 — LOW: `src/app.py` is a deprecated file still in the repo

**File:** `src/app.py`  
**Severity:** Low — cleanup.

Docstring: *"Do not use it."* Opens a `TkNotebook` with `BuilderSurface` + `GameSurface`. Not wired from `kleinos/__main__.py`. Safe to delete.

---

### F10 — LOW: Domain boundary is clean; `src/` has zero Tkinter imports

**Files:** `src/world_model.py`, `src/world_store.py`, `src/world_builder.py`  
**Severity:** N/A — positive finding.

The `src/` domain layer has zero Tkinter imports. `WorldStore.save()` uses `tempfile` + `os.replace` for atomic writes. `WorldBuilder` properly delegates all persistence to `WorldStore`. This is the clean architecture to extend toward.

---

### F11 — LOW: No tests for 5 critical workflows

**Severity:** Medium risk — no regression baseline for hardening work.

Untested workflows (per external team checklist):
- KleinPC lifecycle (sidebar enable/disable, game launch/exit)
- MAHisLAND (canvas creation, game loop, save/load)
- NULL Invaders (scale parameter, game loop)
- room_assist (Ollama thread safety)
- world_library (validate_for_promotion, promote_to_main)

---

## 3. Proposed Tranche Plan

### Tranche 0 — Housekeeping (est. 2 hours)
*No behavior change. Merge-safe at any time.*

- Delete `src/app.py` (deprecated, confirmed unused)
- Remove inline `import json as _json` from `kb_surfaces.py:365`
- Categorize all 14 bare `except/pass`: mark safe vs. dangerous in comments

---

### Tranche 1 — Stability (est. 1–2 days)
*Fix resource leaks and silent failure paths. No restructuring.*

**1a. Fix `_poll_room()` uncancelled loop** (F2)
```python
# on create:
self._poll_id: str | None = None
def _poll_room(self):
    ...
    self._poll_id = self.after(400, self._poll_room)

# on destroy:
self.bind("<Destroy>", self._on_destroy)
def _on_destroy(self, _):
    if self._poll_id:
        self.after_cancel(self._poll_id)
```

**1b. Fix dangerous bare `except/pass`** (F4)
- `config.save()`: catch `OSError` specifically; log to `sys.stderr` on failure
- `mahisland._save_game()`: same — catch `OSError`, let the user know if save fails
- `world_library.save_snapshot()`: let JSON encode/decode errors surface as `WorldLibraryError`

---

### Tranche 2 — Scaling Foundation (est. 2 days)
*Convert to scalable architecture per `docs/scaling_notes.md` plan.*

**2a. Font scaling pass** (Phase 1 from scaling_notes)
- Derive all font sizes from a `_SCALE` factor in `src/ui_theme.py`
- `configure_scale(scale: float)` protocol on `KleinApp`/`KleinGame`

**2b. Canvas game scaling** (Phase 2)
- `MAHisLANDPane`: convert `TILE = 20` to `self._tile = int(20 * scale)` (F8)
- `SpaceInvadersPane`: already accepts `scale` parameter — verify propagation
- `configure_scale` callchain: `RetroMonitorFrame` → `KleinPC` → all hosted panes

---

### Tranche 3 — mahisland.py Decomposition (est. 3 days)
*Extract the 10 safe sections identified by `module_decomp_planner`.*

Target modules:
- `kleinos/mahisland_world.py` — terrain constants, `W_TILES`/`H_TILES`, world generation, `_reset_world`
- `kleinos/mahisland_physics.py` — `_update`, player movement, dt loop, collision
- `kleinos/mahisland_ai.py` — mob spawn, mob update, mob AI
- `kleinos/mahisland_persist.py` — `_save_game`, `_load_game`, `_load_high_score`
- `kleinos/mahisland.py` → thin `MAHisLANDPane` orchestrator (~300 lines)

Prerequisite: establish regression baseline (smoke test for canvas creation + 1 game loop tick) before any file splits.

---

### Tranche 4 — Ollama Config Externalization (est. 1 day)
*Move hardcoded constants to config; expose in settings.*

- Add `ollama` key to `kleinos/config.py:_DEFAULTS`: `{"host": "127.0.0.1", "port": 11434, "narr_model": "qwen2.5:7b", "field_model": "qwen2.5:3b"}`
- `room_assist.py` reads from `_config.load()["ollama"]` instead of module constants
- Add Ollama section to `SettingsPane` Display or new AI tab (F7)

---

### Tranche 5 — Theme Coupling (est. 2 days)
*Replace monkey-patching with a proper theming protocol.*

- Define a `Palette` dataclass in `src/ui_theme.py` (or `kleinos/palette.py`): `background`, `surface`, `accent`, `text`, `status`
- `apply_theme(root, palette=MIDNIGHT_BLUE_PALETTE)` accepts the palette
- `KleinBuilderPane` / `KleinAdventurePane` receive a `palette=GREEN_PHOSPHOR_PALETTE` argument
- Delete `_patch_ui_theme()` and `_ui_patched` global (F3)

---

### Tranche 6 — Test Coverage (est. 2 days, ongoing)
*Establish regression baseline before structural tranches.*

Priority order (matches external team checklist):
1. KleinPC: sidebar enable/disable on game launch/exit
2. `world_library.validate_for_promotion()` — already has logic, easy to test
3. `world_library.promote_to_main()` — atomic replace + backup
4. `MAHisLANDPane` — canvas creation, `_reset_world`, `_save_game`/`_load_game` roundtrip
5. `KleinAdventurePane._poll_room()` — verify cancel-on-destroy after Tranche 1 fix

---

## 4. Summary Table

| # | Finding | Severity | Tranche |
|---|---------|----------|---------|
| F1 | mahisland.py 1484-line god object | High | 3 |
| F2 | _poll_room uncancelled loop | High | 1 |
| F3 | kb_surfaces monkey-patches src.ui_theme | High | 5 |
| F4 | 14 bare except/pass silencing failures | High | 0–1 |
| F5 | settings_pane mixes display + config I/O | Medium | (future) |
| F6 | builder.py 729-line monolith | Medium | (future) |
| F7 | Ollama config hardcoded in room_assist | Medium | 4 |
| F8 | TILE=20 unscalable module constant | Medium | 2 |
| F9 | src/app.py deprecated file in repo | Low | 0 |
| F10 | Domain boundary is clean (positive) | — | — |
| F11 | No tests for 5 critical workflows | Medium | 6 |

---

## 5. Recommended Tranche Order

```
Tranche 0 (housekeeping)  → Tranche 6 (tests)  → Tranche 1 (stability)
  → Tranche 2 (scaling)   → Tranche 3 (mahisland decomp)
  → Tranche 4 (ollama)    → Tranche 5 (theme coupling)
```

Rationale:
- Tranche 6 (tests) is listed second because Tranches 1–3 all require regression baselines. Without tests, the structural changes are un-verifiable.
- Tranches 0 and 1 are safe to run in any sequence; they fix clear bugs and cleanup with no structural risk.
- Tranches 2 and 3 are prerequisite for each other (scaling needs TILE converted; decomp needs scaling done).
- Tranches 4 and 5 are independent and can be done in parallel or deferred.

**Stop for review before beginning any tranche.**
