import json
import random

from core.models import Player


def _gen_packages(base_atk: int = 0, base_def: int = 0, base_hp: int = 0) -> list[dict]:
    """Generate 3 stat packages of 15 points each (atk/def/hp, all ≥ 1).

    Packages lean toward whichever stat is furthest below the balanced target
    (ATK ≈ DEF, HP = ATK + 10), but only once a stat is *more than 20% below
    its target* — moderate natural skew within that window still produces
    fully-random packages.  Bias uses linear weighting (not squared) for a
    gentle push rather than a hard lock-in.  Three options are produced with
    jitter ±1 / ±2 / ±3 so the player always has genuine choice.
    """
    TOTAL = 15

    # Reference: ideal equal value for ATK and DEF; HP target = ref + 10.
    ref = (base_atk + base_def + max(0, base_hp - 10)) / 3

    # 20 % tolerance — deviations within this band are considered fine.
    tolerance = max(1.0, ref * 0.20)

    raw_deficits = {
        "atk": max(0.0, ref - base_atk),
        "def": max(0.0, ref - base_def),
        "hp":  max(0.0, (ref + 10) - base_hp),
    }
    # Only the portion that exceeds the tolerance drives the bias.
    deficits = {k: max(0.0, v - tolerance) for k, v in raw_deficits.items()}

    if sum(deficits.values()) < 0.5:
        # All stats within the 20 % tolerance window — fully random distribution.
        packages = []
        for _ in range(3):
            a = random.randint(1, 13)
            b = random.randint(1, 14 - a)
            packages.append({"atk": a, "def": b, "hp": TOTAL - a - b})
        return packages

    # Linear weighting (softer than squared) + 0.5 floor so every stat always
    # gets at least a token allocation even when its deficit is zero.
    weights = {k: deficits[k] + 0.5 for k in deficits}
    w_sum = sum(weights.values())
    ideal = {k: weights[k] / w_sum * TOTAL for k in weights}

    def _make_pkg(variance: int) -> dict:
        a = max(1, round(ideal["atk"] + random.uniform(-variance, variance)))
        d = max(1, round(ideal["def"] + random.uniform(-variance, variance)))
        h = TOTAL - a - d
        if h < 1:
            # Clamp: shave points from the larger of a/d to restore hp >= 1.
            excess = 1 - h
            if a >= d:
                a = max(1, a - excess)
            else:
                d = max(1, d - excess)
            h = TOTAL - a - d
        return {"atk": a, "def": d, "hp": h}

    # Increasing jitter gives the player genuine choice while still steering
    # all three options toward the under-invested stat(s).
    return [_make_pkg(v) for v in (1, 2, 3)]


class ExperienceManager:
    @staticmethod
    def _get_exp_table():
        with open("assets/exp.json") as f:
            return json.load(f)

    @staticmethod
    async def add_experience(
        bot,
        user_id: str,
        player: Player,
        xp_amount: int,
        server_id: str | None = None,
    ) -> dict:
        """
        Adds XP, processes level ups, and returns a dictionary of the stat changes.
        Respects the user's EXP Protection toggle.

        For levels 1–99, stat gains are *deferred* to a post-combat stat-package
        selection UI instead of being applied immediately.  Pass ``server_id`` so
        packages can be persisted to the DB; omit only for legacy / endgame paths
        where the player is already level 100+ (packages never trigger there anyway).
        """
        changes = {
            "xp_added": 0,
            "levels_gained": 0,
            "ascensions_gained": 0,
            "atk_gained": 0,
            "def_gained": 0,
            "hp_gained": 0,
            "packages_generated": 0,
            "msgs": [],
        }

        # 1. Check EXP Protection
        exp_protected = await bot.database.users.get_exp_protection(user_id)
        if exp_protected:
            changes["msgs"].append("🛡️ **EXP Protection Active:** No EXP gained.")
            return changes

        # 2. Add XP
        player.exp += xp_amount
        changes["xp_added"] = xp_amount
        exp_table = ExperienceManager._get_exp_table()

        # Accumulate pending stat packages for all level-ups in this grant.
        new_packages: list[list[dict]] = []

        # 3. Process Level Ups
        while True:
            exp_threshold = exp_table["levels"].get(str(player.level), 999999999)
            if player.exp < exp_threshold:
                break

            # Ascension (level 100+) — unchanged from original
            if player.level >= 100:
                bracket = (player.ascension // 100) + 1
                exp_threshold *= bracket
                if player.exp < exp_threshold:
                    break

                player.ascension += 1
                player.exp -= exp_threshold
                changes["ascensions_gained"] += 1

                await bot.database.users.modify_currency(user_id, "passive_points", 2)
                changes["msgs"].append(
                    f"🌟 **ASCENSION LEVEL UP!** ({player.ascension})"
                )
                changes["msgs"].append("✨ Gained **2** Passive Points!")

            # Normal Level Up (pre-100): generate packages instead of applying stats.
            else:
                player.level += 1
                player.exp -= exp_threshold
                changes["levels_gained"] += 1

                # Full-heal to current max HP (base stats unchanged until package chosen).
                player.current_hp = player.total_max_hp

                # Generate 3 package options biased toward the most underallocated
                # stat so the player can keep their build balanced over time.
                packages = _gen_packages(
                    player.base_attack, player.base_defence, player.max_hp
                )
                new_packages.append(packages)
                changes["packages_generated"] += 1

                changes["msgs"].append(f"🎉 **LEVEL UP!** ({player.level})")
                # (No "choose after combat" message: the stat-package picker
                # interrupts the post-combat flow automatically.)

                if player.level % 10 == 0:
                    await bot.database.users.modify_currency(
                        user_id, "passive_points", 2
                    )
                    changes["msgs"].append(
                        "✨ **Milestone!** Gained **2** Passive Points! "
                        "Use `/allocate_stats` to spend them on permanent bonuses, "
                        "and check `/journey` to see what you've just unlocked and claim your rewards!"
                    )

        # 4. Persist pending packages to DB (append to any already-pending sets).
        if new_packages and server_id:
            existing = await bot.database.users.get_pending_packages(user_id, server_id)
            all_packages = (existing or []) + new_packages
            await bot.database.users.set_pending_packages(
                user_id, server_id, all_packages
            )

        return changes

    @staticmethod
    async def remove_experience(
        bot, user_id: str, player: Player, base_loss: int
    ) -> int:
        """Removes XP on death, factoring in EXP Protection."""
        exp_protected = await bot.database.users.get_exp_protection(user_id)
        if exp_protected:
            return 0  # No XP lost if protected

        actual_loss = min(player.exp, base_loss)
        player.exp -= actual_loss
        return actual_loss
