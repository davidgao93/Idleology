_BASE_SECONDS = {
    "normal": 2 * 3600,   # 2 hours
    "rare":   4 * 3600,   # 4 hours
    "giga":   8 * 3600,   # 8 hours
}

# Blood drops per egg tier (multiplier × monster_level)
EGG_BLOOD_MULTIPLIER = {"normal": 1, "rare": 2, "giga": 10}


class HatcheryMechanics:

    @staticmethod
    def incubation_seconds(egg_tier: str, workers: int) -> int:
        """Returns actual incubation duration in seconds after applying worker reduction."""
        base = _BASE_SECONDS.get(egg_tier, _BASE_SECONDS["normal"])
        reduction = min(workers * 0.001, 1.0)  # 0.1% per worker, hard-capped at 100%
        return max(60, int(base * (1.0 - reduction)))

    @staticmethod
    def blood_reward(egg_tier: str, monster_level: int) -> int:
        """Returns the amount of blood dropped when the incubated monster is defeated."""
        return monster_level * EGG_BLOOD_MULTIPLIER.get(egg_tier, 1)
