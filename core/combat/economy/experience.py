import json
import random

from core.models import Player


def _gen_packages() -> list[dict]:
    """Generate 3 distinct stat package options, each with 15 points across atk/def/hp.
    Each stat gets at least 1 point; the rest are distributed randomly.
    """
    packages = []
    for _ in range(3):
        a = random.randint(1, 13)
        b = random.randint(1, 14 - a)
        c = 15 - a - b  # always >= 1 since a <= 13 and a+b <= 14
        packages.append({"atk": a, "def": b, "hp": c})
    return packages


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

                # Generate 3 package options and queue them.
                packages = _gen_packages()
                new_packages.append(packages)
                changes["packages_generated"] += 1

                changes["msgs"].append(f"🎉 **LEVEL UP!** ({player.level})")
                changes["msgs"].append(
                    "📦 **Stat packages available** — choose after combat!"
                )

                if player.level % 10 == 0:
                    await bot.database.users.modify_currency(
                        user_id, "passive_points", 2
                    )
                    changes["msgs"].append(
                        "✨ **Milestone!** Gained **2** Passive Points!"
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
