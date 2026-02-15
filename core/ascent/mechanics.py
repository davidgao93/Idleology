import math

class AscentMechanics:
    @staticmethod
    def calculate_monster_level(player_level: int, player_ascension: int, stage: int) -> int:
        """Calculates the monster level for a specific stage."""
        # Base formula from legacy: player.level + player.ascension + 3 + (2 per stage)
        # We adjust to match the loop logic: Start +3, then +2 every iteration
        return player_level + player_ascension + 3 + ((stage - 1) * 2)

    @staticmethod
    def get_modifier_counts(stage: int) -> tuple[int, int]:
        """Returns (normal_mods, boss_mods) for the given stage."""
        n_mods = 5 + (stage // 2)
        b_mods = 1 + (stage // 5)
        return n_mods, b_mods

    @staticmethod
    def calculate_stage_rewards(monster_level: int, stage: int) -> int:
        """Calculates gold gain for clearing a stage."""
        return int((monster_level ** 1.5) * (1 + stage / 10))

    @staticmethod
    def calculate_xp_loss(current_xp: int) -> int:
        """Calculates XP penalty for defeat."""
        return int(current_xp * 0.10)