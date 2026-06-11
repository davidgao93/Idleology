# Backward-compatible lazy re-exports for jewel_engine and rewards.
# These are not direct submodules of core.combat, so we expose them here
# via __getattr__ so that ``from core.combat import jewel_engine`` and
# ``from core.combat import rewards`` keep working without causing circular
# imports during package initialization.


def __getattr__(name: str):
    if name == "jewel_engine":
        from core.combat.turns import jewel_engine

        globals()["jewel_engine"] = jewel_engine  # cache for subsequent accesses
        return jewel_engine
    if name == "rewards":
        from core.combat.economy import rewards

        globals()["rewards"] = rewards
        return rewards
    raise AttributeError(f"module 'core.combat' has no attribute {name!r}")
