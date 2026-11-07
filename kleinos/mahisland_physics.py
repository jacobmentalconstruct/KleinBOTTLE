"""
kleinos/mahisland_physics.py

MAHisLAND physics/actions mixin — update loop, movement, collision,
swing/place/craft actions, hearth upkeep, claim helpers.
"""

from __future__ import annotations

import math

from kleinos.mahisland_world import (
    T_WALL, T_WATER, W_TILES, H_TILES,
    P_SPEED, HUNGER_DRAIN, FOOD_RESTORE_HN, FOOD_RESTORE_HP,
    SWING_CD, SWING_FLASH_TTL, SWING_DMG, SWING_RANGE,
    MOB_SPAWN_INTERVAL, HEARTH_FUEL_TICK, HEARTH_RADIUS,
    SCORE_PER_SEC, SCORE_STRUCT, SCORE_CRAFT,
    _SNAP_ANGLES, _sfx,
    _NODE_DROP, _NODE_RESPAWN,
    _STRUCTURES, _BUILD_HOTBAR, _GEAR_RECIPES,
)


class _PhysicsMixin:

    # ── Update ───────────────────────────────────────────────────────

    def _update(self, dt: float) -> None:
        if self._state == "start":
            k = self._keys
            if "n" in k:
                k.discard("n")
                self._reset_world()         # state → "play"
            elif "c" in k and self._has_save:
                k.discard("c")
                self._load_game()           # state → "play"
            return

        if self._state == "dead":
            if "r" in self._keys:
                self._keys.discard("r")
                self._update_high_score()
                self._clear_save()
                self._has_save = False
                self._state = "start"
            return

        if self._state == "confirm_exit":
            k = self._keys
            if "y" in k:
                k.discard("y")
                self._save_game()
                self._update_high_score()
                self._has_save = True
                self._state = "start"
            elif "n" in k:
                k.discard("n")
                self._state = "play"
            return

        k = self._keys

        # Toggle inventory / build menu
        if "i" in k:
            k.discard("i")
            self._inv_open = not self._inv_open
            self._build_menu_open = False
        if "r" in k:
            k.discard("r")
            self._build_menu_open = not self._build_menu_open
            self._inv_open = False

        # Hotbar: 1/2 equip tool, 3 consumes food (never changes equipped slot)
        if "1" in k:
            k.discard("1")
            self._hotbar_sel = 0   # FIST
        if "2" in k:
            k.discard("2")
            self._hotbar_sel = 1   # HAMMER
        if "3" in k:
            k.discard("3")
            self._eat_food()

        # Player facing — snap to 8 preset directions, click when sector changes
        dx = self._mx - self._px
        dy = self._my - self._py
        if abs(dx) + abs(dy) > 2:
            raw = math.atan2(dy, dx)
            snap = min(_SNAP_ANGLES,
                       key=lambda a: abs(math.atan2(math.sin(raw - a), math.cos(raw - a))))
            if snap != self._prev_snap:
                self._prev_snap = snap
                _sfx("aim_click")
            self._angle = snap

        # Movement
        mx = my = 0.0
        spd = P_SPEED
        ter = self._tile_at(self._px, self._py)
        if ter == T_WATER:
            spd *= 0.5

        if "w" in k or "up" in k:    my -= 1
        if "s" in k or "down" in k:  my += 1
        if "a" in k or "left" in k:  mx -= 1
        if "d" in k or "right" in k: mx += 1

        if mx != 0 and my != 0:
            mx *= 0.707
            my *= 0.707

        nx = self._px + mx * spd * dt
        ny = self._py + my * spd * dt

        # Collide with walls/impassable
        if self._passable(nx, self._py):
            self._px = nx
        if self._passable(self._px, ny):
            self._py = ny

        # Camera follows player
        self._camx = self._px - self._vw / 2
        self._camy = self._py - self._vh / 2

        # Swing cooldown
        if self._swing_cd > 0:
            self._swing_cd -= dt
        if self._swing_flash:
            ox, oy, ax, ay, ttl = self._swing_flash
            if ttl > 0:
                self._swing_flash = (ox, oy, ax, ay, ttl - dt)
            else:
                self._swing_flash = None

        # Swing via key (spacebar fallback)
        if "space" in k and self._swing_cd <= 0:
            self._do_swing()

        # Eat food
        if "f" in k:
            k.discard("f")
            self._eat_food()

        # Hunger tick
        self._hunger_acc += dt
        if self._hunger_acc >= 1.0:
            self._hunger_acc -= 1.0
            self._hunger = max(0, self._hunger - HUNGER_DRAIN)
            if self._hunger == 0:
                self._hp = max(0, self._hp - 2)
                if self._hp <= 0:
                    _sfx("death")
                    self._state = "dead"

        # Hearth fuel/upkeep tick
        self._fuel_acc += dt
        if self._fuel_acc >= HEARTH_FUEL_TICK:
            self._fuel_acc -= HEARTH_FUEL_TICK
            self._burn_hearths()

        # Mob spawn + update
        self._spawn_acc += dt
        if self._spawn_acc >= MOB_SPAWN_INTERVAL:
            self._spawn_acc -= MOB_SPAWN_INTERVAL
            self._try_spawn_mob()
        self._update_mobs(dt)

        # Node respawn
        for node in self._nodes:
            if node["respawn"] > 0:
                node["respawn"] -= dt
                if node["respawn"] <= 0:
                    node["respawn"] = 0.0
                    node["hp"] = node["max_hp"]

        # Score: time survived
        self._score_acc += dt
        if self._score_acc >= 1.0:
            self._score_acc -= 1.0
            self._score += SCORE_PER_SEC

        # Message timeout
        if self._msg_ttl > 0:
            self._msg_ttl -= dt

    def _passable(self, wx: float, wy: float) -> bool:
        r = self._tile * 0.35
        for ox, oy in [(-r, -r), (r, -r), (-r, r), (r, r)]:
            t = self._tile_at(wx + ox, wy + oy)
            if t == T_WALL:
                return False
            tx = int((wx + ox) // self._tile)
            ty = int((wy + oy) // self._tile)
            # Solid structures
            for s in self._structs:
                if s["tx"] == tx and s["ty"] == ty:
                    if s["kind"] in ("wall", "spike", "hearth", "bench", "crate"):
                        return False
                    if s["kind"] == "gate" and not s.get("open", False):
                        return False
            # Alive resource nodes
            for node in self._nodes:
                if node["hp"] > 0 and node["tx"] == tx and node["ty"] == ty:
                    return False
        return True

    def _tile_at(self, wx: float, wy: float) -> int:
        tx = int(wx // self._tile)
        ty = int(wy // self._tile)
        if tx < 0 or ty < 0 or tx >= W_TILES or ty >= H_TILES:
            return T_WALL
        return self._grid[ty][tx]

    # ── Actions ──────────────────────────────────────────────────────

    def _do_swing(self) -> None:
        if self._swing_cd > 0:
            return
        self._swing_cd = SWING_CD
        _sfx("swing")
        dmg = 25 if "gather_tool" in self._gear else SWING_DMG

        # Swing visual: line from player to reach point
        ax = self._px + math.cos(self._angle) * self._swing_range
        ay = self._py + math.sin(self._angle) * self._swing_range
        self._swing_flash = (self._px, self._py, ax, ay, SWING_FLASH_TTL)

        # Hit detection: node within range AND within ~70° of aim direction
        best_dist = self._swing_range + 1
        best_node = None
        for node in self._nodes:
            if node["hp"] <= 0:
                continue
            nx = node["tx"] * self._tile + self._tile / 2
            ny = node["ty"] * self._tile + self._tile / 2
            dist = math.hypot(nx - self._px, ny - self._py)
            if dist > self._swing_range:
                continue
            node_angle = math.atan2(ny - self._py, nx - self._px)
            diff = abs(math.atan2(math.sin(node_angle - self._angle),
                                  math.cos(node_angle - self._angle)))
            if diff > math.pi * 0.45:   # ~80° arc
                continue
            if dist < best_dist:
                best_dist = dist
                best_node = node

        # Hit mobs in arc (checked before nodes — same unified hitbox)
        combat_dmg = 30 if "weapon" in self._gear else SWING_DMG
        for mob in self._mobs:
            mdist = math.hypot(mob["x"] - self._px, mob["y"] - self._py)
            if mdist > self._swing_range:
                continue
            mob_angle = math.atan2(mob["y"] - self._py, mob["x"] - self._px)
            diff = abs(math.atan2(math.sin(mob_angle - self._angle),
                                  math.cos(mob_angle - self._angle)))
            if diff > math.pi * 0.45:
                continue
            mob["hp"] -= combat_dmg
            _sfx("hit_mob")
            self._flash_msg(f"Hit {mob['kind']}  {max(0,mob['hp'])}/{mob['max_hp']}")
            return

        if best_node is not None:
            best_node["hp"] -= dmg
            _sfx("hit_node")
            if best_node["hp"] <= 0:
                res, qty = _NODE_DROP[best_node["kind"]]
                if "gather_tool" in self._gear:
                    qty *= 2
                self._inv[res] = self._inv.get(res, 0) + qty
                best_node["respawn"] = float(_NODE_RESPAWN[best_node["kind"]])
                self._flash_msg(f"+{qty} {res}")
            else:
                self._flash_msg(f"{best_node['kind']}  {best_node['hp']}/{best_node['max_hp']}")

    def _do_interact(self) -> None:
        # Find nearest structure within range
        for s in self._structs:
            sx = s["tx"] * self._tile + self._tile / 2
            sy = s["ty"] * self._tile + self._tile / 2
            if math.hypot(sx - self._px, sy - self._py) < self._tile * 2:
                if s["kind"] == "gate":
                    s["open"] = not s.get("open", False)
                    self._flash_msg("Gate " + ("opened" if s["open"] else "closed"))
                    return
                if s["kind"] == "hearth":
                    wood = self._inv.get("wood", 0)
                    if wood > 0:
                        deposit = min(wood, 20)
                        s["fuel"] = s.get("fuel", 0) + deposit
                        self._inv["wood"] -= deposit
                        self._flash_msg(f"Hearth +{deposit} wood (fuel: {s['fuel']})")
                    else:
                        self._flash_msg("No wood to deposit")
                    return
                elif s["kind"] == "crate":
                    # Deposit all carried resources into crate
                    store = s.setdefault("store", {})
                    deposited = []
                    for res in list(self._inv):
                        qty = self._inv.get(res, 0)
                        if qty > 0:
                            store[res] = store.get(res, 0) + qty
                            self._inv[res] = 0
                            deposited.append(f"{qty} {res}")
                    if deposited:
                        self._flash_msg("Stored: " + ", ".join(deposited))
                    else:
                        # Withdraw everything from crate
                        withdrawn = []
                        for res, qty in list(store.items()):
                            if qty > 0:
                                self._inv[res] = self._inv.get(res, 0) + qty
                                withdrawn.append(f"{qty} {res}")
                        store.clear()
                        if withdrawn:
                            self._flash_msg("Retrieved: " + ", ".join(withdrawn))
                        else:
                            self._flash_msg("Crate is empty")
                    return

    def _do_place(self, kind: str) -> None:
        # Place exactly one self._tile out from the player in the facing direction
        tx = int(self._px // self._tile) + round(math.cos(self._angle))
        ty = int(self._py // self._tile) + round(math.sin(self._angle))

        if tx <= 0 or ty <= 0 or tx >= W_TILES - 1 or ty >= H_TILES - 1:
            self._flash_msg("Can't place there")
            return

        ter = self._grid[ty][tx]
        if ter == T_WALL:
            self._flash_msg("Can't place on wall")
            return
        if kind != "path" and ter == T_WATER:
            self._flash_msg("Only paths go on water")
            return

        # Check occupied
        for s in self._structs:
            if s["tx"] == tx and s["ty"] == ty:
                self._flash_msg("self._tile occupied")
                return

        recipe, hp = _STRUCTURES[kind]
        for res, qty in recipe.items():
            if self._inv.get(res, 0) < qty:
                self._flash_msg(f"Need {qty} {res}")
                return

        for res, qty in recipe.items():
            self._inv[res] -= qty

        s = {"tx": tx, "ty": ty, "kind": kind, "hp": hp, "max_hp": hp}
        if kind == "hearth":
            s["fuel"] = 0
            s["claimed"] = False
        self._structs.append(s)
        self._score += SCORE_STRUCT
        _sfx("place")
        self._flash_msg(f"Placed {kind}  +{SCORE_STRUCT}pts")

    def _do_craft(self, item: str) -> None:
        if item in _GEAR_RECIPES:
            # Need workbench nearby?
            need_bench = True
            for s in self._structs:
                if s["kind"] == "bench":
                    sx = s["tx"] * self._tile + self._tile / 2
                    sy = s["ty"] * self._tile + self._tile / 2
                    if math.hypot(sx - self._px, sy - self._py) < self._tile * 3:
                        need_bench = False
                        break
            if need_bench:
                self._flash_msg("Need a Workbench nearby")
                return
            recipe = _GEAR_RECIPES[item]
        else:
            return

        for res, qty in recipe.items():
            if self._inv.get(res, 0) < qty:
                self._flash_msg(f"Need {qty} {res} for {item}")
                return
        for res, qty in recipe.items():
            self._inv[res] -= qty
        self._gear.add(item)
        self._score += SCORE_CRAFT
        _sfx("craft")
        self._flash_msg(f"Crafted {item}!  +{SCORE_CRAFT}pts")

    def _handle_build_click(self, cx: int, cy: int) -> None:
        x0, y0 = self._build_menu_pos()
        for i, kind in enumerate(_BUILD_HOTBAR):
            by = y0 + 10 + i * 26
            if x0 + 4 <= cx <= x0 + 196 and by <= cy <= by + 22:
                recipe, _ = _STRUCTURES[kind]
                can_afford = all(self._inv.get(r, 0) >= q for r, q in recipe.items())
                if can_afford:
                    self._build_sel = kind
                    self._build_menu_open = False
                    cost_str = " ".join(f"{q}{r[:2]}" for r, q in recipe.items())
                    self._flash_msg(f"[{kind}] selected — RClick to place  ({cost_str})")
                else:
                    self._flash_msg(f"Can't afford {kind}")
                return

    def _build_menu_pos(self) -> tuple[int, int]:
        return (self._vw - 210, 50)

    def _handle_inv_click(self, cx: int, cy: int) -> None:
        # Gear craft buttons in drawer
        x0, y0 = self._inv_drawer_pos()
        bx = x0 + 10
        for i, (item, _) in enumerate(_GEAR_RECIPES.items()):
            by = y0 + 100 + i * 24
            if bx <= cx <= bx + 160 and by <= cy <= by + 20:
                self._do_craft(item)
                return

    def _burn_hearths(self) -> None:
        for s in self._structs:
            if s["kind"] != "hearth":
                continue
            paths = sum(1 for p in self._structs if p["kind"] == "path"
                        and self._in_claim(p["tx"], p["ty"], s))
            cost = 1 + paths // 10
            if s.get("fuel", 0) >= cost:
                s["fuel"] -= cost
                s["claimed"] = True
            else:
                s["claimed"] = False
                # Decay connected structures
                for st in self._structs:
                    if st["kind"] in ("wall", "gate", "spike") and self._in_claim(st["tx"], st["ty"], s):
                        st["hp"] -= 5
                self._structs = [st for st in self._structs if st["hp"] > 0]

    def _in_claim(self, tx: int, ty: int, hearth: dict) -> bool:
        hx = hearth["tx"]
        hy = hearth["ty"]
        return math.hypot(tx - hx, ty - hy) <= HEARTH_RADIUS

    def _claimed(self, tx: int, ty: int) -> bool:
        for s in self._structs:
            if s["kind"] == "hearth" and s.get("claimed"):
                if self._in_claim(tx, ty, s):
                    return True
        return False

    def _has_los(self, x1: float, y1: float, x2: float, y2: float) -> bool:
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy)
        if dist == 0:
            return True
        steps = max(2, int(dist / (self._tile * 0.6)))
        for i in range(1, steps):
            t = i / steps
            cx = int((x1 + dx * t) // self._tile)
            cy = int((y1 + dy * t) // self._tile)
            if cx < 0 or cy < 0 or cx >= W_TILES or cy >= H_TILES:
                return False
            if self._grid[cy][cx] == T_WALL:
                return False
            for node in self._nodes:
                if node["hp"] > 0 and node["tx"] == cx and node["ty"] == cy:
                    return False
        return True

    def _eat_food(self) -> None:
        if self._inv.get("food", 0) <= 0:
            self._flash_msg("No food")
            return
        self._inv["food"] -= 1
        self._hunger = min(P_HN_MAX, self._hunger + FOOD_RESTORE_HN)
        self._hp     = min(P_HP_MAX, self._hp     + FOOD_RESTORE_HP)
        _sfx("eat")
        self._flash_msg(f"Ate food  HP:{int(self._hp)}  HN:{int(self._hunger)}")
