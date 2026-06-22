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
    AMARA_AUTHOR,
    ARBITER_PORTRAIT,
    ARBITER_THUMBNAIL,
    BROTHER_SOLEN_PORTRAIT,
    BROTHER_SOLEN_THUMBNAIL,
    COMBAT_VICTORY,
    DELVE_HUB,
    ELYNDRA_PORTRAIT,
    ELYNDRA_THUMBNAIL,
    HARLAN_AUTHOR,
    INVENTORY_HUB,
    LUCIEN_PORTRAIT,
    LUCIEN_THUMBNAIL,
    MASTERY_MINING,
    PARTNERS_HUB,
    POTION_SHOP_AUTHOR,
    QUEST_BOARD,
    RAGNA_PORTRAIT,
    RAGNA_THUMBNAIL,
    SERAPHINE_PORTRAIT,
    SERAPHINE_THUMBNAIL,
    SETTLEMENT_HUB,
    SLAYER_MASTER,
    SLAYER_MASTER_AUTHOR,
    TAVERN_KEEPER,
    TESSARA_PORTRAIT,
    TESSARA_THUMBNAIL,
    UPGRADE_VOIDFORGE,
    VALDRIS_PORTRAIT,
    VALDRIS_THUMBNAIL,
    VALE_PORTRAIT,
    VALE_THUMBNAIL,
    VEYRA_AUTHOR,
    YUNA_PORTRAIT,
    YUNA_THUMBNAIL,
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
        "author": "Slayer Master Kael",
        "author_icon": SLAYER_MASTER_AUTHOR,
        "description": (
            "*You want a task? Good. I don't assign easy ones.*\n\n"
            "I'll give you a species to hunt. Get out there and kill them — "
            "you'll find your targets through regular combat. "
            "Complete the task and you earn **Slayer XP** and points to spend on "
            "**Emblems** — passive boosts that carry into every fight you ever take. "
            "Five slots. Fill them. You'll feel the difference."
        ),
        "tips": [
            "You can **reroll** an unwanted task once before starting — don't waste it.",
            "Killing your assigned species gives **bonus drop rates** for the duration.",
            "Higher Slayer level unlocks tougher task types with better rewards.",
        ],
        "image": SLAYER_MASTER,
        "color": discord.Color.red(),
    },
    "shop": {
        "title": "🏪 Tavern Shop",
        "author": "Elara",
        "author_icon": POTION_SHOP_AUTHOR,
        "description": (
            "*Oh, a new face! Don't be shy — I don't bite. Much.*\n\n"
            "I keep a small but very important stock here. "
            "**Potions** are what keep you breathing out there — buy them before every fight. "
            "The cost goes up as you level, but so does how much they heal. "
            "Run out mid-combat and you'll regret it."
        ),
        "tips": [
            "**Top Up** buys only as many as you need to reach 20 — efficient and cheap.",
            "Alchemy passives can make potions stronger or add bonus effects — check `/alchemy`.",
            "Gold comes from combat. `/journey` gives bonus gold at level milestones.",
        ],
        "image": TAVERN_KEEPER,
        "color": discord.Color.gold(),
    },
    "companions": {
        "title": "🐾 Companions",
        "author": "Master Tamer Yuna",
        "author_icon": YUNA_PORTRAIT,
        "description": (
            "*Welcome back! Your little ones missed you. Well… most of them. The grumpy one is still pretending he doesn't care.*\n\n"
            "Companions are creatures that travel with you and **passively boost your stats**. "
            "Each has a passive type — ATK, DEF, Hit, Crit, Ward, Rarity, and more — and a tier that determines how strong the bonus is. "
            "Your **active companion** is always working for you in combat.\n\n"
            "Companions can be tamed through combat, earned from boss encounters, or **hatched from eggs** at your Settlement's Hatchery. "
            "Fuse two companions of the same species to produce a stronger one with a chance at a rare passive!"
        ),
        "tips": [
            "Only your **active companion** applies its passive — choose the one that fits your build.",
            "Rare passive types like **Crit** and **Ward** can be game-changing at high tiers.",
            "You can hold up to **20 companions** in your roster. Fuse duplicates to save space and gain power.",
        ],
        "image": YUNA_THUMBNAIL,
        "color": discord.Color.green(),
    },
    "settlement": {
        "title": "🏰 Settlement",
        "author": "Guildmaster Amara",
        "author_icon": AMARA_AUTHOR,
        "description": (
            "*Every great force needs a home. This is yours.*\n\n"
            "Your Settlement is your ideology's base of operations. "
            "Build structures here to generate resources automatically — "
            "**Apothecaries** brew potions, **Barracks** produce fighters, "
            "**Logging Camps** and **Quarries** supply raw materials, and much more. "
            "Assign **Workers** to each building to increase its output.\n\n"
            "As your **Town Hall** tiers up, you unlock new building slots, better upgrades, "
            "and access to endgame structures like the Black Market and Uber Shrine."
        ),
        "tips": [
            "Resources cap over time — collect regularly from the dashboard to avoid waste.",
            "**Development Turns** drive construction and upgrades. Earn them through combat and quests.",
            "Upgrade the **Town Hall** first — it unlocks everything else.",
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
        "author": "Guildmaster Amara",
        "author_icon": AMARA_AUTHOR,
        "description": (
            "*The guild attracts all kinds. Some of them are worth keeping close.*\n\n"
            "Partners are NPC allies recruited using **Guild Tickets**. "
            "Deploy one as your active partner and they'll contribute combat skills in every fight — "
            "ATK boosts, crit bonuses, survivability buffs, and more depending on who you bring.\n\n"
            "When you don't need them in combat, send them on **Dispatch** — "
            "timed missions that return gold, materials, and keys while you're busy elsewhere. "
            "Build **affinity** over time to unlock personal story content with each partner."
        ),
        "tips": [
            "Each partner has distinct **combat skills** and **dispatch skills** — pick one that fits your current goal.",
            "Skills level up by spending Guild Tickets on the partner's skill page.",
            "Dispatch accumulates for up to 48 hours — you won't miss rewards if you're offline.",
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
        "author": "Guildmaster Amara",
        "author_icon": AMARA_AUTHOR,
        "description": (
            "*I don't hand out rewards for nothing. But I do hand them out.*\n\n"
            "The board has two layers. **Daily Contracts** are short-term goals — "
            "kill X, deal Y damage, clear a boss — each one pays out **Quest Tokens** "
            "you can spend in the shop on materials you'd otherwise grind for.\n\n"
            "**Horizon Paths** are the long game. Pick one that matches where you're heading "
            "and work toward it over days or weeks. Finishing a path pays out "
            "unique rewards you can't get anywhere else. "
            "Switching paths resets your progress, so choose carefully."
        ),
        "tips": [
            "Contracts stack — finishing multiple at once gives burst token income.",
            "Rerolling a contract costs a token. Use it when the task is genuinely bad for your build.",
            "Completing quests also earns **Zeal** for your settlement — two birds, one task.",
        ],
        "image": QUEST_BOARD,
        "color": discord.Color.teal(),
    },
    "inventory": {
        "title": "🎒 Inventory & Gear",
        "author": "Armorsmith Veyra",
        "author_icon": VEYRA_AUTHOR,
        "description": (
            "*Don't just carry it. Understand it.*\n\n"
            "Your inventory holds every weapon, armor piece, and accessory you've ever found. "
            "Equip items to raise your combat stats — Attack, Defence, Crit, Ward, and more. "
            "Then **upgrade** them: Forge and Refine weapons, Temper and Reinforce armor, "
            "and push their stats well beyond what they dropped with.\n\n"
            "Gloves, Boots, and Helmets support **Essences** — powerful stat modifiers "
            "you slot in directly. Get the right essences and they'll change how your build plays entirely. "
            "Top-tier weapons can also carry a **Pinnacle** or **Utmost Passive** via the Voidforge."
        ),
        "tips": [
            "Higher **rarity** items drop with stronger base stats — worth equipping even at lower level.",
            "Upgrade costs resources, but upgrades are permanent and carry to your next fight.",
            "Essences on gloves, boots, and helmets are your mid-to-late-game build shapers.",
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
    "apex": {
        "title": "🏹 Apex Hunt",
        "author": "Apex Hunter Lucien",
        "author_icon": LUCIEN_PORTRAIT,
        "description": (
            "*You've got the look of someone who thinks they're ready for this. Good. "
            "Confidence is useful — overconfidence gets you killed.*\n\n"
            "The Apex Hunt sends you into six distinct **Zones**, each with unique monsters, "
            "terrain effects, and signature hazards. "
            "Clear a hunt to earn zone-specific **Shards** — the raw materials for upgrading your Soul Stone.\n\n"
            "**The Soul Stone** is a three-slot artifact built over time by imprinting passives extracted "
            "from your best gear. "
            "Slot two or more passives from the same category and they **Resonate** — granting combat "
            "multipliers that compound in your favor.\n\n"
            "You have **3 charges**. One regenerates every 8 hours. "
            "Don't waste them on zones you haven't prepared for."
        ),
        "tips": [
            "Each zone has a **zone effect** active during the hunt — read it before you commit.",
            "Extract passives from **max-rank gear** only; quality in determines quality out.",
            "Two or more **matching passive categories** trigger Resonance — that's where the real power is.",
        ],
        "image": LUCIEN_THUMBNAIL,
        "color": discord.Color.dark_orange(),
    },
    "ascent": {
        "title": "🗼 The Ascent",
        "author": "Tower Warden Vale",
        "author_icon": VALE_PORTRAIT,
        "description": (
            "*So you're the new fool who wants to climb the Spire. Good. "
            "The last one made it to floor 87 before the screams started. You might do better.*\n\n"
            "The Ascent is a tower of progressively harder floors. "
            "Each cleared floor grants you a **permanent stat bonus** — not just for the Ascent, "
            "but everywhere, forever.\n\n"
            "Floors are grouped into milestone tiers that unlock new bonuses at key thresholds. "
            "The higher you climb, the more your character is permanently shaped. "
            "Dying ends the run, but every bonus already earned is yours to keep."
        ),
        "tips": [
            "**Permanent bonuses persist** across all content — every floor cleared makes you stronger forever.",
            "Milestone floors are significantly harder. Come prepared before pushing into a new tier.",
            "Your gear matters here more than anywhere else. Don't attempt floors you're not ready for.",
        ],
        "image": VALE_THUMBNAIL,
        "color": discord.Color.greyple(),
    },
    "codex": {
        "title": "📖 The Codex",
        "author": "Grand Archivist Seraphine",
        "author_icon": SERAPHINE_PORTRAIT,
        "description": (
            "*Another seeker of the Codex. How many pages will you claim before the tome claims something from you?*\n\n"
            "The Codex is a wave-based survival mode. You fight through escalating waves and collect **Pages** as you go. "
            "Pages are bound into permanent **Codex Tomes** — powerful multiplier bonuses (Vitality, Wrath, Bastion, and more) "
            "that apply to your stats in all content, forever.\n\n"
            "Each run features **Boons** — per-run modifiers that shape your combat — and a **Signature**, "
            "a defining twist that makes no two runs quite the same.\n\n"
            "*The pages remember. They will stay with you long after this run ends… if you survive.*"
        ),
        "tips": [
            "Tomes are **permanent multiplier bonuses** — prioritize types that fit your build.",
            "Your **Signature** shapes the entire run; boons are temporary but stack meaningfully.",
            "Know when the run is worth pushing and when it isn't — each wave gets harder.",
        ],
        "image": SERAPHINE_THUMBNAIL,
        "color": discord.Color.dark_purple(),
    },
    "maw": {
        "title": "Maw of Infinity",
        "author": "Brother Solen",
        "author_icon": BROTHER_SOLEN_PORTRAIT,
        "description": (
            "Welcome adventurer... I have witnessed the horrors beyond the imaginable, and none have quite compared to the Maw...\n"
            "The Maw of Infinity is a **weekly world boss** that all adventurers fight together. "
            "You have up to **5 attempts per cycle** with a 20-hour cooldown between each fight. "
            "Every hit you land over 10 turns contributes to your total for that week.\n\n"
            "Each week the Maw suffers an affliction — a modifier that you can potentially exploit. "
            "Pay attention to it. Some weeks reward raw power; others something else entirely...\n\n"
            "When the cycle ends, the maw retreats, leaving behind its forbidden treasures. "
        ),
        "tips": [
            "The **weekly weakness** can dramatically shift how to earn the most contribution.",
            "You don't need to deal the most damage to earn rewards.",
        ],
        "image": BROTHER_SOLEN_THUMBNAIL,
        "color": discord.Color.dark_blue(),
    },
    "consume": {
        "title": "🦴 Consume",
        "author": "Ragna the Fleshwright",
        "author_icon": RAGNA_PORTRAIT,
        "description": (
            "*You think that's grotesque? You're wearing its arm. It's keeping you alive. "
            "That's more respect than most people get.*\n\n"
            "Monster body parts drop from combat and can be **equipped to your body slots** for permanent Max HP bonuses. "
            "You have 8 slots: head, torso, right arm, left arm, right leg, left leg, cheeks, and organs.\n\n"
            "Each part has an HP value. Equipping it replaces whatever was in that slot — "
            "the old part is destroyed, so confirm before you commit. "
            "Your inventory caps at **20 parts**. Discard what you don't need."
        ),
        "tips": [
            "Equipping a part to an occupied slot **destroys the old one** — a confirmation prompt will appear.",
            "Parts drop from all combat — your inventory fills fast. Discard lower-value pieces regularly.",
            "Max HP from parts stacks with every other HP source, including alchemy and companions.",
        ],
        "image": RAGNA_THUMBNAIL,
        "color": discord.Color.dark_red(),
    },
    "hematurgy": {
        "title": "🩸 Hematurgy",
        "author": "Valdris the Sanguine",
        "author_icon": VALDRIS_PORTRAIT,
        "description": (
            "*Primordial blood unlocks the channel. Evolutionary blood deepens it. "
            "Mutative blood — well. That's where it gets* interesting.\n\n"
            "Hematurgy is a **permanent passive upgrade system** powered by monster blood. "
            "Each passive slot must be unlocked first with **Primordial Blood**, "
            "then tiered up using **Evolutionary Blood** (T1–T5) or **Mutative Blood** (T6–T7, chase tiers only).\n\n"
            "Active passives include effects like reverberation (bonus ATK on hit), "
            "soothing venom (HP regen), haemorrhage (bleed on crit), vital resonance, and more. "
            "Higher tiers produce dramatically stronger effects."
        ),
        "tips": [
            "Unlock slots with **Primordial Blood** before you can tier them up.",
            "T6–T7 require **Mutative Blood** — rarer and only for the dedicated.",
            "Blood drops from combat. Higher-level monsters drop better blood types.",
        ],
        "image": VALDRIS_THUMBNAIL,
        "color": discord.Color.red(),
    },
    "uber": {
        "title": "⚡ Uber Encounters",
        "author": "The Arbiter",
        "author_icon": ARBITER_PORTRAIT,
        "description": (
            "*Aphrodite does not forgive hesitation. Lucifer does not forgive pride. "
            "You have been warned. The gate is open.*\n\n"
            "Uber Encounters are the pinnacle of combat. "
            "Four bosses — **Aphrodite, Lucifer, NEET, and Gemini** — each requiring a "
            "dedicated boss key earned through gameplay. They are multi-phase fights "
            "that demand full preparation.\n\n"
            "Defeating an Uber boss for the first time unlocks a **blueprint** — "
            "a prerequisite for building that boss's statue in your Settlement's Uber Shrine. "
            "Repeat victories yield rare materials used for the most powerful upgrades in the game."
        ),
        "tips": [
            "Each boss has a distinct combat style — review their modifiers before entering.",
            "**Boss keys** are earned through dispatch tasks, curios, and quest rewards.",
            "First-time kills unlock shrine blueprints. Keep fighting for crafting materials.",
        ],
        "image": ARBITER_THUMBNAIL,
        "color": discord.Color.gold(),
    },
    "paradise": {
        "title": "💎 Paradise Jewel",
        "author": "Tessara the Lapidary",
        "author_icon": TESSARA_PORTRAIT,
        "description": (
            "*A jewel is not a weapon. It is a conversation. "
            "You tell it what you need; it tells you what it's capable of. "
            "Rushing that conversation produces nothing but cracks.*\n\n"
            "The Jewel of Paradise is an **active skill system** that gives you powerful abilities "
            "usable in combat. Each jewel skill charges over multiple turns and unleashes a "
            "significant effect — burst damage, ward generation, healing, DoT, and more.\n\n"
            "Jewels are unlocked by defeating Uber bosses and can be **upgraded** using Cosmic Dust "
            "and Paradise Jewels. Higher tiers dramatically increase skill potency. "
            "Charges persist across Ascent floors and Codex waves, but reset between normal combat sessions."
        ),
        "tips": [
            "Skills charge over turns — pick a skill that fits how long your fights typically last.",
            "Upgrade jewel skills with **Cosmic Dust** and **Paradise Jewels** dropped from Uber bosses.",
            "Charges **carry between floors** in Ascent and Codex — don't waste an almost-charged skill.",
        ],
        "image": TESSARA_THUMBNAIL,
        "color": discord.Color.purple(),
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
