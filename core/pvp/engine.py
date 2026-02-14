import random
from typing import Tuple

class PvPEngine:
    @staticmethod
    def calculate_damage(current_hp: int) -> int:
        """
        Calculates damage based on the attacker's current HP.
        Mechanic: Lower HP = Higher Max Hit (Dharok's Effect).
        """
        if current_hp <= 0:
            return 0

        # Base max hit at full HP is 25
        # Scaling: Adds up to 120 damage based on missing HP %
        if current_hp == 100:
            max_hit = 25
        else:
            # Formula from legacy code: 120 * (100 - current_hp) / 100
            bonus = 120 * (100 - current_hp) / 100
            max_hit = max(25, int(bonus))

        return random.randint(1, max_hit)

    @staticmethod
    def calculate_heal() -> int:
        """Fixed heal amount for PvP."""
        return 20