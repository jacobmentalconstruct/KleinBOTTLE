"""
kleinos/mahisland_ai.py

MAHisLAND mob AI mixin — spawn, state machine, drops.
"""

from __future__ import annotations

import math
import random

from kleinos.mahisland_world import (
    T_WALL, W_TILES, H_TILES,
    MOB_CAP_CRITTER, MOB_CAP_RAIDER,
    MOB_CRITTER_HP, MOB_RAIDER_HP,
    MOB_WANDER_DUR, MOB_PAUSE_DUR,
    MOB_WANDER_SPD, MOB_FLEE_SPD, MOB_CHASE_SPD,
    MOB_LOST_TIME,
    RAIDER_CONTACT_DMG, RAIDER_WALL_DMG,
    SCORE_CRITTER, SCORE_RAIDER,
    _sfx,
)


class _AIMixin:

    def _try_spawn_mob(self) -> None:
        critters = sum(1 for m in self._mobs if m["kind"] == "critter")
        raiders  = sum(1 for m in self._mobs if m["kind"] == "raider")
        kind = None
        if critters < MOB_CAP_CRITTER and raiders < MOB_CAP_RAIDER:
            kind = random.choice(["critter", "critter", "raider"])
        elif critters < MOB_CAP_CRITTER:
            kind = "critter"
        elif raiders < MOB_CAP_RAIDER:
            kind = "raider"
        if kind is None:
            return

        # Pick a random unclaimed self._tile away from player
        for _ in range(30):
            tx = random.randint(1, W_TILES - 2)
            ty = random.randint(1, H_TILES - 2)
            if self._grid[ty][tx] == T_WALL:
                continue
            wx = tx * self._tile + self._tile / 2
            wy = ty * self._tile + self._tile / 2
            if math.hypot(wx - self._px, wy - self._py) < self._tile * 12:
                continue
            if self._claimed(tx, ty):
                continue
            hp = MOB_CRITTER_HP if kind == "critter" else MOB_RAIDER_HP
            self._mobs.append({
                "kind": kind, "x": wx, "y": wy,
                "hp": hp, "max_hp": hp,
                "state": "wander", "state_t": MOB_WANDER_DUR,
                "vx": 0.0, "vy": 0.0,
                "dmg_cd": 0.0, "lost_t": 0.0,
            })
            return

    def _update_mobs(self, dt: float) -> None:
        dead = []
        for mob in self._mobs:
            self._update_one_mob(mob, dt)
            if mob["hp"] <= 0:
                dead.append(mob)
        for mob in dead:
            self._mobs.remove(mob)
            self._drop_mob(mob)

    def _update_one_mob(self, mob: dict, dt: float) -> None:
        dx = self._px - mob["x"]
        dy = self._py - mob["y"]
        dist = math.hypot(dx, dy)

        can_see = dist < self._mob_sight and self._has_los(mob["x"], mob["y"], self._px, self._py)

        if mob["kind"] == "critter":
            if can_see:
                mob["state"] = "flee"
                mob["lost_t"] = MOB_LOST_TIME
            elif mob["state"] == "flee":
                mob["lost_t"] -= dt
                if mob["lost_t"] <= 0:
                    mob["state"] = "wander"
                    mob["state_t"] = MOB_WANDER_DUR
                    mob["vx"] = mob["vy"] = 0.0

            if mob["state"] == "flee":
                if dist > 0:
                    spd = MOB_FLEE_SPD * max(0.3, mob["lost_t"] / MOB_LOST_TIME)
                    mob["vx"] = -(dx / dist) * spd
                    mob["vy"] = -(dy / dist) * spd
            else:
                self._wander_tick(mob, dt)

        else:  # raider
            if can_see:
                mob["state"] = "chase"
                mob["lost_t"] = MOB_LOST_TIME
            elif mob["state"] == "chase":
                mob["lost_t"] -= dt
                if mob["lost_t"] <= 0:
                    mob["state"] = "wander"
                    mob["state_t"] = MOB_WANDER_DUR
                    mob["vx"] = mob["vy"] = 0.0

            if mob["state"] == "chase":
                if dist > 0:
                    mob["vx"] = (dx / dist) * MOB_CHASE_SPD
                    mob["vy"] = (dy / dist) * MOB_CHASE_SPD
            else:
                self._wander_tick(mob, dt)

            # Contact damage to player
            if dist < self._tile * 1.2:
                if mob["dmg_cd"] <= 0:
                    dmg = RAIDER_CONTACT_DMG
                    if "tunic" in self._gear:
                        dmg = dmg // 2
                    self._hp = max(0, self._hp - dmg)
                    mob["dmg_cd"] = 1.0
                    _sfx("damage")
                    if self._hp <= 0:
                        _sfx("death")
                        self._state = "dead"
                else:
                    mob["dmg_cd"] -= dt

            # Attack adjacent walls/structures
            for s in self._structs:
                if s["kind"] not in ("wall", "gate", "spike"):
                    continue
                sx = s["tx"] * self._tile + self._tile / 2
                sy = s["ty"] * self._tile + self._tile / 2
                if math.hypot(sx - mob["x"], sy - mob["y"]) < self._tile * 1.4:
                    s["hp"] -= RAIDER_WALL_DMG * dt
            self._structs = [s for s in self._structs if s["hp"] > 0]

        # Move mob
        nx = mob["x"] + mob["vx"] * dt
        ny = mob["y"] + mob["vy"] * dt
        if self._passable(nx, mob["y"]):
            mob["x"] = nx
        else:
            mob["vx"] *= -1
        if self._passable(mob["x"], ny):
            mob["y"] = ny
        else:
            mob["vy"] *= -1

        # Clamp to world
        mob["x"] = max(self._tile, min(mob["x"], (W_TILES - 1) * self._tile))
        mob["y"] = max(self._tile, min(mob["y"], (H_TILES - 1) * self._tile))

    def _wander_tick(self, mob: dict, dt: float) -> None:
        mob["state_t"] -= dt
        if mob["state_t"] <= 0:
            if mob["state"] == "wander":
                mob["state"] = "pause"
                mob["state_t"] = MOB_PAUSE_DUR
                mob["vx"] = mob["vy"] = 0.0
            else:
                mob["state"] = "wander"
                mob["state_t"] = MOB_WANDER_DUR
                angle = random.uniform(0, math.pi * 2)
                mob["vx"] = math.cos(angle) * MOB_WANDER_SPD
                mob["vy"] = math.sin(angle) * MOB_WANDER_SPD

    def _drop_mob(self, mob: dict) -> None:
        _sfx("mob_die")
        if mob["kind"] == "critter":
            self._inv["food"]    = self._inv.get("food",    0) + 2
            self._inv["leather"] = self._inv.get("leather", 0) + 1
            self._score += SCORE_CRITTER
            self._flash_msg(f"+2 food  +1 leather  +{SCORE_CRITTER}pts")
        else:
            self._inv["leather"] = self._inv.get("leather", 0) + 2
            self._score += SCORE_RAIDER
            self._flash_msg(f"+2 leather  +{SCORE_RAIDER}pts")
