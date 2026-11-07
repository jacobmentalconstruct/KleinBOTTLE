# KleinOS PC Scaling — Notes & Findings

Recorded after testing auto-scale (monitor scale ≈ 2.0× at 1920×1080) during the
embedded PC view-swap feature. Reverted to config-based scale for now.

---

## How the scaling system works

The monitor bezel is a fixed PNG rendered by `RetroMonitorFrame` (kleinos/retro_monitor_frame.py).
It takes a `scale: float` and multiplies every dimension:

```python
canvas_w = int(rect["canvas_w"] * scale)   # 760 × scale
canvas_h = int(rect["canvas_h"] * scale)   # 480 × scale
screen_rect = {x, y, width, height}        # all × scale
```

The `screen` area (where apps and games live) also scales proportionally.
At scale=1.3 ("large") the screen rect is roughly 896×530 px.
At scale=2.0 (auto-screen-fill on 1920×1080) it is roughly 1376×816 px.

Config scale values (kleinos/config.py `_PC_SIZES`):

| Key     | Factor | Canvas size (w × h) |
|---------|--------|---------------------|
| small   | 0.65   | 494 × 312           |
| medium  | 1.0    | 760 × 480           |
| large   | 1.3    | 988 × 624           |
| xlarge  | 1.6    | 1216 × 768          |

---

## Game-by-game audit

### NULL Invaders (`kleinos/game_pane.py` — `SpaceInvadersPane`)

**Scaling behaviour: broken.**

- Canvas size is **hardcoded**: `W: int = 539`, `H: int = 408` as class attributes.
- Sprite pixel scale `_S = 3` is a module-level constant (1 logical px = 3 canvas px).
- All physics, collision detection, and drawing use `self.W` / `self.H` as bounds.
- When packed with `fill="both", expand=True` into a larger screen area, the
  `tk.Canvas` grows to fill the available space, but `W` and `H` are still 539×408.
  The game logic (player position clamp, invader grid placement, bullet range) all
  reference the old bounds — the game draws in the top-left quadrant with empty
  space to the right and below.
- **Lag observed at scale ≈ 2.0**: the tk.Canvas has ≈4× more pixels to repaint each
  frame. The game loop uses `after(16, ...)` (60 fps target), but if the draw pass
  takes >16 ms the loop drifts. At 2.0× there are ≈2 M canvas pixels vs ≈220 K at
  scale=1.0 — tile rendering via `create_rectangle` is expensive at that size.

**What a fix needs:**
- Accept a `scale` parameter in `SpaceInvadersPane.__init__`.
- Scale `W`, `H`, `_SPR_W`, `_SPR_H`, `_S`, bullet speed, invader speed, all pixel
  offsets.
- Or redesign with a fixed logical grid and a `zoom` transform.

---

### MAHisLAND (`kleinos/mahisland.py` — `MAHisLANDPane`)

**Scaling behaviour: partially adapts, but visually inconsistent and laggy.**

- Uses a scrolling viewport: `self._vw = self.winfo_width()` and
  `self._vh = self.winfo_height()`, updated on `<Configure>`.
- `_on_resize` fires when the screen rect grows → `_vw`/`_vh` correctly expand.
- `TILE = 20` px is a **module-level constant** shared by world gen, physics, and
  rendering. It does not scale.
- Effect at 2.0×: the viewport shows more of the world (≈2× more tiles), which
  is not inherently wrong, but every tile is still 20 px so objects shrink relative
  to the screen. The world can feel huge and hard to read.
- Physics values (`MOB_WANDER_SPD = 45 px/s`, `SWING_RANGE = TILE * 2.2`, player
  speed) are in world-space px/s, so movement *speed* does not change, but it
  looks faster relative to screen size because tiles are smaller.
- **Lag observed**: rendering scales with visible tile count. At 2.0×, `tx1 - tx0`
  and `ty1 - ty0` double, so the per-frame `create_rectangle` calls roughly quadruple.
  The game loop is `after(16, ...)` so this causes drift and apparent sluggishness in
  movement/attacks (the game loop runs but draw passes are slower than 16 ms).

**What a fix needs:**
- Make `TILE` a runtime variable (not a module constant).
- Scale `TILE`, all speed/range constants, and font sizes by the same factor.
- Re-generate or re-calculate world geometry when scale changes (or treat `TILE` as
  purely a display scale while keeping world coordinates in logical tiles).

---

### The Shack (`kleinos/adventure.py` — `TheShack`)

**Scaling behaviour: layout intact, text unscaled.**

- Renders a `tk.Label` with `font=("Consolas", 9)` inside a Frame.
- Label is packed `anchor="nw"` so it stays top-left; the larger screen area just
  leaves empty space below/right.
- No canvas, no game loop — no lag.
- Perfectly functional, just looks small in a large screen rect.

**What a fix needs:**
- Font size proportional to scale: `int(9 * scale)`.

---

### KleinBOTTLE (TextAdventure via `kleinos/kb_surfaces.py`)

**Scaling behaviour: layout adapts, fonts unscaled.**

- Built from `ttk` / `tk.Frame` / `ttk.PanedWindow` — Tkinter widgets reflow to
  fill the available area.
- Room text, narration, and exit lists use `("Consolas", 9–11)` fixed fonts.
- The room image canvas (`kb_surfaces.py:309`) reads `winfo_width/height` and
  rescales images dynamically → images adapt fine.
- Text adventure state machine (`src/game.py`) is screen-independent.
- No lag at any scale.

**What a fix needs:**
- Scale all font sizes by the monitor scale factor.
- Optionally expose a `configure_scale(factor)` callback (see architecture below).

---

## App audit

### KleinCHAT (`kleinos/chat_pane.py` — `OllamaChatPane`)

- Pure Tkinter Frame + Text widget — reflows to fill screen area. ✓
- Font: `("Consolas", 9)` — fixed, looks small at high scale.
- No lag. Fix: scale font sizes.

### Notes

- Not inspected in detail but expected to be a simple text widget — same as KleinCHAT.
- No lag. Fix: scale font sizes.

### Image Generator (`kleinos/image_gen_pane.py`)

- Uses `min(w / iw, h / ih)` to fit images in the display area → already adapts. ✓
- Control buttons / labels use fixed fonts — small at high scale.
- No lag. Fix: scale font sizes.

### World Builder (`kleinos/kb_surfaces.py` — `WorldBuilder` / `KleinBuilderPane`)

- Full Tkinter layout with PanedWindow, scrollable canvas — reflows. ✓
- Uses `("Consolas", 8–11)` fonts throughout.
- No lag. Fix: scale font sizes.

---

## Root causes summary

| Issue | Root cause |
|-------|-----------|
| NULL Invaders draws in corner | `W`/`H` hardcoded; not updated when Canvas grows |
| NULL Invaders + MAHisLAND lag | `create_rectangle` per-frame cost scales with canvas pixels; loop target 16 ms is broken at 4× pixel count |
| All games look small | `TILE` / `_S` / sprite sizes are module constants, unaware of scale |
| All text looks small | `("Consolas", N)` font sizes are literal integers throughout |
| No crash | Monitor itself scales correctly; screen rect scales proportionally |

---

## Proposed scaling architecture

### Phase 1 — Font scaling (low effort, big visual improvement)

1. Add `FONT_SCALE: float = 1.0` to `kleinos/config.py`, set when PC opens.
2. Replace all `("Consolas", 9)` literals with `font_pt(9)` helper:
   ```python
   def font_pt(n: int) -> int:
       return max(6, int(n * _FONT_SCALE))
   ```
3. Each app reads `font_pt()` on `__init__`. No game loop changes needed.

### Phase 2 — Game canvas scaling (medium effort)

**NULL Invaders:**
- Add `scale: float = 1.0` to `SpaceInvadersPane.__init__`.
- Multiply `W`, `H`, `_S`, all speed/offset constants by `scale`.
- Pass scale from `SpaceInvaders.create(parent, scale=...)`.

**MAHisLAND:**
- Replace `TILE = 20` global with an instance attribute `self._tile`.
- Scale physics constants (`MOB_SIGHT`, `SWING_RANGE`, speeds) relative to `self._tile`.
- Accept `scale: float = 1.0` in `MAHisLANDPane.__init__`, set `self._tile = int(20 * scale)`.

### Phase 3 — `configure_scale` protocol (clean architecture)

Add an optional protocol to `KleinApp` / `KleinGame`:
```python
class KleinApp:
    def configure_scale(self, factor: float) -> None:
        """Called by KleinPC when opening in embedded mode. Override to rescale."""
        pass
```
`KleinPC.__init__` calls `item.configure_scale(scale)` for each app/game when
`embedded_in` is set. Items that do not override do nothing (backward compatible).

### Performance — game loop fix

Both canvas-based games use `after(16, ...)` for 60 fps. At 2×+ scale, draw
passes exceed 16 ms, causing drift. Fix: use `time.monotonic()` delta-time:
```python
now = time.monotonic()
dt = now - self._last_tick
self._last_tick = now
# update physics using dt (seconds), not fixed steps
self.after(16, self._tick)
```
Both games already pass `dt` to physics (MAHisLAND) or use frame counters
(NULL Invaders) — MAHisLAND is closer to ready. NULL Invaders needs a physics
pass to convert frame-count logic to dt-based.

---

## Status

- Auto-scale reverted (`f50cb8d`). Config-based scale active.
- `KleinPC` already accepts `scale` override parameter (`dc494d7`) for future use.
- X-Large (1.6×) added to settings as next manual step up (`25b40bc`).
- No code changes needed to unblock current gameplay at config scales.
