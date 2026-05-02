import random
import csv
from collections import defaultdict
from typing import List, Dict, Any

from core.combat.drops import roll_essence_drop


class CurioManager:
    @staticmethod
    def get_drop_table() -> Dict[str, float]:
        """Returns map of Reward Name -> Weight (relative probability)."""
        return {
            # Fluff (~80%)
            "Boss Key":      22,
            "50k Gold":      20,
            "100k Gold":     18,
            "250k Gold":     12,
            "500k Gold":      8,
            # Uncommon runes — 1x per drop (~14%)
            "Rune of Refinement":  4,
            "Rune of Potential":   4,
            "Rune of Shattering":  4,
            "Rune of Imbuing":     2,
            # Rare — 1x per drop (~5%)
            "Essence":        2,
            "Guild Ticket":   2,
            "Settler Material": 1,
            # Very rare — 1x per drop (~1.5%)
            "Pinnacle Key":   0.5,
            "Antique Tome":   0.5,
            "Elemental Key":  0.5,
        }

    @staticmethod
    async def process_open(bot, user_id: str, server_id: str, amount: int) -> Dict[str, Any]:
        table = CurioManager.get_drop_table()
        population = list(table.keys())
        weights = list(table.values())

        results = random.choices(population, weights=weights, k=amount)
        summary = defaultdict(int)
        for r in results:
            summary[r] += 1

        # --- Gold ---
        gold_total = 0
        for label, mult in (("50k Gold", 50_000), ("100k Gold", 100_000),
                             ("250k Gold", 250_000), ("500k Gold", 500_000)):
            if label in summary:
                gold_total += mult * summary[label]
        if gold_total:
            await bot.database.users.modify_gold(user_id, gold_total)

        # --- Boss Key (1x random per drop) ---
        if "Boss Key" in summary:
            key_options = ["soul_cores", "dragon_key", "angel_key", "void_frags", "balance_fragment"]
            key_counts = defaultdict(int)
            for _ in range(summary["Boss Key"]):
                key_counts[random.choice(key_options)] += 1
            for col, cnt in key_counts.items():
                await bot.database.users.modify_currency(user_id, col, cnt)

        # --- Runes (1x per drop, aggregated) ---
        rune_map = {
            "Rune of Refinement": "refinement_runes",
            "Rune of Potential":  "potential_runes",
            "Rune of Shattering": "shatter_runes",
            "Rune of Imbuing":    "imbue_runes",
        }
        for label, col in rune_map.items():
            if label in summary:
                await bot.database.users.modify_currency(user_id, col, summary[label])

        # --- Essence (1x random per drop) ---
        if "Essence" in summary:
            essence_counts = defaultdict(int)
            for _ in range(summary["Essence"]):
                essence_counts[roll_essence_drop()] += 1
            for etype, cnt in essence_counts.items():
                for _ in range(cnt):
                    await bot.database.essences.add(user_id, etype)

        # --- Guild Ticket (1x per drop) ---
        if "Guild Ticket" in summary:
            await bot.database.partners.add_tickets(user_id, summary["Guild Ticket"])

        # --- Settler Material (1x random sub-type per drop) ---
        if "Settler Material" in summary:
            mat_keys = ["magma_core", "life_root", "spirit_shard"]
            mat_counts = defaultdict(int)
            for _ in range(summary["Settler Material"]):
                mat_counts[random.choice(mat_keys)] += 1
            for col, cnt in mat_counts.items():
                await bot.database.users.modify_currency(user_id, col, cnt)

        # --- Pinnacle Key (1x per drop) ---
        if "Pinnacle Key" in summary:
            await bot.database.users.modify_currency(user_id, "pinnacle_key", summary["Pinnacle Key"])

        # --- Antique Tome (1x per drop) ---
        if "Antique Tome" in summary:
            await bot.database.users.modify_currency(user_id, "antique_tome", summary["Antique Tome"])

        # --- Elemental Key (1x random sub-type per drop) ---
        if "Elemental Key" in summary:
            key_counts = defaultdict(int)
            key_options = ["blessed_bismuth", "sparkling_sprig", "capricious_carp"]
            for _ in range(summary["Elemental Key"]):
                key_counts[random.choice(key_options)] += 1
            for col, cnt in key_counts.items():
                if col == "blessed_bismuth":
                    await bot.database.uber.increment_blessed_bismuth(user_id, server_id, cnt)
                elif col == "sparkling_sprig":
                    await bot.database.uber.increment_sparkling_sprig(user_id, server_id, cnt)
                elif col == "capricious_carp":
                    await bot.database.uber.increment_capricious_carp(user_id, server_id, cnt)

        await bot.database.users.modify_currency(user_id, "curios", -amount)

        return {"summary": dict(summary), "loot_logs": []}

    @staticmethod
    def get_image_url(reward_name: str) -> str:
        key = reward_name.replace(" Gold", "").replace(" ", "_")
        try:
            with open("assets/curios.csv", mode="r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["Item"] == key:
                        return row["URL"]
        except Exception:
            pass
        return None
