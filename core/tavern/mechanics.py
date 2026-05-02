import math

class TavernMechanics:
    @staticmethod
    def calculate_potion_cost(player_level: int) -> int:
        """
        Calculates potion cost based on level.
        Base: 200.
        Level 20+: Adds (Level // 10) * 100.
        """
        additional_cost = 0
        if player_level >= 20:
            additional_cost = int(player_level / 10) * 100
        return 200 + additional_cost

    @staticmethod
    def calculate_rest_cost(player_level: int) -> int:
        """
        Calculates cost to bypass rest cooldown.
        Base: 400.
        Level 20+: Adds (Level // 10) * 100.
        """
        if player_level >= 20:
            return (int(player_level / 10) * 100) + 400
        return 400

