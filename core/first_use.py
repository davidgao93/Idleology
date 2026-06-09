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
    COMBAT_VICTORY,
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
    "combat": {
        "title": "⚔️ Combat",
        "description": (
            "Every fight puts your stats against a monster's. "
            "**Attack** determines how hard you hit; **Defence** reduces how hard they hit you. "
            "**Hit chance** is affected by your accuracy and the monster's evasion — "
            "a miss deals no damage. Land a **Critical Hit** for bonus damage. "
            "Use **Potions** to restore HP during the fight. "
            "If things look grim, you can always **Flee** — though it costs you a turn."
        ),
        "tips": [
            "Higher **ATK** and **DEF** come from your equipped gear — upgrade it regularly.",
            "Each **Weapon passive** activates under specific conditions — read them in `/gear`.",
            "Potions scale with your level, so they stay useful all game.",
        ],
        "image": COMBAT_VICTORY,
        "color": discord.Color.red(),
    },
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
            "Alchemy is your hub for resource transmutation, Cosmic Dust synthesis/disenchanting, "
            "and — most importantly — **Distilling powerful potion passives**. "
            "Use the Potion Lab's Distill Elixir for the 9-step system (see Passives tutorial)."
        ),
        "tips": [
            "Level up to unlock more passive slots and better transmutation/synthesis rates.",
            "Cosmic Dust (from disenchanting keys/essences) powers the new Distillation system.",
            "Transmute gathering resources here for upgrade materials.",
        ],
        "image": ALCHEMY_HUB,
        "color": discord.Color.purple(),
    },
    "passives": {
        "title": "🧪 Potion Passives (Distillation)",
        "description": (
            "Potion passives are now crafted exclusively via the **9-step Distillation** system in the Potion Lab. "
            "First choose a core 'skill' (powerful base effect like Panacea, Eclipse Strike, Astral Aegis, etc.). "
            "The three options each display a brief description of what the passive does together with the possible roll ranges for its strength and duration. "
            "Then over 8 reagent steps you tune Duration Power (how long it lasts) and Value Power (how strong it is). "
            "Each reagent step draws three special properties from a wide weighted pool (middle outcomes are common; extremely powerful effects like 'all future steps free' or 'this step cannot decrease anything' are rare). "
            "The properties are shown in the embed so you know exactly what each colored choice will do. Buttons preview your dust after the choice, e.g. (68->60). "
            "Background resolution (nothing / inc or dec on duration or power) is modified by the property you picked (slightly lucky doubles good rolls and takes the better; very lucky re-rolls on bad results and picks the best-of; safe steps never decrease, etc.). "
            "The final passive is placed in a slot and is far more encounter-changing than legacy effects."
        ),
        "tips": [
            "Core chosen in step 1 is fixed for the run; reagents only tune its two power axes.",
            "At every reagent step the three special properties (cost mods, lucky, safe, free steps, guarantees, very rare powerful bonuses...) are freshly sampled and displayed — read them before clicking.",
            "🟢 Verdant tends toward stable value. 🔵 Astral balanced. 🔴 Crimson higher variance and dramatic events.",
            "Track the two accumulators and active effects in the embed. Dust balance is always visible.",
            "Distilled passives go into slots (Alchemy level unlocks more) and are the only way to obtain powerful potion passives now.",
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
