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
from core.emojis import (
    ASCENT_EMOJI,
    CODEX_TOME_EMOJI,
    CONSUME_ICON,
    GEAR_BACKPACK,
    HEMATURGY_ICON,
    INFINITE_MAW,
    NETHER_MARKET_PLUNDER,
    PARADISE_JEWEL_UNCUT,
    UBER_EMOJI,
    VOID_KEY,
)
from core.images import (
    AMARA_AUTHOR,
    ARBITER_PORTRAIT,
    ARBITER_THUMBNAIL,
    BROTHER_SOLEN_PORTRAIT,
    BROTHER_SOLEN_THUMBNAIL,
    COMBAT_VICTORY,
    DELVE_HUB,
    ELIZA_PORTRAIT,
    ELIZA_THUMBNAIL,
    ELYNDRA_PORTRAIT,
    ELYNDRA_THUMBNAIL,
    HARLAN_AUTHOR,
    INVENTORY_HUB,
    LUCIEN_PORTRAIT,
    LUCIEN_THUMBNAIL,
    MASTERY_MINING,
    PARTNERS_HUB,
    POTION_SHOP,
    POTION_SHOP_AUTHOR,
    QUEST_BOARD,
    RAGNA_PORTRAIT,
    RAGNA_THUMBNAIL,
    SERAPHINE_PORTRAIT,
    SERAPHINE_THUMBNAIL,
    SETTLEMENT_HUB,
    SLAYER_MASTER,
    SLAYER_MASTER_AUTHOR,
    TESSARA_PORTRAIT,
    TESSARA_THUMBNAIL,
    UPGRADE_VOIDFORGE,
    VALDRIS_PORTRAIT,
    VALDRIS_THUMBNAIL,
    VALE_PORTRAIT,
    VALE_THUMBNAIL,
    VEX_PORTRAIT,
    VEX_THUMBNAIL,
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
        "author": "Guildmaster Amara",
        "author_icon": AMARA_AUTHOR,
        "description": (
            "*I'm not going to hold your hand through this. But I will make sure you "
            "leave this hall knowing what you're walking into.*\n\n"
            "Combat is straightforward: your **Attack** determines how hard and how often you land hits; "
            "your **Defence** affects how hard it hits back. "
            "**Percent DR** and **Flat DR** reduce incoming damage further. "
            "Miss a hit and you deal nothing — accuracy matters. "
            "Land a **Critical Hit** and you deal bonus damage.\n\n"
            "You carry **Potions**. Use them mid-fight to restore HP — but it costs you a turn, "
            "so pick your moment. If it's going badly, **Flee**. There's no shame in survival."
        ),
        "tips": [
            "Gear is what separates a survivor from a casualty. Upgrade it early and often.",
            "Potions scale with level — they stay relevant all game. Keep them stocked.",
            "Fleeing costs you nothing. Dying costs you everything.",
        ],
        "image": COMBAT_VICTORY,
        "color": discord.Color.red(),
    },
    "slayer": {
        "title": "⚔️ Slayer Tasks",
        "author": "Slayer Master Kael",
        "author_icon": SLAYER_MASTER_AUTHOR,
        "description": (
            "*Another adventurer just out of the woodwork? Come closer, let me inspect that pitiful frame of yours...*\n\n"
            "Not bad. You'll do. Slayer is the art of killing not just monsters, but the right type of monster."
            " I'll give you a species to hunt. Your job is to kill a specific number of them - "
            "you'll find your targets through regular combat. "
            "Complete the task and you earn **Slayer XP** and some favor with me.\n\n"
            "Here, take this Emblem. It absorbs the very essence of the slayer monsters you kill, granting you boons or challenges to face.\n"
            "As you become a master of slayer yourself, you'll unlock more slots. Fill them. You'll feel the difference."
        ),
        "tips": [
            "Don't hesistate to take a look at the Slayer mastery tree to see what goals you want to work towards. I'll make it worth your while.",
            "Some tasks are harder than others, maybe pick the one that's doable.",
            "Feed your emblem well and often.",
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
            "You can hold up to 20 potions - **Top Up** buys only as many as you need.",
            "Alchemy passives can make potions stronger or add bonus effects — check `/alchemy`.",
        ],
        "image": POTION_SHOP,
        "color": discord.Color.gold(),
    },
    "companions": {
        "title": "🐾 Companions",
        "author": "Master Tamer Yuna",
        "author_icon": YUNA_PORTRAIT,
        "description": (
            "*Welcome adventurer! I'm Yuna, Master Tamer and keeper of the Companion Ranch.*\n\n"
            "Companions are creatures that travel with you and **passively boost your stats**. "
            "Each has a passive type — ATK, DEF, Hit, Crit, Ward, Rarity, and more — and a tier that determines how strong the bonus is. "
            "Your **active companion(s)** are always working for you in combat.\n\n"
            "Companions can be tamed through combat or rarely from boss encounters. "
            "You can even fuse two companions together!\n\n"
            "Companions can gain levels via XP, and you gain companion XP from discarding unwanted equipment (more upgrades = more xp). "
            "The Companion Ranch down at the Settlement can also produce XP cookies to feed to your pets."
        ),
        "tips": [
            "Only your **active companion(s)** applies its passives — choose the one that fits your build.",
            "Rare passive types like Special Rarity are extremely powerful and game-changing.",
            "You can hold up to **20 companions** in your roster. Fuse duplicates or let some go to manage your limit.",
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
            "Your Settlement is what makes this ideology real — it's a central base for that ideology's followers. "
            "**Logging Camps** and **Quarries** generate materials automatically. "
            "The **Nursery** produce followers. Assign staff, take Development Turns, "
            "and watch it compound.\n\n"
            "**Zeal** is the fuel you earn from fighting and quests. Spend it to take a **Development Turn**, "
            "which advances construction, upgrades, and events. "
            "As your **Town Hall** tiers up, new building slots unlock — eventually you're working with "
            "a Black Market, War Camps, and Watchtowers that amplify everything around them. "
            "Oh, and ask Spritz if you're not sure what to do, she's over there."
        ),
        "tips": [
            "Earn Zeal through combat and quests.",
            "Workers are the multiplier — more workers in a building means more output.",
            "Maybe just read the Wiki page for this one...",
        ],
        "image": SETTLEMENT_HUB,
        "color": discord.Color.dark_green(),
    },
    "gather": {
        "title": "⛏️ Gathering Skills",
        "author": "Master Smith Harlan",
        "author_icon": HARLAN_AUTHOR,
        "description": (
            "*I'll be brief — you've got work to do.*\n\n"
            "Every weapon and piece of armor I forge depends on what comes out of the ground, the forest, "
            "and the water. **Mining**, **Woodcutting**, and **Fishing** — that's where your supply chain starts.\n\n"
            "Upgrade your **tools** when you can. Better tools reach better veins, richer timber, deeper water. "
            "The materials from higher-tier nodes are categorically different from what you pull with iron. "
            "Quantity matters, but quality matters more.\n\n"
            "**Artisan Mastery** unlocks passive bonuses that compound over time — yield increases, "
            "rare material chances, synergy between skills. The more you invest in a skill, "
            "the more it pays back."
        ),
        "tips": [
            "Tool tier is the most important upgrade. Don't neglect it.",
            "Artisan Mastery rewards long-term investment — start early, collect the returns later.",
            "The three skills cross-pollinate. Progress in one might unlock bonuses in others.",
        ],
        "image": MASTERY_MINING,
        "color": discord.Color.dark_orange(),
    },
    "delve": {
        "title": "🪨 The Delve",
        "author": "Master Smith Harlan",
        "author_icon": HARLAN_AUTHOR,
        "description": (
            "*Listen carefully. I've lost workers in those tunnels. "
            "I won't lose another because they skipped the briefing.*\n\n"
            "The Delve is an expedition into unstable mining layers. Pay the permit fee and drill down. "
            "Every layer is a hazard — **Gas Pockets**, **Magma Flows**, **Gravel** — and each drains "
            "your **Stability**. Hit zero and the run collapses; you come out with nothing.\n\n"
            "**Ore Veins** are what you're after. They yield rare Obsidian Shards you won't find anywhere else. "
            "You'll pick up regular ore along the way as well.\n\n"
            "Three upgrades matter: **Fuel** (how deep you go), **Structure** (damage you absorb), "
            "and **Sensor** (preview the next layer before committing). Invest in all three."
        ),
        "tips": [
            "Sensor is underrated — knowing what's ahead is worth more than it costs.",
            "Deeper layers carry richer ore. Better Fuel means more Obsidian Shards per run.",
            "Every point of stability you save through Structure is one more layer you can push through.",
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
            "Partners are NPC allies recruited with **Guild Tickets**. "
            "Set one as your active partner and they contribute **combat skills** in every fight — "
            "attack boosts, crit bonuses, survivability buffs. The skills they bring depend entirely "
            "on who you recruit, so read before you commit.\n\n"
            "When combat isn't the priority, put one on **Dispatch** — timed missions that run in the "
            "background and return gold, materials, and keys while you're busy elsewhere. "
            "Dispatch accumulates for up to 48 hours. Check back when it makes sense.\n\n"
            "Rarer partners carry stronger signature skills. The grind for them is real, "
            "but so is the return."
        ),
        "tips": [
            "Each partner rolls both **combat** and **dispatch** skills — pick the one that fits your current priority.",
            "Rarer partners carry more powerful signature skills. They're worth chasing.",
            "Dispatch accumulates for up to 48 hours. Don't let it sit idle.",
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
            "The process is straightforward.\n"
            "**The Potion Lab** — my masterwork. Use *Distill Elixir* to run a "
            "distillation experiment that imprints a powerful passive onto your potions.\n\n"
            "Level up to unlock additional potion passive slots. "
            "You may one day have as many as five active."
        ),
        "tips": [
            "Cosmic Dust is earned through various activities — it's your primary distillation resource, so don't waste it.",
            "Each reagent color has a different risk profile.",
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
            "The board runs two tracks. **Daily Contracts** are short-term — kill X, deal Y damage, "
            "clear a boss. Finish them and you earn **Quest Tokens**, which you spend in the shop on "
            "materials you'd otherwise grind for. A token spent rerolling a terrible contract "
            "is a token well spent.\n\n"
            "**Horizon Paths** are the long game. Pick the one that aligns with where you're already "
            "heading and let your progress feed it passively. Each path pays a unique reward tied to "
            "that system — supplemental, not the main event, but worth doing regardless. "
            "Switching paths resets your progress, so commit before you start walking."
        ),
        "tips": [
            "You can normally take up to 3 contracts a day.",
            "Rerolling a contract costs a token. Use it when the task is genuinely bad.",
        ],
        "image": QUEST_BOARD,
        "color": discord.Color.teal(),
    },
    "inventory": {
        "title": f"{GEAR_BACKPACK} Inventory & Gear",
        "author": "Armorsmith Veyra",
        "author_icon": VEYRA_AUTHOR,
        "description": (
            "*Don't just carry it. Understand it.*\n\n"
            "Your inventory holds every weapon, armor piece, and accessory you've ever found. "
            "Equip items to raise your combat stats — Attack, Defence, Crit, Ward, and more. "
            "Then **upgrade** them: Forge and Refine weapons, Temper and Reinforce armor, "
            "and push their stats well beyond what they dropped with.\n\n"
            "You'll eventually encounter Calcified monsters, monstrosities that drop **Essences** — powerful stat modifiers "
            "you can use on your equipment. Get the right essences and they'll change how your combat works entirely. "
            "Down the line, artefacts like the Voidforge can imprint additional passives."
        ),
        "tips": [
            "Weapons have different quality, some are better than others.",
            "Upgrade quickly and often to keep up with the every growing threat of stronger monsters.",
            "Build around different passive archetypes to shape your build.",
        ],
        "image": INVENTORY_HUB,
        "color": discord.Color.blue(),
    },
    "voidforge": {
        "title": f"{VOID_KEY} The Voidforge",
        "author": "Master Smith Harlan",
        "description": (
            "*You've come to the Voidforge. Good. Let me explain exactly what you're getting into — "
            "there's no undoing this once the ritual begins.*\n\n"
            "The Voidforge channels the essence trapped inside a **sacrifice weapon** — "
            "a weapon you no longer need — and attempts to imprint its passive onto your target weapon. "
            "The sacrifice weapon is consumed regardless of outcome. That's the cost of the void.\n\n"
            "**What is a Pinnacle Passive?**\n"
            "A second passive slot to hold the passive from another weapon.\n\n"
            "**What is an Utmost Passive?**\n"
            "A third and final slot — only reachable after a Pinnacle exists. "
            "The rarest configuration a weapon can have. Few smiths ever see one.\n\n"
            "**The Three Outcomes (each attempt):**\n"
            f"— {VOID_KEY} **Success (25%):** The sacrifice's passive is written into your weapon as "
            "a Pinnacle Passive. If a Pinnacle already exists, it becomes the Utmost instead.\n"
            "— 🔄 **Chaos (25%):** The essence overpowers the ritual. "
            "Your weapon's **main passive is overwritten** with the sacrifice's passive.\n"
            "— ❌ **Failure (50%):** The void consumes the essence entirely. "
            "Your target weapon is untouched, but the sacrifice is still gone.\n\n"
            "*I've seen veterans lose many weapons in a row chasing a Pinnacle. "
            "I've also seen one succeed on the first try. Congrats. Happy for you.*"
        ),
        "tips": [
            "Pick your sacrifice weapon carefully — its **passive** is what transfers, not its stats.",
            "If your weapon has no Pinnacle yet, a Success writes the Pinnacle slot.",
            "With a Pinnacle already present, a Success writes the Utmost.",
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
            "You have **5 charges**. One regenerates every 2 hours. "
            "Don't waste them on zones you haven't prepared for."
        ),
        "tips": [
            "Each zone has a **zone effect** active during the hunt — read it before you commit.",
            "Two or more **matching passive categories** trigger Resonance.",
        ],
        "image": LUCIEN_THUMBNAIL,
        "color": discord.Color.dark_orange(),
    },
    "ascent": {
        "title": f"{ASCENT_EMOJI} The Ascent",
        "author": "Tower Warden Vale",
        "author_icon": VALE_PORTRAIT,
        "description": (
            "*So you're the new fool who wants to climb the Spire. Good. "
            "The last one made it to floor 87 before the screams started. You might do better.*\n\n"
            "The Ascent is a tower of progressively harder floors. "
            "The tower awards you with **permanent stat bonuses**.\n\n"
            "Floors are grouped into milestone tiers that unlock new bonuses at key thresholds. "
            "The higher you climb, the more your power grows. "
            "Dying ends the run, but every bonus already earned is yours to keep."
        ),
        "tips": [
            "Your gear matters here more than anywhere else. Don't attempt floors you're not ready for.",
        ],
        "image": VALE_THUMBNAIL,
        "color": discord.Color.greyple(),
    },
    "codex": {
        "title": f"{CODEX_TOME_EMOJI} The Codex",
        "author": "Grand Archivist Seraphine",
        "author_icon": SERAPHINE_PORTRAIT,
        "description": (
            "*Another seeker of the Codex. How many pages will you claim before the tome claims something from you?*\n\n"
            "The Codex is a wave-based survival mode. You fight through escalating waves and collect **Pages** as you go. "
            "Pages are bound into permanent **Codex Tomes** — providing powerful multiplier bonuses.\n\n"
            "Each run features **Boons** — per-run modifiers that shape your combat — and a **Signature**, "
            "a defining twist that makes no two runs quite the same.\n\n"
            "*The pages remember. They will stay with you long after this run ends… if you survive.*"
        ),
        "tips": [
            "Tomes are **permanent multiplier bonuses** — they make you exponentially stronger.",
            "There are no potions allowed in the Codex, so come prepared.",
            "Dying isn't a complete loss, you simply move on to the next chapter.",
        ],
        "image": SERAPHINE_THUMBNAIL,
        "color": discord.Color.dark_purple(),
    },
    "maw": {
        "title": f"{INFINITE_MAW} Maw of Infinity",
        "author": "Brother Solen",
        "author_icon": BROTHER_SOLEN_PORTRAIT,
        "description": (
            "*I have witnessed horrors beyond the imaginable. "
            "None of them have compared to the Maw. I say that not to frighten you — "
            "only so you understand what you are agreeing to.*\n\n"
            "The Maw of Infinity is a **weekly world boss** that all adventurers fight together. "
            "You have up to **5 attempts per cycle**, with a cooldown between each fight. "
            "Every hit you land across your 10-turn encounter is recorded — your total contribution "
            "for the week accumulates with every visit.\n\n"
            "When the cycle ends and the Maw retreats, those who struck true collect their rewards: "
            "Curios, Guild Tickets, and more for all participants. "
            "The three who landed the heaviest blows receive something extra.\n\n"
            "*It cannot be killed. It never dies. But it can be hurt. "
            "That has to be enough. It usually is.*"
        ),
        "tips": [
            "Each cycle the Maw carries a **weakness**. Study it before you fight — some weeks it changes everything.",
            "You don't need to deal the most damage to earn rewards. Participation matters.",
        ],
        "image": BROTHER_SOLEN_THUMBNAIL,
        "color": discord.Color.dark_blue(),
    },
    "consume": {
        "title": f"{CONSUME_ICON} Consume",
        "author": "Ragna the Fleshwright",
        "author_icon": RAGNA_PORTRAIT,
        "description": (
            "Welcome to my shop welp, so you've come to learn about eating monsters, eh?\n\n"
            "Slain monsters occasionally drop body parts that can be **consumed** for permanent Max HP bonuses. "
            "You have 8 slots:\n\n"
            "Each part has an HP value. Equipping it replaces whatever was in that slot — "
            "the old part is destroyed, so confirm before you commit. "
            "Your inventory caps at **20 parts**. Discard what you don't need."
        ),
        "tips": [
            "Equipping a part to an occupied slot **destroys the old one**.",
            "Parts drop from all combat — your inventory fills fast. Discard or recycle lower-value pieces regularly.",
        ],
        "image": RAGNA_THUMBNAIL,
        "color": discord.Color.dark_red(),
    },
    "hematurgy": {
        "title": f"{HEMATURGY_ICON} Hematurgy",
        "author": "Valdris the Sanguine",
        "author_icon": VALDRIS_PORTRAIT,
        "description": (
            "*Oh — oh you actually came. Wonderful. Sit down, don't touch that, and do NOT open the jar on the left.*\n\n"
            "Hematurgy is a **permanent passive upgrade system** — living power, encoded directly into your blood. "
            "To begin, you need **Primordial Blood**, the raw substrate that opens a passive channel in your body. "
            "Once unlocked, you tier it up with **Evolutionary Blood** (T1–T5) — controlled adaptation, very elegant — "
            "or **Mutative Blood** for higher tiers. Those are… less controlled. I find that exciting, makes my blood curl.\n\n"
            "Now here's the part most people miss: the finest blood does not come from wild kills. "
            "You raise them. Build a **Hatchery** in your Settlement, incubate their eggs, "
            "then release the creatures yourself and *slay them*. "
            "The blood from a creature you personally hunted — one you raised from nothing — "
            "that is categorically superior. The fear-response alone does something remarkable to the yield."
        ),
        "tips": [
            "Build the **Hatchery** settlement building and release eggs yourself — that's the best blood pipeline.",
            "Unlock slots with **Primordial Blood** first. No channel, no power. That's just biology.",
            "Higher tier passives need **Mutative Blood** and a certain tolerance for unpredictability. You'll be fine. Probably.",
        ],
        "image": VALDRIS_THUMBNAIL,
        "color": discord.Color.red(),
    },
    "uber": {
        "title": f"{UBER_EMOJI} Uber Encounters",
        "author": "The Arbiter",
        "author_icon": ARBITER_PORTRAIT,
        "description": (
            "*Aphrodite does not forgive hesitation. Lucifer does not forgive pride. "
            "You have been warned. The gate is open.*\n\n"
            "Uber Encounters are the pinnacle of combat. "
            "Four bosses — **Aphrodite, Lucifer, NEET, and Gemini** — each requiring a dedicated "
            "boss key. They are tough encounters that will test every build decision you have made. "
            "There are no shortcuts.\n\n"
            "Defeating each boss can yield rare drops, including a **blueprint** for their statue in your "
            "Settlement's Uber Shrine. Repeat victories yield the rare materials that power the most "
            "significant upgrades for your gear. You will need to return many times.\n\n"
            "*I do not grant access to those who are unprepared. "
            "If you are here, I have judged you ready. Although is that a new entity approaching?.. oh my...*"
        ),
        "tips": [
            "Each boss has a distinct combat style — review their modifiers before entering.",
        ],
        "image": ARBITER_THUMBNAIL,
        "color": discord.Color.gold(),
    },
    "rite": {
        "title": "🕯️ The Rite of Convergence",
        "author": "The Arbiter",
        "author_icon": ARBITER_PORTRAIT,
        "description": (
            "*You come seeking passage into the Rite of Convergence. "
            "I am merely the one who watches the door.*\n\n"
            "Beyond it wait five faces you may recognize — old horrors, "
            "reborn wrong. What you beat before will not help you here. "
            "They have had a long time to change.\n\n"
            "No one passes through carrying half a key. And nothing that "
            "happens beyond this door can be undone once you've stepped "
            "through it — win, lose, or turn back, the door does not "
            "open twice."
        ),
        "tips": [
            "Enter only when you're ready. There is no stepping out for supplies partway through.",
            "What aid the road offers is offered once per respite — choose deliberately.",
            "The five are not equally forgiving. Some builds will find one crueler than the rest.",
        ],
        "image": ARBITER_THUMBNAIL,
        "color": discord.Color.dark_purple(),
    },
    "paradise": {
        "title": f"{PARADISE_JEWEL_UNCUT} Paradise Jewel",
        "author": "Tessara the Lapidary",
        "author_icon": TESSARA_PORTRAIT,
        "description": (
            "*A jewel is not a weapon. It is a conversation. "
            "You tell it what you need; it tells you what it's capable of. "
            "Rushing that conversation produces nothing but cracks.*\n\n"
            "The Jewel of Paradise is an **active skill system** that gives you powerful abilities "
            "usable in combat. Each jewel skill charges over multiple turns and unleashes a "
            "significant effect — burst damage, ward generation, healing, DoT, and more.\n\n"
            "Jewels are unlocked by defeating corrupted monsters and can be **upgraded** using Cosmic Dust "
            "and Paradise Jewels. Higher tiers dramatically increase skill potency."
        ),
        "tips": [
            "Skills charge over turns — pick a skill that fits how long your fights typically last.",
            "Upgrade jewel skills with **Cosmic Dust** and **Paradise Jewels**.",
        ],
        "image": TESSARA_THUMBNAIL,
        "color": discord.Color.purple(),
    },
    "nether_market": {
        "title": f"{NETHER_MARKET_PLUNDER} Nether Market",
        "author": "Vex, the Fence",
        "author_icon": VEX_PORTRAIT,
        "description": (
            "Hello there! You, yes you, I'm talking to you. Come closer... I'll show you something interesting.\n\n"
            "The Nether Market trades in **curiosities** whose prices drift up and down "
            "every hour — buy low, hold, and sell back when the rotation turns in your favor. "
            "Only 3 items are tradeable at a time, so patience pays.\n\n"
            "You can also **browse** other players' (and a few NPCs') stashes and attempt to **plunder** "
            "a cut of their holdings by cracking a hidden 4-digit code. "
            "Win and you walk away with goods and a Nether Mark; lose and you walk away empty-handed."
        ),
        "tips": [
            "You can only sell an item back while it's one of the 3 currently active offers. Don't say I didn't warn ya!",
            "Plunder charges are limited and regenerate over time — pick your targets carefully.",
            "A successful plunder shields the target from further attempts for a while — the wealthier they are, the longer it lasts.",
            "Spend Nether Marks in the Cutpurse (offense) and Strongbox (defense) trees to get better at plundering, or harder to be plundered.",
        ],
        "image": VEX_THUMBNAIL,
        "color": discord.Color.dark_purple(),
    },
    "prestige": {
        "title": "👑 Prestige",
        "author": "Eliza",
        "author_icon": ELIZA_PORTRAIT,
        "description": (
            "*Ah, another adventurer with more gold than they know what to do with. "
            "Let's fix that, shall we?*\n\n"
            "I deal exclusively in legacy — the things that make you unmistakably **you** "
            "the moment you walk into a room. Five things, to be precise:\n\n"
            "**Avatars** — animated portraits, browsed by gallery. Own one outright and swap freely after.\n"
            "**Titles** — a custom tag of your own choosing, shown right beside your name.\n"
            "**Emblem** — pick any emoji from the bot's own collection to display beside you.\n"
            "**Monument** — etch a quote into the settlement's Hall of Fame, for as long as you're remembered.\n"
            "**Rename** — tired of the name you registered with? I can fix that too.\n\n"
            "None of it is cheap. All of it is worth it."
        ),
        "tips": [
            "Titles and Emblems show up beside your name in combat and on your Adventurer License — pick something you'll want to see often.",
            "Avatars and Emblems are owned once and freely swappable after — Titles and Renames charge again every time you change them.",
            "Check the **Prices** tab before you buy — everything here is gold well spent, but it adds up fast.",
        ],
        "image": ELIZA_THUMBNAIL,
        "color": discord.Color(0xBEBEFE),
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
        if isinstance(main_view, discord.ui.LayoutView):
            # Content lives inside main_view's own components — passing a
            # classic embed alongside a Components V2 view is rejected by
            # Discord, so main_embed is unused in this branch.
            await interaction.response.edit_message(embed=None, view=main_view)
        else:
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
        embed.set_footer(text="First visit — this message only appears once.")
        return embed
