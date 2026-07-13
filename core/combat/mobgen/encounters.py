import random
from typing import Any, Dict, List, Tuple

from core.images import (
    ENCOUNTER_ANGELIC_DRAGON,
    ENCOUNTER_BALANCE,
    ENCOUNTER_SOUL_CORE,
    ENCOUNTER_VOID_FRAGMENT,
)


class EncounterManager:
    @staticmethod
    def check_boss_door(
        player_level: int,
        currencies: dict,
        boss_chance_bonus: float = 0.0,
        affinity: str | None = None,
        affinity_shift: float = 0.0,
    ) -> Tuple[bool, str, dict]:
        """
        Determines if a boss door appears.

        boss_chance_bonus — Inner Sanctum Deicide's Hunter's Resolve node:
            widens the total trigger window beyond the base 80% (capped at 95%).
        affinity / affinity_shift — Deicide's Marked Prey choice node: shifts
            relative weight toward one boss type, taken proportionally from
            the other three.

        Returns: (triggered, boss_type, cost_dict)
        """
        roll = random.random()

        boss_order = ["aphrodite", "lucifer", "gemini", "NEET"]
        p_door = min(0.95, 0.80 + boss_chance_bonus)
        weights = {b: p_door / len(boss_order) for b in boss_order}
        if affinity in weights and affinity_shift > 0:
            bonus = weights[affinity] * affinity_shift
            taken = bonus / (len(boss_order) - 1)
            for b in boss_order:
                if b == affinity:
                    weights[b] += bonus
                else:
                    weights[b] = max(0.0, weights[b] - taken)

        windows = {}
        cumulative = 0.0
        for b in boss_order:
            windows[b] = (cumulative, cumulative + weights[b])
            cumulative += weights[b]

        # 1. Aphrodite (Celestial)
        lo, hi = windows["aphrodite"]
        if (
            player_level >= 20
            and currencies["dragon_key"] > 0
            and currencies["angel_key"] > 0
            and lo <= roll < hi
        ):
            return True, "aphrodite", {"dragon_key": 1, "angel_key": 1}

        # 2. Lucifer (Infernal)
        lo, hi = windows["lucifer"]
        if player_level >= 30 and currencies["soul_cores"] >= 5 and lo <= roll < hi:
            return True, "lucifer", {"soul_cores": 5}

        # 3. Gemini (Balance)
        lo, hi = windows["gemini"]
        if (
            player_level >= 40
            and currencies["balance_fragment"] >= 2
            and lo <= roll < hi
        ):
            return True, "gemini", {"balance_fragment": 2}

        # 4. NEET (Void)
        lo, hi = windows["NEET"]
        if player_level >= 50 and currencies["void_frags"] >= 3 and lo <= roll < hi:
            return True, "NEET", {"void_frags": 3}

        return False, "", {}

    @staticmethod
    def get_door_details(boss_type: str) -> Dict[str, str]:
        if boss_type == "aphrodite":
            return {
                "title": "A Celestial Gate",
                "desc": "Your **Angelic** and **Draconic** keys tremble.\nUnlock the gate?",
                "img": ENCOUNTER_ANGELIC_DRAGON,
                "cost_str": "-1 Dragon Key, -1 Angelic Key",
            }
        elif boss_type == "lucifer":
            return {
                "title": "An Infernal Gate",
                "desc": "Your soul cores tremble. Unlock the gate?",
                "img": ENCOUNTER_SOUL_CORE,
                "cost_str": "-5 Soul Cores",
            }
        elif boss_type == "NEET":
            return {
                "title": "Sad Kid Behind a Gate",
                "desc": "Your **void fragments** suddenly start to resonate.\nUnlock the gate?",
                "img": ENCOUNTER_VOID_FRAGMENT,
                "cost_str": "-3 Void Fragments",
            }
        elif boss_type == "gemini":
            return {
                "title": "A Twinned Gate",
                "desc": "Your **Fragments of Balance** hums in resonance.\nUnlock the gate?",
                "img": ENCOUNTER_BALANCE,
                "cost_str": "-2 Fragments of Balance",
            }
        return {}

    # ============================================================
    # Modifiers count progression tables (tied to player level)
    # Breakpoints: <20, 20-39, 40-59, 60-79, 80-99, >=100
    # ============================================================
    _MOD_PROG_WEAK = [1, 1, 2, 2, 3]
    _MOD_PROG_LIGHT = [1, 2, 2, 3, 4]
    _MOD_PROG_MEDIUM = [1, 2, 3, 4, 5]
    _MOD_PROG_STRONG = [2, 4, 4, 5, 6]
    _MOD_PROG_VERY_STRONG = [2, 4, 6, 6, 8]
    _MOD_PROG_NEET_FINAL = [3, 5, 7, 8, 10]
    _MOD_PROG_GEMINI = [2, 2, 3, 3, 5]

    @staticmethod
    def _resolve_modifiers_count(player_level: int, progression: List[int]) -> int:
        """Resolve modifiers_count using the 20/40/60/80/100 breakpoints."""
        breakpoints = [20, 40, 60, 80, 100]
        for i, bp in enumerate(breakpoints):
            if player_level < bp:
                return progression[i]
        return progression[-1]  # >= 100

    @staticmethod
    def get_boss_phases(
        boss_type: str, player_level: int = 100
    ) -> List[Dict[str, Any]]:
        if boss_type == "aphrodite":
            return [
                {
                    "name": "Aphrodite, Heaven's Envoy",
                    "level": 886,
                    "modifiers_count": EncounterManager._resolve_modifiers_count(
                        player_level, EncounterManager._MOD_PROG_WEAK
                    ),
                    "hp_multiplier": 1.2,
                    "modifiers_progression": EncounterManager._MOD_PROG_WEAK,  # optional
                },
                {
                    "name": "Aphrodite, the Eternal",
                    "level": 887,
                    "modifiers_count": EncounterManager._resolve_modifiers_count(
                        player_level, EncounterManager._MOD_PROG_MEDIUM
                    ),
                    "hp_multiplier": 1.3,
                    "modifiers_progression": EncounterManager._MOD_PROG_MEDIUM,
                },
                {
                    "name": "Aphrodite, Harbinger of Destruction",
                    "level": 888,
                    "modifiers_count": EncounterManager._resolve_modifiers_count(
                        player_level, EncounterManager._MOD_PROG_STRONG
                    ),
                    "hp_multiplier": 1.5,
                    "modifiers_progression": EncounterManager._MOD_PROG_STRONG,
                },
            ]

        elif boss_type == "lucifer":
            return [
                {
                    "name": "Lucifer, Fallen",
                    "level": 663,
                    "modifiers_count": EncounterManager._resolve_modifiers_count(
                        player_level, EncounterManager._MOD_PROG_WEAK
                    ),
                    "hp_multiplier": 1.1,
                    "modifiers_progression": EncounterManager._MOD_PROG_WEAK,
                },
                {
                    "name": "Lucifer, Maddened",
                    "level": 664,
                    "modifiers_count": EncounterManager._resolve_modifiers_count(
                        player_level, EncounterManager._MOD_PROG_LIGHT
                    ),
                    "hp_multiplier": 1.2,
                    "modifiers_progression": EncounterManager._MOD_PROG_LIGHT,
                },
                {
                    "name": "Lucifer, Enraged",
                    "level": 665,
                    "modifiers_count": EncounterManager._resolve_modifiers_count(
                        player_level, EncounterManager._MOD_PROG_MEDIUM
                    ),
                    "hp_multiplier": 1.3,
                    "modifiers_progression": EncounterManager._MOD_PROG_MEDIUM,
                },
                {
                    "name": "Lucifer, Unbound",
                    "level": 666,
                    "modifiers_count": EncounterManager._resolve_modifiers_count(
                        player_level, EncounterManager._MOD_PROG_VERY_STRONG
                    ),
                    "hp_multiplier": 1.5,
                    "modifiers_progression": EncounterManager._MOD_PROG_VERY_STRONG,
                },
            ]

        elif boss_type == "NEET":
            return [
                {
                    "name": "NEET.Sadge",
                    "level": 444,
                    "modifiers_count": EncounterManager._resolve_modifiers_count(
                        player_level, EncounterManager._MOD_PROG_WEAK
                    ),
                    "hp_multiplier": 1.15,
                    "modifiers_progression": EncounterManager._MOD_PROG_WEAK,
                },
                {
                    "name": "NEET.Madge",
                    "level": 445,
                    "modifiers_count": EncounterManager._resolve_modifiers_count(
                        player_level, EncounterManager._MOD_PROG_LIGHT
                    ),
                    "hp_multiplier": 1.25,
                    "modifiers_progression": EncounterManager._MOD_PROG_LIGHT,
                },
                {
                    "name": "NEET.REEEEEE",
                    "level": 446,
                    "modifiers_count": EncounterManager._resolve_modifiers_count(
                        player_level, EncounterManager._MOD_PROG_MEDIUM
                    ),
                    "hp_multiplier": 1.5,
                    "modifiers_progression": EncounterManager._MOD_PROG_MEDIUM,
                },
                {
                    "name": "NEET.Deadge",
                    "level": 447,
                    "modifiers_count": EncounterManager._resolve_modifiers_count(
                        player_level, EncounterManager._MOD_PROG_NEET_FINAL
                    ),
                    "hp_multiplier": 0.2,
                    "modifiers_progression": EncounterManager._MOD_PROG_NEET_FINAL,
                },
            ]

        elif boss_type == "gemini":
            return [
                {
                    "name": "Castor the Mortal",
                    "level": 555,
                    "modifiers_count": EncounterManager._resolve_modifiers_count(
                        player_level, EncounterManager._MOD_PROG_GEMINI
                    ),
                    "hp_multiplier": 1.2,
                    "modifiers_progression": EncounterManager._MOD_PROG_GEMINI,
                },
                {
                    "name": "Pollux the Divine",
                    "level": 556,
                    "modifiers_count": EncounterManager._resolve_modifiers_count(
                        player_level, EncounterManager._MOD_PROG_GEMINI
                    ),
                    "hp_multiplier": 1.2,
                    "modifiers_progression": EncounterManager._MOD_PROG_GEMINI,
                },
                {
                    "name": "The Gemini Twins",
                    "level": 557,
                    "modifiers_count": EncounterManager._resolve_modifiers_count(
                        player_level, EncounterManager._MOD_PROG_STRONG
                    ),
                    "hp_multiplier": 1.5,
                    "modifiers_progression": EncounterManager._MOD_PROG_STRONG,
                },
            ]

        return []
