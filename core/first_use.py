"""
core/first_use.py — First-use tutorial gate system.

Each major command checks whether the player has seen its tutorial yet.
If not, a TutorialGateView is shown first; pressing "Got it!" replaces the
message in-place with the real command view.

Usage in a cog command
----------------------
    async def _build() -> tuple[discord.Embed, BaseView]:
        view = MyView(...)
        return view.build_embed(), view

    if not await self.bot.database.tutorials.has_seen(user_id, "feature_key"):
        await self.bot.database.tutorials.mark_seen(user_id, "feature_key")
        gate = TutorialGateView(self.bot, user_id, server_id, "feature_key", build_main=_build)
        await interaction.response.send_message(embed=gate.build_embed(), view=gate)
        gate.message = await interaction.original_response()
        return

    embed, view = await _build()
    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()
"""

from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.images import (
    ALCHEMY_HUB,
    COMPANIONS_HUB,
    DELVE_HUB,
    INVENTORY_HUB,
    PARTNERS_HUB,
    QUEST_BOARD,
    SETTLEMENT_HUB,
    SLAYER_MASTER,
    TAVERN_KEEPER,
    MASTERY_MINING,
)

# ---------------------------------------------------------------------------
# Tutorial content
# ---------------------------------------------------------------------------
# Each entry: title, description, tips (list of strings), image, color
# ---------------------------------------------------------------------------

TUTORIALS: dict[str, dict] = {
    "slayer": {
        "title": "⚔️ Slayer Tasks",
        "description": (
            "The Slayer Master assigns you a species to hunt. "
            "Completing tasks earns **Slayer XP** and currency you can spend on "
            "powerful **Emblems** — passive stat boosts that persist across all combat. "
            "You have 5 Emblem slots; filling them makes a noticeable difference."
        ),
        "tips": [
            "You can **reroll** an unwanted task once before starting.",
            "Killing your assigned species gives **bonus drop rates** during the task.",
            "Higher Slayer level unlocks tougher (and more rewarding) task types.",
        ],
        "image": SLAYER_MASTER,
        "color": discord.Color.red(),
    },
    "shop": {
        "title": "🏪 Tavern Shop",
        "description": (
            "Elara keeps a modest but essential stock. "
            "**Potions** are your primary combat lifeline — buy them here using gold. "
            "Potion cost scales with your level, but so does their effectiveness. "
            "Keep your stock topped up before heading into combat."
        ),
        "tips": [
            "The **Top Up** option buys only as many as you need to reach 20.",
            "Some alchemy passives augment potions — unlock them via `/alchemy`.",
            "Gold is earned from combat. `/journey` grants bonus gold at milestones.",
        ],
        "image": TAVERN_KEEPER,
        "color": discord.Color.gold(),
    },
    "companions": {
        "title": "🐾 Companions",
        "description": (
            "Companions are creatures that travel with you and **passively boost your stats**. "
            "Each has a passive type (ATK, DEF, Hit, Crit, Ward, Rarity…) and a tier — "
            "higher tiers give stronger bonuses. "
            "You can tame monsters through combat or earn special companions from boss encounters."
        ),
        "tips": [
            "Only your **active companion** applies its passive — choose wisely.",
            "Boss companions (Aphrodite, Lucifer…) have rare passive types.",
            "You can hold up to **20 companions** in your roster at once.",
        ],
        "image": COMPANIONS_HUB,
        "color": discord.Color.green(),
    },
    "settlement": {
        "title": "🏰 Settlement",
        "description": (
            "Your Settlement is your ideology's home base. "
            "Build structures to generate resources automatically — "
            "**Apothecaries** produce potions, **Barracks** train fighters, and more. "
            "Assign Workers to each building to increase their output rate."
        ),
        "tips": [
            "Resources accumulate over time — collect them regularly to avoid waste.",
            "Upgrade your **Town Hall** to unlock additional building slots.",
            "The **Hatchery** (unlocked later) lets you incubate monster eggs.",
        ],
        "image": SETTLEMENT_HUB,
        "color": discord.Color.dark_green(),
    },
    "gather": {
        "title": "⛏️ Gathering Skills",
        "description": (
            "Mining, Fishing, and Woodcutting let you collect resources used in "
            "upgrades and crafting throughout the game. "
            "Each skill has its own **tool tier** — upgrading your tools unlocks "
            "better materials and larger yields per action."
        ),
        "tips": [
            "Resources are collected on a **cooldown** — check back regularly.",
            "Earning **Mastery XP** unlocks permanent passive bonuses per skill.",
            "Higher-tier tools also reduce the chance of coming back empty-handed.",
        ],
        "image": MASTERY_MINING,
        "color": discord.Color.dark_orange(),
    },
    "delve": {
        "title": "🪨 The Delve",
        "description": (
            "Delve sends you on a mining expedition through procedurally generated layers. "
            "Each layer is a hazard — **Gas Pockets, Magma Flows, and Gravel** drain your "
            "Stability. Reach an **Ore Vein** to gather rare Obsidian Shards. "
            "If Stability hits zero, the run ends early."
        ),
        "tips": [
            "Upgrade **Fuel** to reach deeper layers with richer ore.",
            "Upgrade **Structure** to reduce stability damage from hazards.",
            "Upgrade **Sensor** to reveal upcoming layers before you commit.",
        ],
        "image": DELVE_HUB,
        "color": discord.Color.dark_grey(),
    },
    "partner": {
        "title": "🤝 Partners",
        "description": (
            "Partners are powerful NPC allies recruited via **Guild Tickets**. "
            "Deploy one in combat to benefit from their passive skills — ATK boosts, "
            "crit bonuses, slayer synergies, and more. "
            "Send others on **Dispatch tasks** to earn resources and keys while you're away."
        ),
        "tips": [
            "Partner **affinity** grows each fight — reach milestones to unlock story content.",
            "Skills improve by spending Guild Tickets on the partner's skill page.",
            "Dispatch tasks run passively — queue them up and collect later.",
        ],
        "image": PARTNERS_HUB,
        "color": discord.Color.blurple(),
    },
    "alchemy": {
        "title": "⚗️ Alchemy",
        "description": (
            "Alchemy lets you attach **passive effects to your potions**. "
            "Passives can heal more, guarantee hits, boost damage, or reduce incoming damage. "
            "Roll new passives in the **Potion Lab**, then upgrade them as your Alchemy level grows."
        ),
        "tips": [
            "You start with **1 passive slot** — unlock more by raising your Alchemy level.",
            "Rerolling a passive costs Spirit Stones — save them for passives you want to upgrade.",
            "Some passives (Bottled Courage, Linger) change how combat fundamentally plays out.",
        ],
        "image": ALCHEMY_HUB,
        "color": discord.Color.purple(),
    },
    "quests": {
        "title": "📜 Quests",
        "description": (
            "Quests give you long-term goals that reward you for playing every part of the game. "
            "Choose a **Horizon Path** that fits your playstyle — each tracks specific activities "
            "and pays out unique materials on completion. "
            "Daily and weekly **contracts** refresh automatically for ongoing rewards."
        ),
        "tips": [
            "Your Horizon Path can be changed, but progress resets when you switch.",
            "Contracts stack up — complete several at once for burst rewards.",
            "Quest rewards often include rare materials not available elsewhere.",
        ],
        "image": QUEST_BOARD,
        "color": discord.Color.teal(),
    },
    "inventory": {
        "title": "🎒 Inventory & Gear",
        "description": (
            "Your Inventory holds all your weapons, armor, and accessories. "
            "Equip items to raise your combat stats, then **upgrade** them at the Forge "
            "to push them further. "
            "Gloves, Boots, and Helmets support **Essences** — slotting these can dramatically "
            "change your build."
        ),
        "tips": [
            "Higher **rarity** items drop with better base stats and stronger passives.",
            "Each gear piece has a **passive ability** — read them carefully when equipping.",
            "Upgrading gear costs resources but permanently improves the item.",
        ],
        "image": INVENTORY_HUB,
        "color": discord.Color.blue(),
    },
}


# ---------------------------------------------------------------------------
# Gate view
# ---------------------------------------------------------------------------


class TutorialGateView(BaseView):
    """Shows a tutorial embed for ``feature_key``.

    Pressing **Got it!** calls ``build_main`` (an async coroutine that returns
    ``(embed, view)``), then replaces this message in-place with the main view.

    ``build_main`` is an async callable with signature:
        ``async () -> tuple[discord.Embed, BaseView]``
    """

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        feature_key: str,
        *,
        build_main,
    ):
        super().__init__(bot, user_id, server_id, timeout=180)
        self._feature_key = feature_key
        self._build_main = build_main
        self._processing = False

        btn = ui.Button(
            label="Got it! Let's go →",
            style=ButtonStyle.success,
            emoji="▶️",
        )
        btn.callback = self._continue_cb
        self.add_item(btn)

    async def _continue_cb(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        main_embed, main_view = await self._build_main()
        await interaction.response.edit_message(embed=main_embed, view=main_view)
        # interaction.message is the message we just edited — hand it to the new view.
        main_view.message = interaction.message
        self.stop()

    def build_embed(self) -> discord.Embed:
        data = TUTORIALS[self._feature_key]
        embed = discord.Embed(
            title=data["title"],
            description=data["description"],
            color=data.get("color", discord.Color.blue()),
        )
        if tips := data.get("tips"):
            embed.add_field(
                name="Quick Tips",
                value="\n".join(f"• {t}" for t in tips),
                inline=False,
            )
        if img := data.get("image"):
            embed.set_thumbnail(url=img)
        embed.set_footer(text="✨ First visit — this message only appears once.")
        return embed
