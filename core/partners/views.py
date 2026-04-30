from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import List, Optional
import asyncio
import discord
from discord import ButtonStyle, Interaction, ui

from core.models import Partner
from core.partners.data import PARTNER_DATA
from core.partners.mechanics import (
    MAX_COMBAT_SKILL_LEVEL,
    MAX_DISPATCH_SKILL_LEVEL,
    REROLL_COMBAT_COST,
    REROLL_DISPATCH_COST,
    generate_skill_slots,
    get_combat_upgrade_cost,
    get_dispatch_upgrade_cost,
    get_sig_combat_effect_text,
    get_sig_dispatch_effect_text,
    get_skill_effect_text,
    next_available_story,
    portrait_unlocked,
    reroll_skill,
    roll_single,
    roll_ten,
)
from core.partners.dispatch import calculate_rewards, calculate_sigmund_rewards


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

_RARITY_COLOURS = {4: 0xA8D8EA, 5: 0xFFD700, 6: 0xFF6B6B}


def _rarity_colour(rarity: int) -> int:
    return _RARITY_COLOURS.get(rarity, 0xFFFFFF)


# ---------------------------------------------------------------------------
# Dispatch item routing helpers
# ---------------------------------------------------------------------------

_MINING_ITEMS = frozenset({"iron", "coal", "gold", "platinum", "idea"})
_WOODCUTTING_ITEMS = frozenset({"oak_logs", "willow_logs", "mahogany_logs", "magic_logs", "idea_logs"})
_FISHING_ITEMS = frozenset({"desiccated_bones", "regular_bones", "sturdy_bones", "reinforced_bones", "titanium_bones"})
_GATHERING_ITEMS = _MINING_ITEMS | _WOODCUTTING_ITEMS | _FISHING_ITEMS

_RUNE_CURRENCY_MAP = {
    "refinement_rune": "refinement_runes",
    "potential_rune": "potential_runes",
    "shatter_rune": "shatter_runes",
}
_BOSS_KEY_TYPES = ["draconic_key", "angelic_key", "soul_core", "void_frag", "balance_fragment"]

# ---------------------------------------------------------------------------
# Affinity story text (placeholders — content to be filled in later)
# ---------------------------------------------------------------------------

_AFFINITY_STORIES: dict = {
    (1, 1): "**Skol | First Encounter**\n*He doesn't speak much. You fight side by side, and when the last enemy falls, he simply nods. The gesture feels heavy with something you can't name.*",
    (1, 2): "**Skol | Returning**\n*You find him studying the ruins of his old throne room. He picks up a shard of the crown. \"Some things should stay broken,\" he says, and drops it.*",
    (1, 3): "**Skol | The Weight**\n*Late after a hard battle, he admits: 'I was a cruel king. I thought strength was everything.' He pauses. 'You've shown me it isn't.'*",
    (1, 4): "**Skol | New Allegiance**\n*He kneels — not in submission, but in choice. 'You've earned what no subject ever could. My loyalty, freely given.' The broken king is whole.*",
    (2, 1): "**Eve | First Encounter**\n*She hands you a vial with a smile that doesn't quite reach her eyes. 'Don't worry — I only poison people who deserve it.' You're not entirely reassured.*",
    (2, 2): "**Eve | The Recipe**\n*You catch her adjusting a formula. When she notices you watching, she hides it. 'Curious? Good. Curiosity keeps you alive.' She still won't show you the vial.*",
    (2, 3): "**Eve | What She Keeps**\n*After a near-death battle, she stays up all night refining an antidote you didn't ask for. She leaves it on your pack without a word.*",
    (2, 4): "**Eve | The Truth**\n*'I've helped a lot of people,' she says quietly. 'And hurt just as many.' She looks at you. 'You make me want the ledger to balance. Someday.'*",
    (3, 1): "**Kay | First Encounter**\n*She acknowledges your presence with exactly one glance, then goes back to sharpening her blade. You get the sense that was a warm greeting.*",
    (3, 2): "**Kay | Distance**\n*She fights brilliantly but always alone. Afterward, you sit nearby in silence for an hour. She doesn't leave. That's something.*",
    (3, 3): "**Kay | Walls**\n*'I stopped trusting people after—' She catches herself. 'It doesn't matter.' It clearly does. You don't push. She doesn't forget that you didn't.*",
    (3, 4): "**Kay | Steady Ground**\n*She stands closer now. Not touching, not speaking — but present. For Kay, that's everything. You suspect this is what her loyalty looks like.*",
    (4, 1): "**Sigmund | First Encounter**\n*The hounds arrive first. Then him — unhurried, eyes sharp. 'They like you,' he says. One of them is already chewing your boot.*",
    (4, 2): "**Sigmund | The Pack**\n*He explains the hounds' names like they're family. They are, you realize. 'We don't abandon our own,' he says simply. You wonder if that includes you.*",
    (4, 3): "**Sigmund | The Hunt**\n*He leads you on a chase through fog and bracken. You catch nothing — but afterward he says, 'Good instincts. The hounds respect that.' High praise.*",
    (4, 4): "**Sigmund | Quarry**\n*He carves something into the hilt of your weapon. You ask what it means. 'You're part of the hunt now,' he says. The hounds howl in agreement.*",
    (5, 1): "**Velour | First Encounter**\n*The storm arrives before she does. When she steps through it, utterly dry, she smiles. 'Weather respects intent,' she explains. You don't entirely follow, but you're impressed.*",
    (5, 2): "**Velour | The Roots**\n*She teaches you to read the forest — not the trees, but what moves beneath them. 'Everything is connected,' she says. 'Even the silence has something to say.'*",
    (5, 3): "**Velour | The Tempest**\n*In a brutal fight, she calls the storm down on your enemies and shelters you within it. Afterward, you're both soaked. She laughs. You laugh too.*",
    (5, 4): "**Velour | Season's End**\n*She presses a seed into your hand. 'Plant it somewhere you call home.' You realize you haven't thought of anywhere as home in a long time. Maybe now.*",
    (6, 1): "**Flora | First Encounter**\n*The roots part for her, and she walks through like a guest in her own home. She looks at you with ancient, patient eyes. 'The World Tree sent me,' she says simply.*",
    (6, 2): "**Flora | What Grows**\n*She kneels beside a dying plant and hums. It doesn't survive — but she stays with it until it doesn't. 'Everything that ends feeds what comes next,' she says.*",
    (6, 3): "**Flora | The Heartwood**\n*She shares a memory from the World Tree — centuries old. 'I carry all of it,' she admits. 'Sometimes it's very heavy.' You sit with her in that weight.*",
    (6, 4): "**Flora | New Growth**\n*Where you've traveled together, flowers bloom out of season. She points this out quietly. 'The Tree likes you.' You think that might be the highest compliment.*",
    (7, 1): "**Yvenn | First Encounter**\n*She's already assessed your stance, your weapon grip, and three of your bad habits. 'Fixable,' she declares. You're not sure whether to be relieved or offended.*",
    (7, 2): "**Yvenn | The Standard**\n*'Perfect isn't the goal,' she says mid-drill. 'One kill better than yesterday — that's the goal.' She makes it sound simple. It isn't. She makes you try anyway.*",
    (7, 3): "**Yvenn | The Scar**\n*She shows you a scar she doesn't usually show anyone. 'That's the last mistake I made twice,' she says. 'What's yours?' You tell her. She nods. No judgment.*",
    (7, 4): "**Yvenn | Penultimate**\n*'They call me penultimate,' she says, cleaning her blade. 'Because perfection has no master.' She glances over. 'But you — you might just surprise me yet.'*",
}


def _stars(rarity: int) -> str:
    return "★" * rarity


# ---------------------------------------------------------------------------
# Partner embed builders
# ---------------------------------------------------------------------------

def _build_partner_embed(partner: Partner, items: dict) -> discord.Embed:
    """Detail embed for a single partner."""
    colour = _rarity_colour(partner.rarity)
    embed = discord.Embed(
        title=f"{_stars(partner.rarity)} {partner.name}",
        description=f"*{partner.title}*",
        colour=colour,
    )
    if partner.display_image:
        embed.set_thumbnail(url=partner.display_image)

    embed.add_field(
        name="📊 Stats",
        value=(
            f"⚔️ **{partner.total_attack}** ATK  "
            f"🛡️ **{partner.total_defence}** DEF  "
            f"❤️ **{partner.total_hp}** HP\n"
            f"Level **{partner.level}** (Lv.100 max)"
        ),
        inline=False,
    )

    # Combat skills
    co_lines = []
    for i, (key, lvl) in enumerate(partner.combat_skills, 1):
        if key:
            co_lines.append(f"`S{i}` **{key}** Lv.{lvl} — {get_skill_effect_text(key, lvl)}")
        else:
            co_lines.append(f"`S{i}` *Empty*")
    if partner.rarity >= 6 and partner.sig_combat_key:
        co_lines.append(
            f"`SIG` **Sig** Lv.{partner.sig_combat_lvl} — "
            f"{get_sig_combat_effect_text(partner.partner_id, partner.sig_combat_lvl)}"
        )
    embed.add_field(name="⚔️ Combat Skills", value="\n".join(co_lines) or "None", inline=False)

    # Dispatch skills
    di_lines = []
    for i, (key, lvl) in enumerate(partner.dispatch_skills, 1):
        if key:
            di_lines.append(f"`S{i}` **{key}** Lv.{lvl} — {get_skill_effect_text(key, lvl)}")
        else:
            di_lines.append(f"`S{i}` *Empty*")
    if partner.rarity >= 6 and partner.sig_dispatch_key:
        di_lines.append(
            f"`SIG` **Sig** Lv.{partner.sig_dispatch_lvl} — "
            f"{get_sig_dispatch_effect_text(partner.partner_id, partner.sig_dispatch_lvl)}"
        )
    embed.add_field(name="📋 Dispatch Skills", value="\n".join(di_lines) or "None", inline=False)

    # Affinity (6★ only)
    if partner.rarity >= 6:
        embed.add_field(
            name="💞 Affinity",
            value=(
                f"Encounters: **{partner.affinity_encounters}/100** | "
                f"Stories read: **{partner.affinity_story_seen}/4**"
            ),
            inline=False,
        )

    # Status
    status_parts = []
    if partner.is_active_combat:
        status_parts.append("⚔️ Active Combat Partner")
    if partner.is_dispatched:
        task = partner.dispatch_task or "?"
        status_parts.append(f"📋 Dispatched ({task})")
    if not status_parts:
        status_parts.append("Idle")
    embed.add_field(name="Status", value=" | ".join(status_parts), inline=False)

    # Shards in footer
    char_shards = items.get("char_shards", 0)
    embed.set_footer(
        text=(
            f"🎫 {items.get('guild_tickets', 0)} tickets  |  "
            f"⚔️ {items.get('combat_skill_shards', 0)} combat shards  |  "
            f"📋 {items.get('dispatch_skill_shards', 0)} dispatch shards"
            + (f"  |  🔷 {char_shards} char shards" if partner.rarity >= 6 else "")
        )
    )
    return embed


def _build_roster_embed(
    partners: List[Partner], page: int, total_pages: int, items: dict
) -> discord.Embed:
    embed = discord.Embed(
        title="🤝 Partner Roster",
        colour=0xBEBEFE,
    )
    if not partners:
        embed.description = "You have no partners yet! Use **Pull** to obtain some."
        return embed

    lines = []
    for p in partners:
        status = ""
        if p.is_active_combat:
            status = " ⚔️"
        elif p.is_dispatched:
            status = " 📋"
        lines.append(f"{_stars(p.rarity)} **{p.name}** Lv.{p.level}{status}")
    embed.description = "\n".join(lines)
    embed.set_footer(
        text=(
            f"Page {page + 1}/{total_pages}  |  "
            f"🎫 {items.get('guild_tickets', 0)} tickets"
        )
    )
    return embed


# ---------------------------------------------------------------------------
# PartnerDetailView
# ---------------------------------------------------------------------------

class PartnerDetailView(ui.View):
    def __init__(self, bot, user_id: str, partner: Partner, items: dict, roster_view):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.partner = partner
        self.items = items
        self.roster_view = roster_view
        self._update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)

    def _update_buttons(self):
        self.clear_items()
        p = self.partner

        # Set Active Combat
        if p.is_active_combat:
            btn = ui.Button(
                label="✅ Active Partner", style=ButtonStyle.success, disabled=True
            )
        else:
            btn = ui.Button(label="Set Active Combat", style=ButtonStyle.primary)
            btn.callback = self._set_active
        self.add_item(btn)

        # Dispatch
        if p.is_dispatched:
            collect_btn = ui.Button(label="Collect Dispatch", style=ButtonStyle.success)
            collect_btn.callback = self._collect_dispatch
            self.add_item(collect_btn)
        elif not p.is_active_combat:
            dispatch_btn = ui.Button(label="Send on Dispatch", style=ButtonStyle.secondary)
            dispatch_btn.callback = self._dispatch_menu
            self.add_item(dispatch_btn)

        # Manage Skills
        skills_btn = ui.Button(label="Manage Skills", style=ButtonStyle.secondary, emoji="⚙️")
        skills_btn.callback = self._open_skills
        self.add_item(skills_btn)

        # Switch Portrait (6★ with maxed affinity)
        if p.rarity >= 6 and portrait_unlocked(p.affinity_encounters, p.affinity_story_seen):
            portrait_label = "🖼️ Alt Portrait" if p.portrait_variant == 0 else "🖼️ Default Portrait"
            portrait_btn = ui.Button(label=portrait_label, style=ButtonStyle.secondary, row=1)
            portrait_btn.callback = self._toggle_portrait
            self.add_item(portrait_btn)

        # Back
        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def _set_active(self, interaction: Interaction):
        await interaction.response.defer()
        await self.bot.database.partners.set_active_combat(
            self.user_id, self.partner.partner_id
        )
        self.partner.is_active_combat = True
        self._update_buttons()
        embed = _build_partner_embed(self.partner, self.items)
        embed.colour = discord.Colour.green()
        embed.description = (embed.description or "") + "\n\n✅ Set as active combat partner!"
        await interaction.edit_original_response(embed=embed, view=self)

    async def _collect_dispatch(self, interaction: Interaction):
        await interaction.response.defer()
        p = self.partner
        is_sigmund = (
            p.sig_combat_key == "sig_co_sigmund"
            and p.sig_dispatch_lvl >= 1
            and p.dispatch_task_2 is not None
        )
        if is_sigmund:
            result = calculate_sigmund_rewards(p)
        else:
            result = calculate_rewards(p, p.dispatch_start_time or "")

        gold = result.get("gold", 0)
        exp = result.get("exp", 0)
        rolls = result.get("rolls", 0)
        items_got = result.get("items", {})

        server_id = str(interaction.guild.id)

        if gold > 0:
            await self.bot.database.users.modify_gold(self.user_id, gold)
        if exp > 0:
            await self.bot.database.users.add_exp(self.user_id, exp)

        if items_got:
            # Batch gathering materials by skill table
            mining_batch: dict = {}
            woodcutting_batch: dict = {}
            fishing_batch: dict = {}

            for item_key, qty in items_got.items():
                if item_key in _MINING_ITEMS:
                    mining_batch[item_key] = mining_batch.get(item_key, 0) + qty
                elif item_key in _WOODCUTTING_ITEMS:
                    woodcutting_batch[item_key] = woodcutting_batch.get(item_key, 0) + qty
                elif item_key in _FISHING_ITEMS:
                    fishing_batch[item_key] = fishing_batch.get(item_key, 0) + qty
                elif item_key in ("timber", "stone"):
                    try:
                        await self.bot.database.settlement.commit_production(
                            self.user_id, server_id, {item_key: qty}
                        )
                    except Exception:
                        pass
                elif item_key == "boss_key":
                    for _ in range(qty):
                        for key_type in _BOSS_KEY_TYPES:
                            if random.random() < 0.20:
                                await self.bot.database.users.modify_currency(
                                    self.user_id, key_type, 1
                                )
                elif item_key in _RUNE_CURRENCY_MAP:
                    await self.bot.database.users.modify_currency(
                        self.user_id, _RUNE_CURRENCY_MAP[item_key], qty
                    )
                elif item_key == "guild_ticket":
                    await self.bot.database.partners.add_tickets(self.user_id, qty)
                elif item_key in ("antique_tome", "pinnacle_key"):
                    await self.bot.database.users.modify_currency(self.user_id, item_key, qty)
                elif item_key == "blessed_bismuth":
                    await self.bot.database.uber.increment_blessed_bismuth(
                        self.user_id, server_id, qty
                    )
                elif item_key == "sparkling_sprig":
                    await self.bot.database.uber.increment_sparkling_sprig(
                        self.user_id, server_id, qty
                    )
                elif item_key == "capricious_carp":
                    await self.bot.database.uber.increment_capricious_carp(
                        self.user_id, server_id, qty
                    )
                elif item_key == "spirit_stone":
                    await self.bot.database.users.modify_currency(
                        self.user_id, "spirit_stones", qty
                    )
                elif item_key == "essence":
                    from database.repositories.essences import COMMON_ESSENCE_TYPES, RARE_ESSENCE_TYPES
                    pool = list(COMMON_ESSENCE_TYPES) + list(RARE_ESSENCE_TYPES)
                    for _ in range(qty):
                        await self.bot.database.essences.add(
                            self.user_id, random.choice(pool), 1
                        )
                elif item_key == "slayer_drop":
                    try:
                        await self.bot.database.slayer.add_rewards(
                            self.user_id, server_id, 0, qty
                        )
                    except Exception:
                        pass

            if mining_batch:
                try:
                    await self.bot.database.skills.update_batch(
                        self.user_id, server_id, "mining", mining_batch
                    )
                except Exception:
                    pass
            if woodcutting_batch:
                try:
                    await self.bot.database.skills.update_batch(
                        self.user_id, server_id, "woodcutting", woodcutting_batch
                    )
                except Exception:
                    pass
            if fishing_batch:
                try:
                    await self.bot.database.skills.update_batch(
                        self.user_id, server_id, "fishing", fishing_batch
                    )
                except Exception:
                    pass

        # Reset timer (keep dispatched but fresh start)
        now_str = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        await self.bot.database.partners.reset_dispatch_timer(
            self.user_id, p.partner_id, now_str
        )
        if is_sigmund:
            await self.bot.database.partners.reset_dispatch_timer_2(
                self.user_id, p.partner_id, now_str
            )

        # Build result embed
        lines = [f"⏱️ **{rolls:.1f}** reward rolls collected"]
        if gold:
            lines.append(f"💰 **{gold:,}** gold")
        if exp:
            lines.append(f"📚 **{exp:,}** XP")
        for item_key, qty in items_got.items():
            lines.append(f"📦 {qty}× **{item_key.replace('_', ' ').title()}**")

        embed = _build_partner_embed(p, self.items)
        embed.add_field(name="📋 Dispatch Rewards", value="\n".join(lines) or "Nothing yet!", inline=False)
        await interaction.edit_original_response(embed=embed, view=self)

    async def _dispatch_menu(self, interaction: Interaction):
        view = DispatchTaskSelectView(
            self.bot, self.user_id, self.partner, self.items, self
        )
        embed = discord.Embed(
            title=f"Dispatch — {self.partner.name}",
            description="Choose a task to dispatch this partner on.",
            colour=_rarity_colour(self.partner.rarity),
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def _open_skills(self, interaction: Interaction):
        view = PartnerSkillsView(
            self.bot, self.user_id, self.partner, self.items, self
        )
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    async def _toggle_portrait(self, interaction: Interaction):
        await interaction.response.defer()
        new_variant = 1 - self.partner.portrait_variant
        await self.bot.database.partners.update_portrait(
            self.user_id, self.partner.partner_id, new_variant
        )
        self.partner.portrait_variant = new_variant
        self._update_buttons()
        await interaction.edit_original_response(
            embed=_build_partner_embed(self.partner, self.items), view=self
        )

    async def _back(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=_build_roster_embed(
                self.roster_view.partners,
                self.roster_view.page,
                self.roster_view.total_pages,
                self.items,
            ),
            view=self.roster_view,
        )


# ---------------------------------------------------------------------------
# DispatchTaskSelectView
# ---------------------------------------------------------------------------

_TASK_LABELS = {"combat": "⚔️ Combat", "gathering": "⛏️ Gathering", "boss": "👑 Boss"}


class DispatchTaskSelectView(ui.View):
    def __init__(self, bot, user_id: str, partner: Partner, items: dict, detail_view):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.partner = partner
        self.items = items
        self.detail_view = detail_view
        for task, label in _TASK_LABELS.items():
            btn = ui.Button(label=label, style=ButtonStyle.secondary)
            btn.callback = self._make_callback(task)
            self.add_item(btn)
        back_btn = ui.Button(label="Cancel", style=ButtonStyle.secondary, row=1)
        back_btn.callback = self._cancel
        self.add_item(back_btn)

    def _make_callback(self, task: str):
        async def callback(interaction: Interaction):
            await interaction.response.defer()
            now_str = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            await self.bot.database.partners.set_dispatch(
                self.user_id, self.partner.partner_id, task, now_str
            )
            self.partner.is_dispatched = True
            self.partner.dispatch_task = task
            self.partner.dispatch_start_time = now_str
            self.detail_view._update_buttons()
            embed = _build_partner_embed(self.partner, self.items)
            embed.colour = discord.Colour.blue()
            embed.description = (embed.description or "") + f"\n\n📋 Dispatched on **{task}**!"
            await interaction.edit_original_response(embed=embed, view=self.detail_view)
            self.stop()
        return callback

    async def _cancel(self, interaction: Interaction):
        embed = _build_partner_embed(self.partner, self.items)
        await interaction.response.edit_message(embed=embed, view=self.detail_view)
        self.stop()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id


# ---------------------------------------------------------------------------
# PartnerSkillsView
# ---------------------------------------------------------------------------

_SKILL_SLOT_COLS = {
    "combat": [
        ("combat_slot_1", "combat_slot_1_lvl"),
        ("combat_slot_2", "combat_slot_2_lvl"),
        ("combat_slot_3", "combat_slot_3_lvl"),
    ],
    "dispatch": [
        ("dispatch_slot_1", "dispatch_slot_1_lvl"),
        ("dispatch_slot_2", "dispatch_slot_2_lvl"),
        ("dispatch_slot_3", "dispatch_slot_3_lvl"),
    ],
}


class PartnerSkillsView(ui.View):
    def __init__(self, bot, user_id: str, partner: Partner, items: dict, detail_view):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.partner = partner
        self.items = items
        self.detail_view = detail_view
        self.mode = "combat"  # "combat" or "dispatch"
        self._refresh_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    def build_embed(self) -> discord.Embed:
        p = self.partner
        embed = discord.Embed(
            title=f"⚙️ Skills — {p.name}",
            colour=_rarity_colour(p.rarity),
        )
        shards_key = "combat_skill_shards" if self.mode == "combat" else "dispatch_skill_shards"
        shards = self.items.get(shards_key, 0)
        reroll_cost = REROLL_COMBAT_COST if self.mode == "combat" else REROLL_DISPATCH_COST

        lines = [f"**{shards}** {self.mode} shards  |  Reroll costs **{reroll_cost}** shards"]
        slots = p.combat_skills if self.mode == "combat" else p.dispatch_skills
        max_lvl = MAX_COMBAT_SKILL_LEVEL if self.mode == "combat" else MAX_DISPATCH_SKILL_LEVEL

        for i, (key, lvl) in enumerate(slots, 1):
            if key:
                cost = (
                    get_combat_upgrade_cost(lvl)
                    if self.mode == "combat"
                    else get_dispatch_upgrade_cost(lvl)
                )
                cost_str = f" | Upgrade: **{cost}** shards" if cost else " | **MAX**"
                lines.append(
                    f"`S{i}` **{key}** Lv.{lvl}/{max_lvl} — "
                    f"{get_skill_effect_text(key, lvl)}{cost_str}"
                )
            else:
                lines.append(f"`S{i}` *Empty*")
        embed.description = "\n\n".join(lines)
        return embed

    def _refresh_buttons(self):
        self.clear_items()

        slots = (
            self.partner.combat_skills
            if self.mode == "combat"
            else self.partner.dispatch_skills
        )
        col_pairs = _SKILL_SLOT_COLS[self.mode]
        max_lvl = MAX_COMBAT_SKILL_LEVEL if self.mode == "combat" else MAX_DISPATCH_SKILL_LEVEL

        for i, (key, lvl) in enumerate(slots):
            key_col, lvl_col = col_pairs[i]
            if key and lvl < max_lvl:
                upgrade_btn = ui.Button(
                    label=f"Upgrade S{i + 1}", style=ButtonStyle.primary
                )
                upgrade_btn.callback = self._make_upgrade(i, key_col, lvl_col, key, lvl)
                self.add_item(upgrade_btn)

        # Reroll buttons
        for i, (key, _) in enumerate(slots):
            key_col, lvl_col = col_pairs[i]
            reroll_btn = ui.Button(
                label=f"Reroll S{i + 1}", style=ButtonStyle.secondary
            )
            reroll_btn.callback = self._make_reroll(i, key_col, lvl_col)
            self.add_item(reroll_btn)

        # Toggle combat / dispatch
        toggle_label = "Switch to Dispatch" if self.mode == "combat" else "Switch to Combat"
        toggle_btn = ui.Button(label=toggle_label, style=ButtonStyle.secondary, row=2)
        toggle_btn.callback = self._toggle_mode
        self.add_item(toggle_btn)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=2)
        back_btn.callback = self._back
        self.add_item(back_btn)

    def _make_upgrade(self, slot_idx: int, key_col: str, lvl_col: str, key: str, lvl: int):
        async def callback(interaction: Interaction):
            await interaction.response.defer()
            if self.mode == "combat":
                cost = get_combat_upgrade_cost(lvl)
                ok = await self.bot.database.partners.spend_combat_shards(self.user_id, cost)
            else:
                cost = get_dispatch_upgrade_cost(lvl)
                ok = await self.bot.database.partners.spend_dispatch_shards(self.user_id, cost)
            if not ok:
                await interaction.followup.send("Not enough shards!", ephemeral=True)
                return
            new_lvl = lvl + 1
            await self.bot.database.partners.update_skill_level(
                self.user_id, self.partner.partner_id, lvl_col, new_lvl
            )
            # Update in-memory partner
            setattr(self.partner, lvl_col, new_lvl)
            # Refresh items
            self.items = await self.bot.database.partners.get_items(self.user_id)
            self._refresh_buttons()
            await interaction.edit_original_response(embed=self.build_embed(), view=self)
        return callback

    def _make_reroll(self, slot_idx: int, key_col: str, lvl_col: str):
        async def callback(interaction: Interaction):
            await interaction.response.defer()
            if self.mode == "combat":
                ok = await self.bot.database.partners.spend_combat_shards(
                    self.user_id, REROLL_COMBAT_COST
                )
            else:
                ok = await self.bot.database.partners.spend_dispatch_shards(
                    self.user_id, REROLL_DISPATCH_COST
                )
            if not ok:
                await interaction.followup.send("Not enough shards!", ephemeral=True)
                return
            new_key = reroll_skill(self.mode, self.partner.rarity)
            await self.bot.database.partners.update_skill_slot(
                self.user_id, self.partner.partner_id,
                key_col, new_key, lvl_col, 1,
            )
            setattr(self.partner, key_col, new_key)
            setattr(self.partner, lvl_col, 1)
            self.items = await self.bot.database.partners.get_items(self.user_id)
            self._refresh_buttons()
            await interaction.edit_original_response(embed=self.build_embed(), view=self)
        return callback

    async def _toggle_mode(self, interaction: Interaction):
        self.mode = "dispatch" if self.mode == "combat" else "combat"
        self._refresh_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _back(self, interaction: Interaction):
        embed = _build_partner_embed(self.partner, self.items)
        self.detail_view._update_buttons()
        await interaction.response.edit_message(embed=embed, view=self.detail_view)
        self.stop()


# ---------------------------------------------------------------------------
# PartnerRosterView  (paginated list)
# ---------------------------------------------------------------------------

_PAGE_SIZE = 5


class PartnerRosterView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        partners: List[Partner],
        items: dict,
        main_view,
    ):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.partners = partners
        self.items = items
        self.main_view = main_view
        self.page = 0
        self.total_pages = max(1, (len(partners) + _PAGE_SIZE - 1) // _PAGE_SIZE)
        self._refresh()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    @property
    def _page_partners(self) -> List[Partner]:
        start = self.page * _PAGE_SIZE
        return self.partners[start: start + _PAGE_SIZE]

    def _refresh(self):
        self.clear_items()
        for p in self._page_partners:
            lbl = f"{_stars(p.rarity)} {p.name} Lv.{p.level}"
            btn = ui.Button(label=lbl[:80], style=ButtonStyle.secondary)
            btn.callback = self._make_select(p)
            self.add_item(btn)

        # Pagination
        prev_btn = ui.Button(label="◀", style=ButtonStyle.secondary, disabled=self.page == 0, row=2)
        prev_btn.callback = self._prev
        self.add_item(prev_btn)

        next_btn = ui.Button(
            label="▶", style=ButtonStyle.secondary,
            disabled=self.page >= self.total_pages - 1, row=2
        )
        next_btn.callback = self._next
        self.add_item(next_btn)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=2)
        back_btn.callback = self._back
        self.add_item(back_btn)

    def _make_select(self, partner: Partner):
        async def callback(interaction: Interaction):
            detail = PartnerDetailView(
                self.bot, self.user_id, partner, self.items, self
            )
            await interaction.response.edit_message(
                embed=_build_partner_embed(partner, self.items), view=detail
            )
        return callback

    async def _prev(self, interaction: Interaction):
        self.page -= 1
        self._refresh()
        await interaction.response.edit_message(
            embed=_build_roster_embed(self.partners, self.page, self.total_pages, self.items),
            view=self,
        )

    async def _next(self, interaction: Interaction):
        self.page += 1
        self._refresh()
        await interaction.response.edit_message(
            embed=_build_roster_embed(self.partners, self.page, self.total_pages, self.items),
            view=self,
        )

    async def _back(self, interaction: Interaction):
        embed = self.main_view.build_embed(self.items)
        await interaction.response.edit_message(embed=embed, view=self.main_view)
        self.stop()


# ---------------------------------------------------------------------------
# PullResultView  (shown after a pull)
# ---------------------------------------------------------------------------

class PullResultView(ui.View):
    def __init__(self, bot, user_id: str, pull_view):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.pull_view = pull_view

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    @ui.button(label="Pull Again (10 tickets)", style=ButtonStyle.primary)
    async def pull_again(self, interaction: Interaction, button: ui.Button):
        await self.pull_view._do_pull(interaction, count=10)
        self.stop()

    @ui.button(label="Back", style=ButtonStyle.secondary)
    async def back(self, interaction: Interaction, button: ui.Button):
        items = await self.bot.database.partners.get_items(self.user_id)
        await interaction.response.edit_message(
            embed=self.pull_view.build_embed(items), view=self.pull_view
        )
        self.stop()


# ---------------------------------------------------------------------------
# PullView
# ---------------------------------------------------------------------------

_RARITY_EMOJIS = {4: "💙", 5: "💛", 6: "❤️"}


class PullView(ui.View):
    def __init__(self, bot, user_id: str, main_view):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.main_view = main_view

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    def build_embed(self, items: dict) -> discord.Embed:
        embed = discord.Embed(
            title="🎫 Partner Pull",
            colour=0xFFD700,
        )
        embed.description = (
            "Spend **Guild Tickets** to recruit new partners!\n\n"
            "**Rates:** 88% ★★★★ | 11% ★★★★★ | 1% ★★★★★★\n"
            "Soft pity begins at pull 60. Hard pity at 100.\n"
            "10-pull guarantees ≥1 five-star."
        )
        embed.add_field(
            name="Your Tickets",
            value=f"🎫 **{items.get('guild_tickets', 0)}** tickets",
        )
        embed.add_field(
            name="Pity",
            value=f"**{items.get('pity_counter', 0)}/100**",
        )
        embed.set_thumbnail(url="https://i.imgur.com/Vmjfyj5.jpeg")
        return embed

    @ui.button(label="Pull ×1 (1 ticket)", style=ButtonStyle.primary)
    async def pull_one(self, interaction: Interaction, button: ui.Button):
        await self._do_pull(interaction, count=1)

    @ui.button(label="Pull ×10 (10 tickets)", style=ButtonStyle.success)
    async def pull_ten(self, interaction: Interaction, button: ui.Button):
        await self._do_pull(interaction, count=10)

    @ui.button(label="Back", style=ButtonStyle.secondary, row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        items = await self.bot.database.partners.get_items(self.user_id)
        await interaction.response.edit_message(
            embed=self.main_view.build_embed(items), view=self.main_view
        )
        self.stop()

    async def _do_pull(self, interaction: Interaction, count: int):
        ticket_cost = count
        ok = await self.bot.database.partners.spend_tickets(self.user_id, ticket_cost)
        if not ok:
            await interaction.response.send_message(
                f"Not enough tickets! You need **{ticket_cost}** 🎫.", ephemeral=True
            )
            return

        await interaction.response.defer()

        items = await self.bot.database.partners.get_items(self.user_id)
        pity = items["pity_counter"]

        # Roll
        if count == 1:
            rarity, new_pity = roll_single(pity)
            rarities = [rarity]
        else:
            rarities, new_pity = roll_ten(pity)

        await self.bot.database.partners.update_pity(self.user_id, new_pity)

        # === NEW: Determine highest rarity for banner ===
        max_rarity = max(rarities)
        banner_urls = {
            4: "https://i.imgur.com/NpUHE2b.jpeg",
            5: "https://i.imgur.com/OUrwCWk.jpeg",
            6: "https://i.imgur.com/Kfmq9Pg.jpeg",
        }
        # Step 1: Show banner (full image)
        banner_embed = discord.Embed(
            title="🎫 Recruiting...",
            description="The clerks hands you a scroll, you unfurl it...",
            colour=_rarity_colour(max_rarity),
        )
        banner_embed.set_image(url=banner_urls.get(max_rarity))
        await interaction.edit_original_response(embed=banner_embed, view=None)

        # Wait 3 seconds for dramatic effect
        await asyncio.sleep(3)

        # === Proceed with normal pull logic ===
        all_partners_by_rarity = {
            4: [pid for pid, d in PARTNER_DATA.items() if d["rarity"] == 4],
            5: [pid for pid, d in PARTNER_DATA.items() if d["rarity"] == 5],
            6: [pid for pid, d in PARTNER_DATA.items() if d["rarity"] == 6],
        }

        result_lines = []
        # For each result, assign a partner of that rarity
        all_partners_by_rarity = {
            4: [pid for pid, d in PARTNER_DATA.items() if d["rarity"] == 4],
            5: [pid for pid, d in PARTNER_DATA.items() if d["rarity"] == 5],
            6: [pid for pid, d in PARTNER_DATA.items() if d["rarity"] == 6],
        }

        result_lines = []
        shards_combat = 0
        shards_dispatch = 0
        char_shards_gained: dict[int, int] = {}
        new_partners = 0
        MAX_SIG_TIER = 5
        MAX_TICKET_GRANT = 10

        for rarity in rarities:
            pool = all_partners_by_rarity.get(rarity, all_partners_by_rarity[4])
            partner_id = random.choice(pool)
            static = PARTNER_DATA[partner_id]
            emoji = _RARITY_EMOJIS.get(rarity, "💙")

            already_owned = await self.bot.database.partners.owns_partner(
                self.user_id, partner_id
            )

            if not already_owned:
                # New partner
                co_slots = generate_skill_slots(rarity, "combat")
                di_slots = generate_skill_slots(rarity, "dispatch")
                await self.bot.database.partners.add_partner(
                    self.user_id, partner_id, co_slots, di_slots
                )
                result_lines.append(
                    f"{emoji} **NEW** — {_stars(rarity)} **{static['name']}**!"
                )
                new_partners += 1

            else:
                # Duplicate — grant shards
                if rarity == 6:
                    cur_sig = await _get_sig_lvl(self.bot, self.user_id, partner_id)
                    if cur_sig >= MAX_SIG_TIER:
                        await self.bot.database.partners.add_tickets(self.user_id, MAX_TICKET_GRANT)
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** (Sig MAX) → +{MAX_TICKET_GRANT} 🎫"
                        )
                    else:
                        char_shards_gained[partner_id] = char_shards_gained.get(partner_id, 0) + 1
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** → +1 char shard"
                        )
                else:
                    # 50/50 combat or dispatch shard
                    if random.random() < 0.5:
                        shards_combat += 1
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** → +1 combat shard ⚔️"
                        )
                    else:
                        shards_dispatch += 1
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** → +1 dispatch shard 📋"
                        )

        # Persist shard grants
        if shards_combat > 0:
            await self.bot.database.partners.add_combat_shards(self.user_id, shards_combat)
        if shards_dispatch > 0:
            await self.bot.database.partners.add_dispatch_shards(self.user_id, shards_dispatch)
        for pid, amt in char_shards_gained.items():
            await self.bot.database.partners.add_shard(self.user_id, pid, amt)

        # Build result embed
        items_after = await self.bot.database.partners.get_items(self.user_id)
        embed = discord.Embed(
            title=f"🎫 Pull Results ({count}×)",
            description="\n".join(result_lines) or "No results.",
            colour=0xFFD700,
        )
        image_url = static['image_url']
        embed.set_image(url=image_url)
        embed.set_footer(
            text=(
                f"Pity: {new_pity}/100  |  "
                f"🎫 {items_after.get('guild_tickets', 0)} tickets remaining"
            )
        )
        result_view = PullResultView(self.bot, self.user_id, self)
        await interaction.edit_original_response(embed=embed, view=result_view)


async def _get_sig_lvl(bot, user_id: str, partner_id: int) -> int:
    row = await bot.database.partners.get_partner(user_id, partner_id)
    if not row:
        return 0
    return row[11]  # sig_combat_lvl column index


# ---------------------------------------------------------------------------
# PartnerMainView  (entry point)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# AffinityView / AffinityStoryView
# ---------------------------------------------------------------------------

class AffinityStoryView(ui.View):
    def __init__(self, bot, user_id: str, partner: Partner, story_idx: int, affinity_view):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.partner = partner
        self.story_idx = story_idx
        self.affinity_view = affinity_view
        read_btn = ui.Button(label="Acknowledge", style=ButtonStyle.success)
        read_btn.callback = self._acknowledge
        self.add_item(read_btn)
        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary)
        back_btn.callback = self._back
        self.add_item(back_btn)

    def build_embed(self) -> discord.Embed:
        story_text = _AFFINITY_STORIES.get(
            (self.partner.partner_id, self.story_idx),
            "*(Story placeholder — content coming soon.)*",
        )
        embed = discord.Embed(
            title=f"💞 {self.partner.name} — Story {self.story_idx}/4",
            description=story_text,
            colour=_rarity_colour(self.partner.rarity),
        )
        if self.partner.display_image:
            embed.set_thumbnail(url=self.partner.display_image)
        return embed

    async def _acknowledge(self, interaction: Interaction):
        await interaction.response.defer()
        await self.bot.database.partners.update_affinity_story_seen(
            self.user_id, self.partner.partner_id, self.story_idx
        )
        self.partner.affinity_story_seen = self.story_idx
        for p in self.affinity_view.partners:
            if p.partner_id == self.partner.partner_id:
                p.affinity_story_seen = self.story_idx
        self.affinity_view._refresh()
        embed = self.affinity_view.build_embed()
        if portrait_unlocked(self.partner.affinity_encounters, self.story_idx):
            embed.add_field(
                name="🖼️ Portrait Unlocked!",
                value=f"Use **Switch Portrait** on {self.partner.name}'s detail page to toggle their new portrait.",
                inline=False,
            )
        else:
            embed.set_footer(text=f"The bond with {self.partner.name} grows stronger.")
        await interaction.edit_original_response(embed=embed, view=self.affinity_view)

    async def _back(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=self.affinity_view.build_embed(), view=self.affinity_view
        )

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id


class AffinityView(ui.View):
    def __init__(self, bot, user_id: str, partners_6star: list, items: dict, main_view):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.partners = partners_6star
        self.items = items
        self.main_view = main_view
        self._refresh()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    def _refresh(self):
        self.clear_items()
        if self.partners:
            options = []
            for p in self.partners:
                story_idx = next_available_story(p.affinity_encounters, p.affinity_story_seen)
                indicator = " ✨" if story_idx else ""
                portrait_tag = " 🖼️" if portrait_unlocked(p.affinity_encounters, p.affinity_story_seen) else ""
                options.append(
                    discord.SelectOption(
                        label=f"{p.name}{indicator}",
                        value=str(p.partner_id),
                        description=f"{p.affinity_encounters} encounters | {p.affinity_story_seen}/4 stories{portrait_tag}",
                    )
                )
            select = ui.Select(placeholder="Select a partner to view their story…", options=options)
            select.callback = self._on_select
            self.add_item(select)
        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back_btn.callback = self._back
        self.add_item(back_btn)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="💞 Partner Affinity", colour=0xFF6B6B)
        lines = []
        for p in self.partners:
            story_idx = next_available_story(p.affinity_encounters, p.affinity_story_seen)
            portrait_tag = " 🖼️" if portrait_unlocked(p.affinity_encounters, p.affinity_story_seen) else ""
            new_tag = " ✨ **New story!**" if story_idx else ""
            lines.append(
                f"{_stars(6)} **{p.name}** — {p.affinity_encounters} encounters "
                f"({p.affinity_story_seen}/4 stories){portrait_tag}{new_tag}"
            )
        embed.description = "\n".join(lines) if lines else "You have no 6★ partners yet."
        embed.set_footer(text="✨ = new story available  |  🖼️ = alt portrait unlocked")
        return embed

    async def _on_select(self, interaction: Interaction):
        await interaction.response.defer()
        partner_id = int(interaction.data["values"][0])
        partner = next((p for p in self.partners if p.partner_id == partner_id), None)
        if not partner:
            return
        story_idx = next_available_story(partner.affinity_encounters, partner.affinity_story_seen)
        if not story_idx:
            await interaction.followup.send(
                f"No new stories available for **{partner.name}** yet. "
                f"Take them into more combat encounters!",
                ephemeral=True,
            )
            return
        view = AffinityStoryView(self.bot, self.user_id, partner, story_idx, self)
        await interaction.edit_original_response(embed=view.build_embed(), view=view)

    async def _back(self, interaction: Interaction):
        items = await self.bot.database.partners.get_items(self.user_id)
        await interaction.response.edit_message(
            embed=self.main_view.build_embed(items), view=self.main_view
        )


# ---------------------------------------------------------------------------
# PartnerMainView  (entry point)
# ---------------------------------------------------------------------------

class PartnerMainView(ui.View):
    def __init__(self, bot, user_id: str):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)

    def build_embed(self, items: dict) -> discord.Embed:
        embed = discord.Embed(
            title="🤝 Partners",
            description=(
                "Partners are powerful adventurers that join you in combat and "
                "can be dispatched on missions while you're away.\n\n"
                "Use daily **/checkin** and combat to earn 🎫 Guild Tickets for pulls."
            ),
            colour=0xBEBEFE,
        )
        embed.add_field(
            name="💼 Inventory",
            value=(
                f"🎫 **{items.get('guild_tickets', 0)}** Guild Tickets\n"
                f"⚔️ **{items.get('combat_skill_shards', 0)}** Combat Shards\n"
                f"📋 **{items.get('dispatch_skill_shards', 0)}** Dispatch Shards"
            ),
            inline=True,
        )
        embed.add_field(
            name="🎰 Pull Rates",
            value="88% ★★★★ | 11% ★★★★★ | 1% ★★★★★★\n10 tickets per pull",
            inline=True,
        )
        embed.set_thumbnail(url="https://i.imgur.com/agWsjri.jpeg")
        return embed

    @ui.button(label="Roster", style=ButtonStyle.primary, emoji="📋")
    async def roster_btn(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        rows = await self.bot.database.partners.get_owned(self.user_id)
        items = await self.bot.database.partners.get_items(self.user_id)
        if not rows:
            await interaction.followup.send(
                "You have no partners yet! Use the **Pull** button to recruit some.",
                ephemeral=True,
            )
            return
        partners = [
            Partner.from_row(row, PARTNER_DATA[row[2]])
            for row in rows
            if row[2] in PARTNER_DATA
        ]
        view = PartnerRosterView(self.bot, self.user_id, partners, items, self)
        embed = _build_roster_embed(partners, 0, view.total_pages, items)
        await interaction.edit_original_response(embed=embed, view=view)

    @ui.button(label="Pull", style=ButtonStyle.success, emoji="🎫")
    async def pull_btn(self, interaction: Interaction, button: ui.Button):
        items = await self.bot.database.partners.get_items(self.user_id)
        pull_view = PullView(self.bot, self.user_id, self)
        await interaction.response.edit_message(
            embed=pull_view.build_embed(items), view=pull_view
        )

    @ui.button(label="Affinity", style=ButtonStyle.secondary, emoji="💞", row=1)
    async def affinity_btn(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        rows = await self.bot.database.partners.get_owned(self.user_id)
        items = await self.bot.database.partners.get_items(self.user_id)
        partners_6star = [
            Partner.from_row(row, PARTNER_DATA[row[2]])
            for row in rows
            if row[2] in PARTNER_DATA and PARTNER_DATA[row[2]]["rarity"] == 6
        ]
        view = AffinityView(self.bot, self.user_id, partners_6star, items, self)
        await interaction.edit_original_response(embed=view.build_embed(), view=view)

    @ui.button(label="Close", style=ButtonStyle.secondary, row=1)
    async def close_btn(self, interaction: Interaction, button: ui.Button):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.edit_message(view=None)
