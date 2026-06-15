import asyncio
import random

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.codex.mechanics import (
    CodexBoon,
    CodexChapter,
    apply_per_wave_boons,
    apply_respite_boon,
    apply_signature_modifier,
    calculate_run_fragments,
    calculate_wave_monster_level,
    get_wave_modifier_counts,
    restore_clean_stats,
    roll_boons,
)
from core.combat import jewel_engine as _je
from core.combat import ui as combat_ui
from core.combat.calc.hit_calc import calculate_crit_chance
from core.combat.combat_log import CombatLogger
from core.combat.economy.experience import ExperienceManager
from core.combat.economy.rewards import calculate_rewards
from core.combat.mobgen.gen_mob import generate_ascent_monster
from core.combat.turns import engine
from core.images import CODEX_BOON, CODEX_CHAPTERS
from core.models import Monster, Player


async def _generate_codex_wave_monster(
    player: Player, chapter: CodexChapter, wave_num: int
) -> Monster:
    """Generates a monster for a Codex wave, then injects chapter-level monster buffs."""
    from core.combat.mobgen.modifier_data import make_modifier

    m_level = calculate_wave_monster_level(player, chapter, wave_num)
    n_mods, b_mods = get_wave_modifier_counts(wave_num, chapter.difficulty)
    monster = Monster(
        name="",
        level=0,
        hp=0,
        max_hp=0,
        xp=0,
        attack=0,
        defence=0,
        modifiers=[],
        image="",
        flavor="",
        is_boss=(wave_num == 7),
    )
    monster = await generate_ascent_monster(player, monster, m_level, n_mods, b_mods)

    # Inject chapter-level monster buffs — guarantee a minimum tier for each named modifier.
    # If the monster already rolled the same modifier at a higher tier, the higher tier wins.
    for mod_name, tier in chapter.monster_mods:
        existing = next((m for m in monster.modifiers if m.name == mod_name), None)
        if existing is None:
            monster.modifiers.append(make_modifier(mod_name, m_level, force_tier=tier))
        elif existing.tier < tier:
            monster.modifiers.remove(existing)
            monster.modifiers.append(make_modifier(mod_name, m_level, force_tier=tier))

    return monster


class BoonButton(ui.Button):
    def __init__(self, boon: CodexBoon, run_view: "CodexRunView", row: int):
        label = boon.label
        if boon.downside_label:
            label = f"{label} / ⚠️ {boon.downside_label}"
        super().__init__(
            label=label[:80],
            style=ButtonStyle.primary,
            row=row,
        )
        self.boon = boon
        self.run_view = run_view

    async def callback(self, interaction: Interaction):
        await self.run_view.handle_boon_choice(interaction, self.boon)


class RerollButton(ui.Button):
    def __init__(self, run_view: "CodexRunView"):
        super().__init__(
            label="Reroll Choices",
            style=ButtonStyle.secondary,
            emoji="🔄",
            row=2,
        )
        self.run_view = run_view

    async def callback(self, interaction: Interaction):
        await self.run_view.handle_reroll(interaction)


class CodexRunView(BaseView):
    """
    Manages a complete Codex run (5 chapters × 7 waves each).
    State machine: "combat" | "respite" | "chapter_transition" | "done"
    """

    def __init__(
        self,
        bot,
        user_id: str,
        player: Player,
        chapters: list[CodexChapter],
        initial_monster: Monster,
        start_logs: dict,
        chapter_wave_baseline: dict = None,
    ):
        super().__init__(bot, user_id, timeout=600)
        self.player = player
        self.chapters = chapters
        self.chapter_idx = 0
        self.wave_num = 1
        self.monster = initial_monster
        self.logs = start_logs or {}

        # Baseline snapshot taken after chapter setup (signature + boons applied) but before
        # combat passives fire. Reset at the start of every wave so that sturdy/omnipotent/
        # absorb etc. don't compound across waves.
        self.chapter_wave_baseline: dict = chapter_wave_baseline or {}

        # Respite interaction guard — prevents double-processing from rapid clicks
        self._boon_processing: bool = False

        # Run-level state
        self.active_boons: list[CodexBoon] = []
        self.run_state: dict = {"fragment_multiplier": 1.0, "sig_nullify_next": False}
        self.reroll_used_chapters: set[int] = (
            set()
        )  # chapter indices that consumed their reroll
        self.chapters_cleared = 0
        self.waves_cleared_this_run = 0
        self.deaths = 0
        self.chapter_start_xp = (
            0  # XP total at the start of the current chapter (for rollback)
        )
        self.chapter_start_gold = (
            0  # Gold total at the start of the current chapter (for rollback)
        )
        self.cleared_chapter_indices: set[int] = (
            set()
        )  # which chapter positions were cleared
        self.page_drops: list[int] = []  # chapter ids where a page dropped

        # XP/gold accumulation across the run
        self.cumulative_xp = 0
        self.cumulative_gold = 0

        self.combat_logger = CombatLogger(player, initial_monster)
        self.combat_logger.log_combat_start(player, initial_monster)

    @property
    def current_chapter(self) -> CodexChapter:
        return self.chapters[self.chapter_idx]

    # ------------------------------------------------------------------
    # Embed builders
    # ------------------------------------------------------------------

    def _combat_embed(self) -> discord.Embed:
        chapter = self.current_chapter
        title = (
            f"📖 Codex — {chapter.name} | Wave {self.wave_num}/7 "
            f"(Chapter {self.chapter_idx + 1}/5)"
        )
        embed = combat_ui.create_combat_embed(
            self.player, self.monster, self.logs, title_override=title
        )
        embed.color = discord.Color.dark_purple()
        sig_label = chapter.signature_label
        sig_desc = chapter.signature_description
        if (
            self.run_state.get("sig_nullify_next")
            and self.chapter_idx < len(self.chapters) - 1
        ):
            next_name = self.chapters[self.chapter_idx + 1].name
            embed.set_footer(
                text=(
                    f"Signature: {sig_label} — {sig_desc} | "
                    f"⚡ Next chapter '{next_name}' signature NULLIFIED"
                )
            )
        else:
            embed.set_footer(text=f"Signature: {sig_label} — {sig_desc}")
        return embed

    def _snapshot_wave_baseline(self):
        """Snapshot base stats after chapter/boon setup but before combat passives fire.
        Restored at the top of every wave so combat-start passives (sturdy, omnipotent,
        absorb, juggernaut, gilded_hunger, diabolic_pact, cursed_precision, Enfeeble,
        Impenetrable) don't compound across waves."""
        self.chapter_wave_baseline = {
            "bonus_crit": self.player.bonus_crit,
            "bonus_max_hp": self.player.bonus_max_hp,
            "combat_ward": self.player.combat_ward,
            "atk_multiplier": self.player.atk_multiplier,
            "def_multiplier": self.player.def_multiplier,
            "crit_multiplier": self.player.crit_multiplier,
            "chapter_hit_penalty": self.player.chapter_hit_penalty,
            "chapter_pdr_reduction": self.player.chapter_pdr_reduction,
            "chapter_ward_gen_mult": self.player.chapter_ward_gen_mult,
            "chapter_crit_dmg_reduction": self.player.chapter_crit_dmg_reduction,
            "chapter_hp_entry_pct": self.player.chapter_hp_entry_pct,
        }

    def _restore_wave_baseline(self):
        """Reset per-combat bonuses and restore the post-setup snapshot before
        combat passives fire.  base_attack/defence are never mutated so only
        the bonus accumulator and multipliers need restoring."""
        if not self.chapter_wave_baseline:
            return
        self.player.reset_combat_bonus()
        self.player.bonus_crit = self.chapter_wave_baseline["bonus_crit"]
        self.player.bonus_max_hp = self.chapter_wave_baseline.get("bonus_max_hp", 0)
        self.player.combat_ward = self.chapter_wave_baseline["combat_ward"]
        self.player.atk_multiplier = self.chapter_wave_baseline.get(
            "atk_multiplier", 1.0
        )
        self.player.def_multiplier = self.chapter_wave_baseline.get(
            "def_multiplier", 1.0
        )
        self.player.crit_multiplier = self.chapter_wave_baseline.get(
            "crit_multiplier", 1.0
        )
        self.player.chapter_hit_penalty = self.chapter_wave_baseline.get(
            "chapter_hit_penalty", 0
        )
        self.player.chapter_pdr_reduction = self.chapter_wave_baseline.get(
            "chapter_pdr_reduction", 0.0
        )
        self.player.chapter_ward_gen_mult = self.chapter_wave_baseline.get(
            "chapter_ward_gen_mult", 1.0
        )
        self.player.chapter_crit_dmg_reduction = self.chapter_wave_baseline.get(
            "chapter_crit_dmg_reduction", 0.0
        )
        self.player.chapter_hp_entry_pct = self.chapter_wave_baseline.get(
            "chapter_hp_entry_pct", 0.0
        )
        # Re-apply HP entry cap each wave (bonus_max_hp already restored above so total_max_hp is correct)
        if self.player.chapter_hp_entry_pct > 0:
            cap = int(self.player.total_max_hp * (1 - self.player.chapter_hp_entry_pct))
            self.player.current_hp = min(self.player.current_hp, cap)

    def _projected_ward(self) -> int:
        """Ward the player will have at the start of the next wave."""
        return self.chapter_wave_baseline.get("combat_ward", self.player.combat_ward)

    def _run_modifiers_text(self) -> str:
        """Compact summary of all active run-level stat modifiers from boons and their downsides."""
        p = self.player
        parts = []

        atk_boost = sum(b.value for b in self.active_boons if b.type == "atk_boost")
        def_boost = sum(b.value for b in self.active_boons if b.type == "def_boost")
        crit_boost = sum(
            int(b.value) for b in self.active_boons if b.type == "crit_boost"
        )
        fdr_boost = sum(
            int(b.value) for b in self.active_boons if b.type == "fdr_boost"
        )
        ward_boost = sum(b.value for b in self.active_boons if b.type == "ward_boost")
        page_rate_boost = sum(
            b.value for b in self.active_boons if b.type == "page_rate_boost"
        )

        atk_pen_pct = sum(
            b.downside_value
            for b in self.active_boons
            if b.downside_type == "atk_penalty"
        )
        def_pen_pct = sum(
            b.downside_value
            for b in self.active_boons
            if b.downside_type == "def_penalty"
        )
        crit_pen_pw = sum(
            int(b.downside_value)
            for b in self.active_boons
            if b.downside_type == "crit_penalty"
        )

        if atk_boost or atk_pen_pct:
            net = atk_boost - atk_pen_pct
            parts.append(f"ATK {'+' if net >= 0 else ''}{net:.0f}%")
        if p.run_atk_penalty:
            parts.append(f"ATK −{p.run_atk_penalty}")

        if def_boost or def_pen_pct:
            net = def_boost - def_pen_pct
            parts.append(f"DEF {'+' if net >= 0 else ''}{net:.0f}%")
        if p.run_def_penalty:
            parts.append(f"DEF −{p.run_def_penalty}")

        total_crit_pen = crit_pen_pw + p.run_crit_penalty
        if crit_boost or total_crit_pen:
            net = crit_boost - total_crit_pen
            parts.append(f"Crit {'+' if net >= 0 else ''}{net}")

        if fdr_boost:
            parts.append(f"FDR +{fdr_boost}")
        if ward_boost:
            parts.append(f"Ward +{ward_boost:.0f}%")
        if page_rate_boost:
            parts.append(f"Page Rate +{page_rate_boost:.0f}%")

        frag_mult = self.run_state.get("fragment_multiplier", 1.0)
        frag_pct = round((frag_mult - 1.0) * 100)
        if frag_pct:
            parts.append(f"Fragments {'+' if frag_pct >= 0 else ''}{frag_pct}%")

        if p.run_max_hp_bonus:
            parts.append(
                f"Max HP {'+' if p.run_max_hp_bonus >= 0 else ''}{p.run_max_hp_bonus:,}"
            )

        if self.run_state.get("guaranteed_page_this_chapter"):
            parts.append("📄 Page (this chapter)")
        if self.run_state.get("sig_nullify_next"):
            parts.append("⚡ Sig Nullified")

        return " · ".join(parts) if parts else "None"

    def _respite_embed(
        self, boons: list[CodexBoon], reroll_available: bool = False
    ) -> discord.Embed:
        chapter = self.current_chapter
        p = self.player

        atk = p.get_total_attack()
        def_ = p.get_total_defence()
        eff_max_hp = p.get_effective_max_hp()
        fdr = p.get_total_fdr()
        pdr = p.get_total_pdr()

        # Hit chance — mirrors profile_ui logic
        _HIT_BASE_PCT = 60
        hit_pct = (
            int(p.equipped_weapon.hit_chance * 100)
            if p.equipped_weapon
            else _HIT_BASE_PCT
        )
        hit_ascension = p.get_ascension_bonuses()["hit"] if p.ascension_unlocks else 0
        hit_deadeye = 0
        if p.equipped_weapon:
            for _passive in (
                p.equipped_weapon.passive,
                p.equipped_weapon.p_passive,
                p.equipped_weapon.u_passive,
            ):
                if _passive and "deadeye" in _passive.lower():
                    try:
                        hit_deadeye += int(_passive.lower().split("_")[-1]) * 4
                    except (ValueError, IndexError):
                        pass
        hit_companion = p._get_companion_bonus("hit")
        hit_emblem = p.get_emblem_bonus("accuracy") * 2
        hit_total = (
            hit_pct
            + hit_ascension
            + hit_deadeye
            + hit_companion
            + hit_emblem
            - p.chapter_hit_penalty
        )
        # NEET glove corrupted essence forces accuracy to 0 in combat
        if p.get_glove_corrupted_essence() == "neet":
            hit_total = 0

        # Crit chance — includes piercing passive + partner bonus (matches engine)
        crit_chance = calculate_crit_chance(p)

        # Crit multiplier — reduced by chapter dullness modifier if active
        crit_multi = p.get_weapon_crit_multi()
        if p.chapter_crit_dmg_reduction > 0:
            crit_multi *= 1 - p.chapter_crit_dmg_reduction

        block = p.get_total_block()
        evasion = p.get_total_evasion()

        hp_line = f"❤️ **{p.current_hp:,}/{eff_max_hp:,}**"
        proj_ward = self._projected_ward()
        if proj_ward > 0:
            hp_line += f"  🔮 Ward (next wave): **{proj_ward:,}**"
        stats_block = (
            f"⚔️ ATK: **{atk:,}**  🛡️ DEF: **{def_:,}**\n"
            f"{hp_line}\n"
            f"🎯 Hit: **{hit_total}%**  Crit: **{crit_chance}%**  ×{crit_multi:.2f}"
        )
        if fdr > 0 or pdr > 0:
            stats_block += f"\n🔒 FDR: **{fdr}**  🪨 PDR: **{pdr}%**"
        if block > 0 or evasion > 0:
            be_parts = []
            if block > 0:
                be_parts.append(f"🛡️ Block: **{block}%**")
            if evasion > 0:
                be_parts.append(f"💨 Evasion: **{evasion}%**")
            stats_block += "\n" + "  ".join(be_parts)

        reroll_hint = (
            "\n*(🔄 Reroll available — one use per chapter)*"
            if reroll_available
            else ""
        )
        embed = discord.Embed(
            title=f"⚗️ Respite — {chapter.name}",
            description=(
                f"A moment of stillness between the waves.\n\n"
                f"{stats_block}\n\n"
                f"Choose a boon:{reroll_hint}"
            ),
            color=discord.Color.teal(),
        )
        embed.set_thumbnail(url=CODEX_BOON)
        for i, boon in enumerate(boons, 1):
            field_name = f"Option {i}: {boon.label}"
            if boon.downside_label:
                field_name += f"  ⚠️ {boon.downside_label}"
            embed.add_field(name=field_name, value=boon.description, inline=False)
        embed.add_field(
            name="📊 Run Modifiers",
            value=self._run_modifiers_text(),
            inline=False,
        )
        return embed

    def _chapter_clear_embed(
        self, xp: int, gold: int, page_dropped: bool
    ) -> discord.Embed:
        chapter = self.current_chapter
        embed = discord.Embed(
            title=f"✅ Chapter Complete — {chapter.name}",
            description="All 7 waves cleared!",
            color=discord.Color.green(),
        )
        embed.add_field(name="📚 XP", value=f"{xp:,}", inline=True)
        embed.add_field(name="💰 Gold", value=f"{gold:,}", inline=True)
        if page_dropped:
            embed.add_field(
                name="📄 Codex Page", value="A Codex Page dropped!", inline=False
            )
        next_idx = self.chapter_idx + 1
        if next_idx < len(self.chapters):
            next_ch = self.chapters[next_idx]
            nullified = self.run_state.get("sig_nullify_next", False)
            sig_info = (
                "~~" + next_ch.signature_label + "~~ (Nullified)"
                if nullified
                else (f"{next_ch.signature_label}: {next_ch.signature_description}")
            )
            embed.add_field(
                name=f"📖 Next: {next_ch.name}",
                value=sig_info,
                inline=False,
            )
            embed.set_footer(text="Continuing in 4 seconds...")
        else:
            embed.set_footer(text="Run complete! Finalising in 4 seconds...")
        return embed

    def _summary_embed(
        self, fragments: int, pages_dropped: int, exp_changes: dict
    ) -> discord.Embed:
        is_perfect = self.deaths == 0 and self.chapters_cleared == 5
        if is_perfect:
            description = (
                "✨ **Perfect Codex Clear!** All 5 chapters without a single death."
            )
        elif self.chapters_cleared == 5:
            description = "All 5 chapters cleared!"
        else:
            description = f"{self.chapters_cleared}/5 chapters cleared."
        embed = discord.Embed(
            title="📕 Codex Run Complete",
            description=description,
            color=discord.Color.gold() if is_perfect else discord.Color.blurple(),
        )
        embed.add_field(
            name="📚 Total XP", value=f"{self.cumulative_xp:,}", inline=True
        )
        embed.add_field(
            name="💰 Total Gold", value=f"{self.cumulative_gold:,}", inline=True
        )
        if exp_changes["ascensions_gained"]:
            embed.add_field(
                name="✨ Ascensions",
                value=str(exp_changes["ascensions_gained"]),
                inline=True,
            )
        embed.add_field(name="🔷 Fragments Earned", value=str(fragments), inline=True)
        if pages_dropped > 0:
            embed.add_field(
                name="📄 Codex Pages", value=str(pages_dropped), inline=True
            )
        if self.deaths > 0:
            embed.add_field(
                name="💀 Deaths",
                value=f"{self.deaths} (−{min(50, self.deaths * 10)}% Fragments)",
                inline=True,
            )
        if exp_changes["msgs"]:
            embed.add_field(
                name="Level Ups", value="\n".join(exp_changes["msgs"]), inline=False
            )
        chapters_text = "\n".join(
            f"{'✅' if i in self.cleared_chapter_indices else '❌'} {ch.name}"
            for i, ch in enumerate(self.chapters)
        )
        embed.add_field(name="Chapters", value=chapters_text, inline=False)
        embed.set_thumbnail(url=CODEX_CHAPTERS)
        return embed

    # ------------------------------------------------------------------
    # Wave lifecycle
    # ------------------------------------------------------------------

    async def _setup_next_wave(
        self, interaction: Interaction = None, message: discord.Message = None
    ):
        """Set up the next wave. Stats only reset at chapter start (wave_num == 1)."""
        chapter = self.current_chapter

        if self.wave_num == 1:
            # Snapshot chapter-start resources so a death can roll them back
            self.chapter_start_xp = self.cumulative_xp
            self.chapter_start_gold = self.cumulative_gold
            # Clear any guaranteed-page flag left over from a prior chapter's boon
            self.run_state.pop("guaranteed_page_this_chapter", None)

            restore_clean_stats(self.player)
            self.player.combat_ward = self.player.get_combat_ward_value()

            nullify = self.run_state.get("sig_nullify_next", False)
            if nullify:
                self.run_state["sig_nullify_next"] = False
            else:
                apply_signature_modifier(self.player, chapter)
            apply_per_wave_boons(self.player, self.active_boons)

            self._snapshot_wave_baseline()
        else:
            self._restore_wave_baseline()

        from core.combat.turns.boundary import reset_combat_transients

        reset_combat_transients(self.player)

        self.combat_logger.log_combat_end(self.player, self.monster, "victory")

        self.monster = await _generate_codex_wave_monster(
            self.player, chapter, self.wave_num
        )
        engine.apply_stat_effects(self.player, self.monster)
        self.logs = engine.apply_combat_start_passives(self.player, self.monster)

        self.combat_logger = CombatLogger(self.player, self.monster)
        self.combat_logger.log_combat_start(self.player, self.monster)

        for child in self.children:
            child.disabled = False

        embed = self._combat_embed()
        msg_obj = message or (
            await interaction.original_response() if interaction else None
        )
        if msg_obj:
            await msg_obj.edit(embed=embed, view=self)

    async def _handle_wave_clear(
        self, interaction: Interaction = None, message: discord.Message = None
    ):
        """Called when monster HP drops to 0. Awards XP/Gold, decides next action."""
        rewards = calculate_rewards(self.player, self.monster)
        wave_xp = int(rewards["xp"] * 0.05)
        wave_gold = int(rewards["gold"] * 0.05)
        self.cumulative_xp += wave_xp
        self.cumulative_gold += wave_gold

        self.waves_cleared_this_run += 1

        from core.combat.turns.boundary import fire_on_victory_effects

        fire_on_victory_effects(self.player)

        if self.wave_num in (3, 6):
            await self._enter_respite(interaction, message)
            return

        if self.wave_num == 7:
            await self._handle_chapter_clear(interaction, message)
            return

        self.wave_num += 1
        await self._setup_next_wave(interaction, message)

    async def _enter_respite(
        self, interaction: Interaction = None, message: discord.Message = None
    ):
        """Swap to respite state with 2 randomly weighted boons."""
        self._boon_processing = False
        boons = roll_boons(2)
        reroll_available = self.chapter_idx not in self.reroll_used_chapters
        self.clear_items()
        self.add_item(BoonButton(boons[0], self, row=0))
        self.add_item(BoonButton(boons[1], self, row=1))
        if reroll_available:
            self.add_item(RerollButton(self))

        embed = self._respite_embed(boons, reroll_available=reroll_available)
        msg_obj = message or (
            await interaction.original_response() if interaction else None
        )
        if msg_obj:
            await msg_obj.edit(embed=embed, view=self)

    async def handle_reroll(self, interaction: Interaction):
        """Re-rolls both boon choices (once per chapter)."""
        await interaction.response.defer()
        self.reroll_used_chapters.add(self.chapter_idx)
        boons = roll_boons(2)
        self.clear_items()
        self.add_item(BoonButton(boons[0], self, row=0))
        self.add_item(BoonButton(boons[1], self, row=1))

        embed = self._respite_embed(boons, reroll_available=False)
        await (await interaction.original_response()).edit(embed=embed, view=self)

    async def handle_boon_choice(self, interaction: Interaction, boon: CodexBoon):
        """Processes the player's respite boon selection."""
        if self._boon_processing:
            await interaction.response.defer()
            return
        self._boon_processing = True
        await interaction.response.defer()
        apply_respite_boon(self.player, boon, self.active_boons, self.run_state)

        self.clear_items()
        self._add_combat_buttons()

        self.wave_num += 1
        await self._setup_next_wave(message=await interaction.original_response())

    async def _handle_chapter_clear(
        self, interaction: Interaction = None, message: discord.Message = None
    ):
        """Awards chapter completion, drops page, transitions to next chapter or run end."""
        await self.bot.database.codex.log_chapter_clear(
            self.user_id, self.current_chapter.id, perfect=False
        )
        self.chapters_cleared += 1
        self.cleared_chapter_indices.add(self.chapter_idx)

        page_rate_bonus = sum(
            b.value for b in self.active_boons if b.type == "page_rate_boost"
        )
        page_drop_rate = 0.05 * (1 + page_rate_bonus / 100)
        guaranteed_page = self.run_state.pop("guaranteed_page_this_chapter", False)
        page_dropped = guaranteed_page or random.random() < page_drop_rate
        if page_dropped:
            await self.bot.database.users.modify_currency(
                self.user_id, "codex_pages", 1
            )
            self.page_drops.append(self.current_chapter.id)

        embed = self._chapter_clear_embed(
            self.cumulative_xp, self.cumulative_gold, page_dropped
        )
        msg_obj = message or (
            await interaction.original_response() if interaction else None
        )
        if msg_obj:
            await msg_obj.edit(embed=embed, view=None)

        await asyncio.sleep(4)

        next_idx = self.chapter_idx + 1
        if next_idx >= len(self.chapters):
            await self._handle_run_complete(msg_obj)
            return

        self.chapter_idx = next_idx
        self.wave_num = 1
        self._add_combat_buttons()

        if msg_obj:
            await self._setup_next_wave(message=msg_obj)

    async def _handle_run_complete(self, message: discord.Message = None):
        """Finalises a completed run, awards all fragment rewards."""
        is_perfect = self.deaths == 0 and self.chapters_cleared == 5
        fragments = calculate_run_fragments(
            self.chapters_cleared,
            is_perfect=is_perfect,
            fragment_multiplier=self.run_state.get("fragment_multiplier", 1.0),
            deaths=self.deaths,
        )
        if is_perfect:
            chapter_ids = [ch.id for ch in self.chapters]
            await self.bot.database.codex.log_perfect_run(self.user_id, chapter_ids)

        try:
            from core.quests.mechanics import tick_quest_progress

            await tick_quest_progress(
                self.bot, self.user_id, getattr(self, "server_id", ""), "codex_complete"
            )
        except Exception as e:
            print(f"[Quest tick error in codex]: {e}")

        await self.bot.database.users.modify_currency(
            self.user_id, "codex_fragments", fragments
        )

        await self.bot.database.users.modify_gold(self.user_id, self.cumulative_gold)

        exp_changes = await ExperienceManager.add_experience(
            self.bot, self.user_id, self.player, self.cumulative_xp
        )
        await self.bot.database.users.update_from_player_object(self.player)

        embed = self._summary_embed(fragments, len(self.page_drops), exp_changes)
        self.clear_items()
        self.stop()
        self.bot.state_manager.clear_active(self.user_id)

        if message:
            await message.edit(embed=embed, view=None)

    # ------------------------------------------------------------------
    # Defeat / Retreat
    # ------------------------------------------------------------------

    async def _handle_defeat(
        self, interaction: Interaction = None, message: discord.Message = None
    ):
        """Chapter fails on defeat. XP/gold forfeited. Player advances to the next chapter."""
        self.combat_logger.log_combat_end(self.player, self.monster, "defeat")
        self.deaths += 1

        # Forfeit XP and gold accumulated within this chapter
        chapter_xp_lost = self.cumulative_xp - self.chapter_start_xp
        chapter_gold_lost = self.cumulative_gold - self.chapter_start_gold
        self.cumulative_xp = self.chapter_start_xp
        self.cumulative_gold = self.chapter_start_gold

        # Void any guaranteed-page flag — chapter not cleared
        self.run_state.pop("guaranteed_page_this_chapter", None)

        # Restore to full HP for the next chapter
        self.player.current_hp = self.player.total_max_hp
        await self.bot.database.users.update_from_player_object(self.player)

        next_idx = self.chapter_idx + 1
        is_last_chapter = next_idx >= len(self.chapters)
        proceed_line = (
            "Finalising run..."
            if is_last_chapter
            else f"Advancing to **Chapter {next_idx + 1}**..."
        )

        embed = discord.Embed(
            title=f"💀 Chapter Failed — {self.current_chapter.name}",
            description=(
                f"**{self.player.name}** was slain on Wave {self.wave_num} "
                f"of Chapter {self.chapter_idx + 1}.\n{proceed_line}"
            ),
            color=discord.Color.red(),
        )
        embed.add_field(
            name="📚 XP Forfeited", value=f"{chapter_xp_lost:,}", inline=True
        )
        embed.add_field(
            name="💰 Gold Forfeited", value=f"{chapter_gold_lost:,}", inline=True
        )
        embed.add_field(name="💀 Deaths", value=str(self.deaths), inline=True)

        msg_obj = message or (
            await interaction.original_response() if interaction else None
        )
        if msg_obj:
            await msg_obj.edit(embed=embed, view=None)

        await asyncio.sleep(4)

        if is_last_chapter:
            await self._handle_run_complete(msg_obj)
            return

        self.chapter_idx = next_idx
        self.wave_num = 1
        self._add_combat_buttons()
        if msg_obj:
            await self._setup_next_wave(message=msg_obj)

    # ------------------------------------------------------------------
    # Combat button helpers
    # ------------------------------------------------------------------

    def _add_combat_buttons(self):
        """Clears and re-adds the standard combat buttons."""
        self.clear_items()
        self.add_item(self._attack_btn)
        self.add_item(self._auto_btn)
        self.add_item(self._retreat_btn)

    async def _refresh_ui(
        self, interaction: Interaction = None, message: discord.Message = None
    ):
        embed = self._combat_embed()
        if interaction and not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=self)
        elif message:
            await message.edit(embed=embed, view=self)
        elif interaction:
            await interaction.edit_original_response(embed=embed, view=self)

    async def _execute_turn(self, message: discord.Message):
        p_log = engine.process_player_turn(self.player, self.monster)
        self.combat_logger.log_player_turn(p_log, self.monster)
        self.logs = {self.player.name: p_log}
        if self.monster.hp > 0:
            m_log = engine.process_monster_turn(self.player, self.monster)
            self.combat_logger.log_monster_turn(m_log, self.player)
            self.logs[self.monster.name] = m_log
        await self._check_state(message=message)

    async def _check_state(
        self, interaction: Interaction = None, message: discord.Message = None
    ):
        if self.player.current_hp <= 0:
            await self._handle_defeat(interaction, message)
        elif self.monster.hp <= 0:
            await self._handle_wave_clear(interaction, message)
        else:
            await self._refresh_ui(interaction, message)

    # ------------------------------------------------------------------
    # Static combat buttons
    # ------------------------------------------------------------------

    @ui.button(label="Attack", style=ButtonStyle.danger, emoji="⚔️", row=0)
    async def _attack_btn(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await self._execute_turn(message=interaction.message)

    # @ui.button(label="Heal", style=ButtonStyle.success, emoji="🩹", row=0)
    # async def _heal_btn(self, interaction: Interaction, button: ui.Button):
    #     await interaction.response.defer()
    #     message = interaction.message
    #     heal_log = engine.process_heal(self.player, self.monster)
    #     self.logs = {"Heal": heal_log}
    #     if self.monster.hp > 0:
    #         m_log = engine.process_monster_turn(self.player, self.monster)
    #         self.combat_logger.log_monster_turn(m_log, self.player)
    #         self.logs[self.monster.name] = m_log
    #     await self._check_state(message=message)

    @ui.button(label="Auto", style=ButtonStyle.primary, emoji="⏩", row=0)
    async def _auto_btn(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        message = interaction.message

        # Disable all buttons for the duration of the auto loop
        for child in self.children:
            child.disabled = True
        await message.edit(view=self)

        while (
            self.player.current_hp > (self.player.total_max_hp * 0.2)
            and self.monster.hp > 0
        ):
            for _ in range(10):
                if (
                    self.player.current_hp <= (self.player.total_max_hp * 0.2)
                    or self.monster.hp <= 0
                ):
                    break
                p_log = engine.process_player_turn(self.player, self.monster)
                self.combat_logger.log_player_turn(p_log, self.monster)
                m_log = ""
                if self.monster.hp > 0:
                    m_log = engine.process_monster_turn(self.player, self.monster)
                    self.combat_logger.log_monster_turn(m_log, self.player)
                self.logs = {self.player.name: p_log, self.monster.name: m_log}

            if self.monster.hp > 0 and self.player.current_hp > (
                self.player.total_max_hp * 0.2
            ):
                await self._refresh_ui(message=message)
                await asyncio.sleep(1.0)
            else:
                break

        if (
            0 < self.player.current_hp <= (self.player.total_max_hp * 0.2)
            and self.monster.hp > 0
        ):
            # Low HP pause — re-enable buttons so the player can act
            for child in self.children:
                child.disabled = False
            self.logs["Auto-Wave"] = "🛑 Paused: Low HP Protection triggered!"
            await self._refresh_ui(message=message)
            await message.channel.send(
                f"<@{self.user_id}> ⚠️ Low HP Protection triggered — auto paused!",
                delete_after=15,
            )
        else:
            await self._check_state(message=message)

    @ui.button(label="Retreat", style=ButtonStyle.secondary, emoji="🏃", row=1)
    async def _retreat_btn(self, interaction: Interaction, button: ui.Button):
        embed = discord.Embed(
            title="📕 Codex Abandoned",
            description=(
                f"**{self.player.name}** retreated from the Codex.\n"
                f"Chapters cleared: **{self.chapters_cleared}/5** — No rewards."
            ),
            color=discord.Color.light_grey(),
        )
        embed.add_field(
            name="📚 XP Accumulated (lost)",
            value=f"{self.cumulative_xp:,}",
            inline=True,
        )
        embed.add_field(
            name="💰 Gold Accumulated (lost)",
            value=f"{self.cumulative_gold:,}",
            inline=True,
        )
        await self.bot.database.users.update_from_player_object(self.player)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)
