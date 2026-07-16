# core/companions/logic.py

import random
from collections import defaultdict
from datetime import datetime

from core.companions.mechanics import CompanionMechanics
from core.emojis import GOLD_COIN
from core.items.factory import create_companion


class CompanionLogic:
    @staticmethod
    async def apply_loot_bag(bot, user_id: str, items: list) -> dict:
        """Credits a list of ("Type", Amount) loot tuples to the player. Shared
        by passive collection and the Kinship Point loot roll (mastery tree)."""
        summary = defaultdict(int)

        for loot_type, amount in items:
            # --- GOLD ---
            if loot_type == "Gold":
                await bot.database.users.modify_gold(user_id, amount)
                summary["Gold"] += amount

            # --- RUNES ---
            elif loot_type == "Rune of Refinement":
                await bot.database.users.modify_currency(user_id, "refinement_runes", 1)
                summary["Rune of Refinement"] += 1
            elif loot_type == "Rune of Potential":
                await bot.database.users.modify_currency(user_id, "potential_runes", 1)
                summary["Rune of Potential"] += 1
            elif loot_type == "Rune of Shattering":
                await bot.database.users.modify_currency(user_id, "shatter_runes", 1)
                summary["Rune of Shattering"] += 1

            # --- BOSS KEYS (Random Selection) ---
            elif loot_type == "Boss Key":
                # 20% Dragon, 20% Angel, 20% Soul Core, 20% Void Frag, 20% balance fragment
                key_roll = random.random()
                if key_roll < 0.20:
                    await bot.database.users.modify_currency(user_id, "dragon_key", 1)
                    summary["Draconic Key"] += 1
                elif key_roll < 0.40:
                    await bot.database.users.modify_currency(user_id, "angel_key", 1)
                    summary["Angelic Key"] += 1
                elif key_roll < 0.60:
                    await bot.database.users.modify_currency(user_id, "soul_cores", 1)
                    summary["Soul Core"] += 1
                elif key_roll < 0.80:
                    await bot.database.users.modify_currency(user_id, "void_frags", 1)
                    summary["Void Fragment"] += 1
                else:
                    await bot.database.users.modify_currency(
                        user_id, "balance_fragment", 1
                    )  # [NEW]
                    summary["Fragment of Balance"] += 1

        return summary

    @staticmethod
    async def collect_passive_rewards(bot, user_id: str, guild_id: str) -> str:
        """
        Handles the calculation and DB updates for passive companion loot.
        """
        # 1. Fetch Data
        last_collect = await bot.database.users.get_companion_collect_time(user_id)

        active_rows = await bot.database.companions.get_active(user_id)
        if not active_rows:
            return "You have no active companions to gather loot."

        active_comps = [create_companion(row) for row in active_rows]

        # 2. Load mastery nodes for loot modifiers
        try:
            mastery = await bot.database.companions.get_mastery(user_id, guild_id)
            mastery_nodes = mastery.get("nodes_owned", {})
        except Exception:
            mastery_nodes = {}

        # 3. Calculate
        results = CompanionMechanics.calculate_collection_rewards(
            active_comps, last_collect, mastery_nodes=mastery_nodes
        )

        if not results["can_collect"]:
            return "Your companions are still gathering supplies. Check back later (1h interval)."

        # 4. Process Loot
        summary = await CompanionLogic.apply_loot_bag(bot, user_id, results["items"])

        # 5. Update Timer
        await bot.database.users.update_companion_collect_time(
            user_id, datetime.now().isoformat()
        )

        # 6. Format Output
        if not summary:
            return f"Your companions returned empty-handed from {results['cycles']} cycles."

        msg = f"**Companions returned after {results['cycles']} adventures! They drop their gifts at your feet.**\n"

        # Gold
        if summary["Gold"] > 0:
            msg += f"{GOLD_COIN} **{summary['Gold']:,}** Gold\n"
            del summary["Gold"]

        # Items
        items_list = [f"{k} x{v}" for k, v in summary.items()]

        if items_list:
            msg += "📦 " + ", ".join(items_list)

        return msg

    @staticmethod
    async def spend_kp_for_loot(bot, user_id: str, server_id: str) -> str:
        """Spends all available Kinship Points 1-for-1 on rolls of the companion
        loot table. Intended for once the Forged Bonds tree is fully unlocked
        and KP has no further node to buy."""
        mastery = await bot.database.companions.get_mastery(user_id, server_id)
        kp = mastery.get("kinship_points", 0)
        if kp <= 0:
            return "You have no Kinship Points to spend."

        ok = await bot.database.companions.spend_kinship_points(user_id, server_id, kp)
        if not ok:
            return "Failed to spend Kinship Points — try again."

        nodes_owned = mastery.get("nodes_owned", {})
        items = CompanionMechanics.roll_kp_loot(nodes_owned, kp)
        summary = await CompanionLogic.apply_loot_bag(bot, user_id, items)

        if not summary:
            return f"Spent **{kp:,}** Kinship Points but found nothing of value."

        msg = f"**Spent {kp:,} Kinship Points for {kp:,} loot roll(s)!**\n"
        if summary.get("Gold"):
            msg += f"{GOLD_COIN} **{summary['Gold']:,}** Gold\n"
            del summary["Gold"]

        items_list = [f"{k} x{v}" for k, v in summary.items()]
        if items_list:
            msg += "📦 " + ", ".join(items_list)

        return msg
