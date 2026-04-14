import json
import random

from core.models import Player


class ExperienceManager:
    @staticmethod
    def _get_exp_table():
        with open("assets/exp.json") as f:
            return json.load(f)

    @staticmethod
    async def add_experience(bot, user_id: str, player: Player, xp_amount: int) -> dict:
        """
        Adds XP, processes level ups, and returns a dictionary of the stat changes.
        Respects the user's EXP Protection toggle.
        """
        changes = {
            "xp_added": 0,
            "levels_gained": 0,
            "ascensions_gained": 0,
            "atk_gained": 0,
            "def_gained": 0,
            "hp_gained": 0,
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

        # 3. Process Level Ups
        while True:
            exp_threshold = exp_table["levels"].get(str(player.level), 999999999)
            if player.exp < exp_threshold:
                break

            # Ascension (level 100+)
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

            # Normal Level Up (pre-100)
            else:
                player.level += 1
                player.exp -= exp_threshold
                changes["levels_gained"] += 1

                atk_inc = random.randint(1, 5)
                def_inc = random.randint(1, 5)
                hp_inc = random.randint(1, 5)

                player.base_attack += atk_inc
                player.base_defence += def_inc
                player.max_hp += hp_inc
                player.current_hp = player.max_hp  # Full heal on level up
                player.compute_flat_stats()  # Refresh flat cache with new base values

                changes["atk_gained"] += atk_inc
                changes["def_gained"] += def_inc
                changes["hp_gained"] += hp_inc

                await bot.database.users.modify_stat(user_id, "attack", atk_inc)
                await bot.database.users.modify_stat(user_id, "defence", def_inc)
                await bot.database.users.modify_stat(user_id, "max_hp", hp_inc)

                changes["msgs"].append(f"🎉 **LEVEL UP!** ({player.level})")
                changes["msgs"].append(
                    f"📈 +{atk_inc} Atk, +{def_inc} Def, +{hp_inc} HP"
                )

                if player.level % 10 == 0:
                    await bot.database.users.modify_currency(
                        user_id, "passive_points", 2
                    )
                    changes["msgs"].append(
                        "✨ **Milestone!** Gained **2** Passive Points!"
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
