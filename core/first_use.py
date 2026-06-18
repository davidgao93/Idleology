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
    COMBAT_VICTORY,
    COMPANIONS_HUB,
    DELVE_HUB,
    ELYNDRA_PORTRAIT,
    ELYNDRA_THUMBNAIL,
    HARLAN_AUTHOR,
    INVENTORY_HUB,
    MASTERY_MINING,
    PARTNERS_HUB,
    QUEST_BOARD,
    SETTLEMENT_HUB,
    SLAYER_MASTER,
    TAVERN_KEEPER,
    UPGRADE_VOIDFORGE,
)

# ---------------------------------------------------------------------------
# Tutorial content
# ---------------------------------------------------------------------------
# Each entry: title, description, tips (list of strings), image, color
# ---------------------------------------------------------------------------

TUTORIALS: dict[str, dict] = {
    "combat": {
        "title": "⚔️ Combat",
        "description": (
            "Every fight puts your stats against a monster's. "
            "**Attack** determines how often and hard you hit; "
            "**Defence** reduces how often they hit you. Percent DR and Flat DR reduces how hard. "
            "**Hit chance** is also affected by your accuracy and the monster's evasion — "
            "a miss deals no damage. Land a **Critical Hit** for bonus damage. "
            "Use **Potions** to restore HP during the fight, though it costs you a turn. "
            "If things look grim, you can always **Flee** - better safe than dead."
        ),
        "tips": [
            "Higher **ATK** and **DEF** come from your equipped gear — upgrade it regularly.",
            "Equip yourself with powerful passives.",
            "Potions scale with your level, so they stay useful all game.",
        ],
        "image": COMBAT_VICTORY,
        "color": discord.Color.red(),
    },
    "slayer": {
        "title": "⚔️ Slayer Tasks",
        "description": (
            "Slayer Master Kael assigns you a species to hunt. You can encounter them via combat. "
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
            "Only your **active companion(s)** applies passives — choose wisely.",
            "Rare companions have rare passive types.",
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
            "Resources can be collected passively or actively through minigames.",
            "Artisan Mastery lets you unlock permanent passive bonuses per skill.",
            "Higher-tier tools give you access to higher tier materials.",
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
            "Send one on **Dispatch** to earn resources and keys while you're away."
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
        "author": "Master Alchemist Elyndra",
        "description": (
            "*You've wandered into my lab. How fortunate — for you.*\n\n"
            "Alchemy is not mere potion-mixing. It is the art of coaxing power out of "
            "reluctant materials, and occasionally out of catastrophe.\n\n"
            "My laboratory handles three disciplines:\n"
            "**Transmutation** — shift your gathered resources up or down the tier ladder. "
            "Efficient. Reliable. Occasionally expensive, but that is the cost of ambition.\n"
            "**Synthesis** — convert keys, essences, and other materials into Cosmic Dust, "
            "or use Dust to produce something more immediately useful. "
            "The process is straightforward. The results are not always.\n"
            "**The Potion Lab** — my masterwork. Use *Distill Elixir* to run a "
            "distillation ritual that imprints a powerful passive onto your potions. "
            "Choose your reagents carefully. The Crimson ones in particular have… opinions.\n\n"
            "Level up to unlock additional passive slots. "
            "You may one day have as many as five active distilled passives. "
            "Try not to waste them."
        ),
        "tips": [
            "Cosmic Dust is earned through various activities — it's your primary distillation resource, so don't waste it.",
            "Each reagent color has a different risk profile. Verdant is safe. Crimson is not.",
            "Higher alchemy level unlocks more passive slots and better transmutation rates.",
        ],
        "image": ELYNDRA_THUMBNAIL,
        "author_icon": ELYNDRA_PORTRAIT,
        "color": discord.Color.purple(),
    },
    "quests": {
        "title": "📜 Quests",
        "description": (
            "Quests give you daily goals that reward you for playing. "
            "Choose a **Horizon Path** that's a long term goal "
            "and pays out unique materials on completion. "
        ),
        "tips": [
            "Your Horizon Path can be changed, but progress resets when you switch.",
            "Contracts stack up — complete several at once for burst rewards.",
        ],
        "image": QUEST_BOARD,
        "color": discord.Color.teal(),
    },
    "inventory": {
        "title": "🎒 Inventory & Gear",
        "description": (
            "Your Inventory holds all your weapons, armor, and accessories. "
            "Equip items to raise your combat stats, then **upgrade** them "
            "to push them further. "
            "Later on, Gloves, Boots, and Helmets support **Essences** — slotting these can dramatically "
            "change your build."
        ),
        "tips": [
            "Higher **quality** items drop with better base stats.",
            "Upgrading gear costs resources but permanently improves the item.",
        ],
        "image": INVENTORY_HUB,
        "color": discord.Color.blue(),
    },
    "voidforge": {
        "title": "🌌 The Voidforge",
        "author": "Master Smith Harlan",
        "description": (
            "*You've come to the Voidforge. Good. Let me explain exactly what you're getting into — "
            "there's no undoing this once the ritual begins.*\n\n"
            "The Voidforge channels the essence trapped inside a **sacrifice weapon** — "
            "a weapon you no longer need — and attempts to imprint its passive onto your target weapon. "
            "The sacrifice weapon is consumed regardless of outcome. That's the cost of the void.\n\n"
            "**What is a Passive?**\n"
            "Every weapon can carry a primary passive ability — a bonus that activates in combat. "
            "Think of it as the weapon's soul. Forging and refining can improve a weapon's numbers, "
            "but they cannot change its passive. Only the Voidforge can.\n\n"
            "**What is a Pinnacle Passive?**\n"
            "A second passive slot, rarer and more powerful. Once you've imprinted a Pinnacle, "
            "the Voidforge costs double. It's worth it.\n\n"
            "**What is an Utmost Passive?**\n"
            "A third and final slot — only reachable after a Pinnacle exists. "
            "The rarest configuration a weapon can have. Few smiths ever see one.\n\n"
            "**The Three Outcomes (each attempt):**\n"
            "— 🌌 **Success (25%):** The sacrifice's passive is written into your weapon as "
            "a Pinnacle Passive. If a Pinnacle already exists, it becomes the Utmost instead.\n"
            "— 🔄 **Chaos (25%):** The essence overpowers the ritual. "
            "Your weapon's **main passive is overwritten** with the sacrifice's passive.\n"
            "— ❌ **Failure (50%):** The void consumes the essence entirely. "
            "Your target weapon is untouched, but the sacrifice is still gone.\n\n"
            "*I've seen veterans lose three weapons in a row chasing a Pinnacle. "
            "I've also seen one succeed on the first try. The void doesn't negotiate.*"
        ),
        "tips": [
            "Pick your sacrifice weapon carefully — its **passive** is what transfers, not its stats.",
            "If your weapon has no Pinnacle yet, a Success writes the Pinnacle slot.",
            "With a Pinnacle already present, a Success writes the Utmost — costs 10M gold.",
            "A Void Key is consumed on every attempt, win or lose.",
        ],
        "image": UPGRADE_VOIDFORGE,
        "author_icon": HARLAN_AUTHOR,
        "color": discord.Color.dark_purple(),
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
        super().__init__(bot, user_id, server_id)
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
        if author := data.get("author"):
            embed.set_author(name=author, icon_url=data.get("author_icon"))
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
