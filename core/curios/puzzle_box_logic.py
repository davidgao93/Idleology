import random
from collections import defaultdict

from core.combat.drops import roll_essence_drop
from core.images import CURIO_PUZZLE_BOX

PUZZLE_BOX_IMAGE = CURIO_PUZZLE_BOX

REWARD_POOL = [
    "Potential Runes",
    "Refinement Runes",
    "Shattering Runes",
    "Guild Tickets",
    "Gold",
    "Essences",
    "Elemental Keys",
    "Pinnacle Keys",
    "Antique Tomes",
    "Settler Materials",
]

REWARD_EMOJIS = {
    "Potential Runes":   "🔷",
    "Refinement Runes":  "🔶",
    "Shattering Runes":  "💠",
    "Guild Tickets":     "🎫",
    "Gold":              "💰",
    "Essences":          "🧪",
    "Elemental Keys":    "🗝️",
    "Pinnacle Keys":     "🔑",
    "Antique Tomes":     "📜",
    "Settler Materials": "⚒️",
}


def _roll_quantity(rtype: str) -> int:
    if rtype in ("Pinnacle Keys", "Antique Tomes"):
        return random.randint(1, 3)
    if rtype == "Gold":
        return random.randint(1, 10_000_000)
    return random.randint(1, 10)


def format_slot_display(rtype: str, qty: int) -> str:
    if rtype == "Gold":
        return f"{qty:,}g"
    return f"x{qty}"


def roll_slot() -> tuple[str, int]:
    """Roll a random reward type and quantity."""
    rtype = random.choice(REWARD_POOL)
    return (rtype, _roll_quantity(rtype))


def roll_all_slots() -> list[tuple[str, int]]:
    return [roll_slot() for _ in range(3)]


async def claim_rewards(bot, user_id: str, server_id: str, slots: list[tuple[str, int]]) -> list[str]:
    """Grant pre-rolled slot rewards. Returns display strings for the result embed."""
    lines = []

    for rtype, qty in slots:
        emoji = REWARD_EMOJIS[rtype]
        display = format_slot_display(rtype, qty)

        if rtype == "Potential Runes":
            await bot.database.users.modify_currency(user_id, "potential_runes", qty)
            lines.append(f"{emoji} **Potential Runes** {display}")

        elif rtype == "Refinement Runes":
            await bot.database.users.modify_currency(user_id, "refinement_runes", qty)
            lines.append(f"{emoji} **Refinement Runes** {display}")

        elif rtype == "Shattering Runes":
            await bot.database.users.modify_currency(user_id, "shatter_runes", qty)
            lines.append(f"{emoji} **Shattering Runes** {display}")

        elif rtype == "Guild Tickets":
            await bot.database.partners.add_tickets(user_id, qty)
            lines.append(f"{emoji} **Guild Tickets** {display}")

        elif rtype == "Gold":
            await bot.database.users.modify_gold(user_id, qty)
            lines.append(f"{emoji} **Gold** {display}")

        elif rtype == "Essences":
            essence_counts = defaultdict(int)
            for _ in range(qty):
                etype = roll_essence_drop()
                essence_counts[etype] += 1
                await bot.database.essences.add(user_id, etype)
            summary = ", ".join(f"{t} x{c}" for t, c in essence_counts.items())
            lines.append(f"{emoji} **Essences** x{qty} — {summary}")

        elif rtype == "Elemental Keys":
            key_counts = defaultdict(int)
            key_labels = {"blessed_bismuth": "Bismuth", "sparkling_sprig": "Sprig", "capricious_carp": "Carp"}
            for _ in range(qty):
                col = random.choice(list(key_labels.keys()))
                key_counts[col] += 1
            for col, cnt in key_counts.items():
                if col == "blessed_bismuth":
                    await bot.database.uber.increment_blessed_bismuth(user_id, server_id, cnt)
                elif col == "sparkling_sprig":
                    await bot.database.uber.increment_sparkling_sprig(user_id, server_id, cnt)
                elif col == "capricious_carp":
                    await bot.database.uber.increment_capricious_carp(user_id, server_id, cnt)
            summary = ", ".join(f"{key_labels[c]} x{v}" for c, v in key_counts.items())
            lines.append(f"{emoji} **Elemental Keys** x{qty} — {summary}")

        elif rtype == "Pinnacle Keys":
            await bot.database.users.modify_currency(user_id, "pinnacle_key", qty)
            lines.append(f"{emoji} **Pinnacle Keys** {display}")

        elif rtype == "Antique Tomes":
            await bot.database.users.modify_currency(user_id, "antique_tome", qty)
            lines.append(f"{emoji} **Antique Tomes** {display}")

        elif rtype == "Settler Materials":
            mat_counts = defaultdict(int)
            mat_labels = {"magma_core": "Magma Core", "life_root": "Life Root", "spirit_shard": "Spirit Shard"}
            for _ in range(qty):
                col = random.choice(list(mat_labels.keys()))
                mat_counts[col] += 1
            for col, cnt in mat_counts.items():
                await bot.database.users.modify_currency(user_id, col, cnt)
            summary = ", ".join(f"{mat_labels[c]} x{v}" for c, v in mat_counts.items())
            lines.append(f"{emoji} **Settler Materials** x{qty} — {summary}")

    await bot.database.users.modify_currency(user_id, "curio_puzzle_boxes", -1)
    return lines
