import copy
from dataclasses import dataclass
from core.models import Player, Monster


@dataclass
class SimulationResult:
    # --- Outgoing ---
    total_damage: int
    hits: int
    misses: int
    crits: int
    max_hit: int
    min_hit: int
    average_damage: float
    turns: int
    # --- Incoming ---
    total_damage_taken: int
    avg_damage_taken: float
    max_damage_taken: int
    is_max_lethal: bool


class DummyEngine:
    @staticmethod
    def run_simulation(player: Player, monster: Monster, turns: int = 100) -> SimulationResult:
        """
        Runs a fixed-length combat simulation using the real engine.
        Works on deep copies of player and monster so the originals are never mutated.
        Monster HP is reset each player turn so the simulation measures per-turn DPS
        rather than fight length.
        """
        from core.combat import engine

        sim_player  = copy.deepcopy(player)
        sim_monster = copy.deepcopy(monster)

        # Initialise ward and apply the same one-time combat-start effects the real fight uses
        sim_player.combat_ward = sim_player.get_combat_ward_value()
        engine.apply_stat_effects(sim_player, sim_monster)
        engine.apply_combat_start_passives(sim_player, sim_monster)

        # Keep a reference HP so the monster never actually "dies" mid-simulation
        monster_ref_hp = sim_monster.hp

        total_damage       = 0
        hits               = 0
        misses             = 0
        crits              = 0
        max_hit            = 0
        min_hit            = float('inf')
        total_damage_taken = 0
        max_damage_taken   = 0

        for _ in range(turns):
            # Reset monster HP each turn so the player always fights a full-health enemy,
            # giving clean per-turn DPS numbers unaffected by kill timing.
            sim_monster.hp = monster_ref_hp

            # --- Player turn ---
            p = engine.process_player_turn(sim_player, sim_monster)

            if p.is_hit:
                hits += 1
                if p.is_crit:
                    crits += 1
            else:
                misses += 1

            if p.damage > 0:
                total_damage += p.damage
                if p.damage > max_hit: max_hit = p.damage
                if p.damage < min_hit: min_hit = p.damage

            # Keep player HP above zero so HP-scaling passives (e.g. Frenzy) behave sensibly
            if sim_player.current_hp <= 0:
                sim_player.current_hp = 1

            # --- Monster turn ---
            m = engine.process_monster_turn(sim_player, sim_monster)

            total_damage_taken += m.hp_damage
            if m.hp_damage > max_damage_taken:
                max_damage_taken = m.hp_damage

        if min_hit == float('inf'):
            min_hit = 0

        return SimulationResult(
            total_damage=total_damage,
            hits=hits,
            misses=misses,
            crits=crits,
            max_hit=max_hit,
            min_hit=min_hit,
            average_damage=total_damage / turns,
            turns=turns,
            total_damage_taken=total_damage_taken,
            avg_damage_taken=total_damage_taken / turns,
            max_damage_taken=max_damage_taken,
            is_max_lethal=(max_damage_taken >= player.total_max_hp),
        )

    # ---------------------------------------------------------------------- #
    # Readiness assessments for Uber boss lobbies                              #
    # ---------------------------------------------------------------------- #

    @staticmethod
    def _make_uber_proxy(ref_lvl: int, modifiers: list[str]) -> Monster:
        """Build a proxy Monster using the same stat pipeline as the real generators."""
        from core.combat.gen_mob import calculate_monster_stats
        proxy = Monster(
            name="Proxy", level=ref_lvl, hp=999_999, max_hp=999_999, xp=0,
            attack=0, defence=0, modifiers=modifiers,
            image="", flavor="",
        )
        return calculate_monster_stats(proxy)

    @staticmethod
    def assess_readiness(player: Player, target: str) -> str:

        ref_lvl = player.level + player.ascension + 20

        if target == "aphrodite_uber":
            proxy = DummyEngine._make_uber_proxy(ref_lvl, ["Radiant Protection", "Absolute"])
            proxy.attack  += 25
            proxy.defence += 25
            proxy.is_boss = True

            res = DummyEngine.run_simulation(player, proxy, turns=50)
            avg_taken   = res.avg_damage_taken
            time_to_die = player.total_max_hp / avg_taken if avg_taken > 0 else 999
            if time_to_die < 5:
                return "You feel as if you are **not ready**. The aura alone crushes you."
            elif res.average_damage < (player.total_max_hp * 0.1) and time_to_die < 15:
                return "You feel this would be a **tough battle**. Survival is uncertain."
            return "You are **filled with determination**. Press onwards."

        if target == "lucifer_uber":
            proxy = DummyEngine._make_uber_proxy(ref_lvl, ["Hell's Fury", "Absolute"])
            proxy.attack  = int(proxy.attack  * 1.3)
            proxy.defence = int(proxy.defence * 0.3)
            proxy.attack  += 25
            proxy.defence += 25
            proxy.attack  += int(ref_lvl * 1.0)
            proxy.defence += int(ref_lvl * 0.2)
            proxy.is_boss = True

            res = DummyEngine.run_simulation(player, proxy, turns=50)
            avg_taken   = res.avg_damage_taken
            time_to_die = player.total_max_hp / avg_taken if avg_taken > 0 else 999
            if time_to_die < 3:
                return "You feel as if you are **not ready**. His strikes alone would end you."
            elif res.average_damage < (player.total_max_hp * 0.1) and time_to_die < 10:
                return "You feel this would be a **tough battle**. Survival is uncertain."
            return "You are **filled with determination**. Press onwards."

        if target == "neet_uber":
            proxy = DummyEngine._make_uber_proxy(ref_lvl, ["Void Aura", "Absolute"])
            proxy.attack  += 25
            proxy.defence += 25
            proxy.attack  += int(ref_lvl * 0.8)
            proxy.defence += int(ref_lvl * 0.5)
            proxy.is_boss = True

            res = DummyEngine.run_simulation(player, proxy, turns=50)
            avg_taken   = res.avg_damage_taken
            time_to_die = player.total_max_hp / avg_taken if avg_taken > 0 else 999
            if res.average_damage < (player.total_max_hp * 0.05):
                return "You feel as if you are **not ready**. The void would consume you before you land a dent."
            elif time_to_die < 5:
                return "You feel as if you are **not ready**. Its strikes alone would end you."
            elif res.average_damage < (player.total_max_hp * 0.10) and time_to_die < 12:
                return "You feel this would be a **tough battle**. The void slowly drains everything."
            return "You are **filled with determination**. The void beckons."

        if target == "gemini_uber":
            proxy = DummyEngine._make_uber_proxy(ref_lvl, ["Twin Strike", "Absolute"])
            proxy.attack  += 25
            proxy.defence += 25
            proxy.attack  += int(ref_lvl * 0.65)
            proxy.defence += int(ref_lvl * 0.65)
            proxy.is_boss = True

            res = DummyEngine.run_simulation(player, proxy, turns=50)
            avg_taken   = res.avg_damage_taken
            time_to_die = player.total_max_hp / avg_taken if avg_taken > 0 else 999
            if res.average_damage < (player.total_max_hp * 0.05):
                return "You feel as if you are **not ready**. The twins would outlast you entirely."
            elif time_to_die < 4:
                return "You feel as if you are **not ready**. Their Twin Strike would end you too quickly."
            elif res.average_damage < (player.total_max_hp * 0.10) and time_to_die < 10:
                return "You feel this would be a **tough battle**. The twins' rhythm is relentless."
            return "You are **filled with determination**. The constellation awaits."

        return "Unknown target."
