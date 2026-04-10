import asyncio
import json
import random
import discord
from discord import ui, ButtonStyle, Interaction

from core.models import Player, Monster
from core.combat import engine
from core.combat import ui as combat_ui
from core.combat.gen_mob import generate_ascent_monster
from core.combat.rewards import calculate_rewards
from core.codex.mechanics import (
    CodexChapter, CodexBoon,
    select_run_chapters, roll_boons,
    snapshot_clean_stats, restore_clean_stats,
    apply_signature_modifier, apply_per_wave_boons, apply_respite_boon,
    calculate_wave_monster_level, get_wave_modifier_counts, calculate_run_fragments,
)
from database.repositories.codex import TOME_UPGRADE_COSTS, TOME_PASSIVE_TYPES, get_reroll_cost

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PASSIVE_LABELS = {
    'vitality':    ('🌿 Vitality',    '+{v:.1f}% Max HP'),
    'wrath':       ('🔥 Wrath',       '+{v:.1f}% DEF → ATK'),
    'bastion':     ('🛡️ Bastion',     '+{v:.1f}% ATK → DEF'),
    'tenacity':    ('⚡ Tenacity',    '{v:.1f}% chance halve dmg'),
    'bloodthirst': ('🩸 Bloodthirst', '{v:.1f}% crit HP drain'),
    'providence':  ('✨ Providence',  '+{v:.1f}% Rarity'),
    'precision':   ('🎯 Precision',   '-{v:.1f} Crit Target'),
    'affluence':   ('💰 Affluence',   '+{v:.1f}% XP & Gold'),
    'bulwark':     ('🪨 Bulwark',     '+{v:.1f}% PDR'),
    'resilience':  ('🔒 Resilience',  '+{v:.1f} FDR'),
}

def _tome_field(tome) -> tuple[str, str]:
    """Returns (name, value) for an embed field showing a tome slot."""
    name_tmpl, val_tmpl = _PASSIVE_LABELS.get(tome.passive_type, (tome.passive_type, '{v:.1f}'))
    stat_str = val_tmpl.format(v=tome.value) if tome.value > 0 else 'Not upgraded'
    return name_tmpl, f"Tier {tome.tier}/5 — {stat_str}"


async def _generate_codex_wave_monster(player: Player, chapter: CodexChapter, wave_num: int) -> Monster:
    """Generates a monster for a Codex wave using the ascent generator."""
    m_level = calculate_wave_monster_level(player, chapter, wave_num)
    n_mods, b_mods = get_wave_modifier_counts(wave_num, chapter.difficulty)
    monster = Monster(
        name="", level=0, hp=0, max_hp=0, xp=0,
        attack=0, defence=0, modifiers=[], image="", flavor="",
        is_boss=(wave_num == 7),
    )
    return await generate_ascent_monster(player, monster, m_level, n_mods, b_mods)


# ---------------------------------------------------------------------------
# Boon Button (dynamic, created per respite)
# ---------------------------------------------------------------------------

class BoonButton(ui.Button):
    def __init__(self, boon: CodexBoon, run_view: 'CodexRunView', row: int):
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
    def __init__(self, run_view: 'CodexRunView'):
        super().__init__(
            label="Reroll Choices",
            style=ButtonStyle.secondary,
            emoji="🔄",
            row=2,
        )
        self.run_view = run_view

    async def callback(self, interaction: Interaction):
        await self.run_view.handle_reroll(interaction)


# ---------------------------------------------------------------------------
# CodexRunView — main run state machine
# ---------------------------------------------------------------------------

class CodexRunView(ui.View):
    """
    Manages a complete Codex run (5 chapters × 7 waves each).
    State machine: "combat" | "respite" | "chapter_transition" | "done"
    """

    def __init__(self, bot, user_id: str, player: Player,
                 chapters: list[CodexChapter], initial_monster: Monster,
                 start_logs: dict, clean_stats: dict,
                 chapter_wave_baseline: dict = None):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.player = player
        self.chapters = chapters
        self.chapter_idx = 0
        self.wave_num = 1
        self.monster = initial_monster
        self.clean_stats = clean_stats
        self.logs = start_logs or {}

        # Baseline snapshot taken after chapter setup (signature + boons applied) but before
        # combat passives fire. Reset at the start of every wave so that sturdy/omnipotent/
        # absorb etc. don't compound across waves.
        self.chapter_wave_baseline: dict = chapter_wave_baseline or {}

        # Run-level state
        self.active_boons: list[CodexBoon] = []
        self.run_state: dict = {'fragment_multiplier': 1.0, 'sig_nullify_next': False}
        self.reroll_used_chapters: set[int] = set()  # chapter indices that consumed their reroll
        self.chapters_cleared = 0
        self.waves_cleared_this_run = 0
        self.page_drops: list[int] = []   # chapter ids where a page dropped

        # XP/gold accumulation across the run
        self.cumulative_xp = 0
        self.cumulative_gold = 0

    @property
    def current_chapter(self) -> CodexChapter:
        return self.chapters[self.chapter_idx]

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)

    # ------------------------------------------------------------------
    # Embed builders
    # ------------------------------------------------------------------

    def _combat_embed(self) -> discord.Embed:
        chapter = self.current_chapter
        title = (f"📖 Codex — {chapter.name} | Wave {self.wave_num}/7 "
                 f"(Chapter {self.chapter_idx + 1}/5)")
        embed = combat_ui.create_combat_embed(
            self.player, self.monster, self.logs, title_override=title
        )
        embed.color = discord.Color.dark_purple()
        sig_label = chapter.signature_label
        sig_desc = chapter.signature_description
        if self.run_state.get('sig_nullify_next') and self.chapter_idx < len(self.chapters) - 1:
            next_name = self.chapters[self.chapter_idx + 1].name
            embed.set_footer(text=(
                f"Signature: {sig_label} — {sig_desc} | "
                f"⚡ Next chapter '{next_name}' signature NULLIFIED"
            ))
        else:
            embed.set_footer(text=f"Signature: {sig_label} — {sig_desc}")
        return embed

    def _snapshot_wave_baseline(self):
        """Snapshot base stats after chapter/boon setup but before combat passives fire.
        Restored at the top of every wave so combat-start passives (sturdy, omnipotent,
        absorb, juggernaut, gilded_hunger, diabolic_pact, cursed_precision, Enfeeble,
        Impenetrable) don't compound across waves."""
        self.chapter_wave_baseline = {
            'attack':     self.player.base_attack,
            'defence':    self.player.base_defence,
            'crit_target': self.player.base_crit_chance_target,
        }

    def _restore_wave_baseline(self):
        """Restore base stats to the post-setup snapshot before combat passives fire."""
        if not self.chapter_wave_baseline:
            return
        self.player.base_attack = self.chapter_wave_baseline['attack']
        self.player.base_defence = self.chapter_wave_baseline['defence']
        self.player.base_crit_chance_target = self.chapter_wave_baseline['crit_target']

    def _projected_ward(self) -> int:
        """Ward the player will have at the start of the next wave.
        Respite is always mid-chapter, so ward carries over from the current value.
        Boon ward additions are included since they fire every wave.
        """
        ward = self.player.combat_ward
        for boon in self.active_boons:
            if boon.type == "ward_boost":
                ward += int(self.player.max_hp * (boon.value / 100))
        return ward

    def _respite_embed(self, boons: list[CodexBoon], reroll_available: bool = False) -> discord.Embed:
        chapter = self.current_chapter
        p = self.player

        atk = p.get_total_attack()
        def_ = p.get_total_defence()
        eff_max_hp = p.get_effective_max_hp()
        crit = p.get_current_crit_target()
        rarity = p.get_total_rarity()
        fdr = p.get_total_fdr()
        pdr = p.get_total_pdr()

        hp_line = f"❤️ **{p.current_hp:,}/{eff_max_hp:,}**"
        proj_ward = self._projected_ward()
        if proj_ward > 0:
            hp_line += f"  🔮 Ward (next wave): **{proj_ward:,}**"
        stats_block = (
            f"⚔️ ATK: **{atk:,}**  🛡️ DEF: **{def_:,}**\n"
            f"{hp_line}\n"
            f"🎯 Crit Target: **{crit}**  ✨ Rarity: **{rarity}%**"
        )
        if fdr > 0 or pdr > 0:
            stats_block += f"\n🔒 FDR: **{fdr}**  🪨 PDR: **{pdr}%**"

        reroll_hint = "\n*(🔄 Reroll available — one use per chapter)*" if reroll_available else ""
        embed = discord.Embed(
            title=f"⚗️ Respite — {chapter.name}",
            description=(
                f"A moment of stillness between the waves.\n\n"
                f"{stats_block}\n\n"
                f"Choose one boon for the remaining waves:{reroll_hint}"
            ),
            color=discord.Color.teal(),
        )
        embed.set_thumbnail(url="https://i.imgur.com/hiLIsNI.png")
        for i, boon in enumerate(boons, 1):
            field_name = f"Option {i}: {boon.label}"
            if boon.downside_label:
                field_name += f"  ⚠️ {boon.downside_label}"
            embed.add_field(name=field_name, value=boon.description, inline=False)
        if self.active_boons:
            boon_summary = ", ".join(b.label for b in self.active_boons)
            embed.set_footer(text=f"Active boons: {boon_summary}")
        return embed

    def _chapter_clear_embed(self, xp: int, gold: int, page_dropped: bool) -> discord.Embed:
        chapter = self.current_chapter
        embed = discord.Embed(
            title=f"✅ Chapter Complete — {chapter.name}",
            description=f"All 7 waves cleared!",
            color=discord.Color.green(),
        )
        embed.add_field(name="📚 XP", value=f"{xp:,}", inline=True)
        embed.add_field(name="💰 Gold", value=f"{gold:,}", inline=True)
        if page_dropped:
            embed.add_field(name="📄 Codex Page", value="A Codex Page dropped!", inline=False)
        next_idx = self.chapter_idx + 1
        if next_idx < len(self.chapters):
            next_ch = self.chapters[next_idx]
            nullified = self.run_state.get('sig_nullify_next', False)
            sig_info = "~~" + next_ch.signature_label + "~~ (Nullified)" if nullified else (
                f"{next_ch.signature_label}: {next_ch.signature_description}"
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

    def _summary_embed(self, fragments: int, pages_dropped: int) -> discord.Embed:
        is_perfect = (self.chapters_cleared == 5 and self.waves_cleared_this_run == 35)
        embed = discord.Embed(
            title="📕 Codex Run Complete",
            description=(
                f"**{self.player.name}** cleared **{self.chapters_cleared}/5** chapters."
                + (" ✨ **Perfect Run!**" if is_perfect else "")
            ),
            color=discord.Color.gold() if is_perfect else discord.Color.blurple(),
        )
        embed.add_field(name="📚 Total XP", value=f"{self.cumulative_xp:,}", inline=True)
        embed.add_field(name="💰 Total Gold", value=f"{self.cumulative_gold:,}", inline=True)
        embed.add_field(name="🔷 Fragments Earned", value=str(fragments), inline=True)
        if pages_dropped > 0:
            embed.add_field(name="📄 Codex Pages", value=str(pages_dropped), inline=True)
        chapters_text = "\n".join(
            f"{'✅' if i < self.chapters_cleared else '❌'} {ch.name}"
            for i, ch in enumerate(self.chapters)
        )
        embed.add_field(name="Chapters", value=chapters_text, inline=False)
        embed.set_thumbnail(url="https://i.imgur.com/CYoQQLk.png")
        return embed

    # ------------------------------------------------------------------
    # Wave lifecycle
    # ------------------------------------------------------------------

    async def _setup_next_wave(self, interaction: Interaction = None, message: discord.Message = None):
        """Set up the next wave. Stats only reset at chapter start (wave_num == 1)."""
        chapter = self.current_chapter

        if self.wave_num == 1:
            # Chapter start: wipe the previous chapter's signature so it doesn't stack,
            # then apply the new signature and re-apply all accumulated boons on top.
            restore_clean_stats(self.player, self.clean_stats)
            self.player.combat_ward = self.player.get_combat_ward_value()

            nullify = self.run_state.get('sig_nullify_next', False)
            if nullify:
                self.run_state['sig_nullify_next'] = False
            else:
                apply_signature_modifier(self.player, chapter)
            apply_per_wave_boons(self.player, self.active_boons)

            # Snapshot post-setup stats for this chapter so combat passives
            # (sturdy, omnipotent, absorb, Enfeeble, Impenetrable, etc.) are
            # restored to this value at the start of every subsequent wave.
            self._snapshot_wave_baseline()
        else:
            # Mid-chapter: restore to post-setup baseline before combat passives fire
            self._restore_wave_baseline()

        # Per-combat transients reset every wave regardless
        self.player.voracious_stacks = 0
        self.player.cursed_precision_active = False
        self.player.gaze_stacks = 0
        self.player.hunger_stacks = 0
        self.player.is_invulnerable_this_combat = False
        self.player.celestial_vow_used = False

        self.monster = await _generate_codex_wave_monster(self.player, chapter, self.wave_num)
        engine.apply_stat_effects(self.player, self.monster)
        self.logs = engine.apply_combat_start_passives(self.player, self.monster)

        embed = self._combat_embed()
        msg_obj = message or (await interaction.original_response() if interaction else None)
        if msg_obj:
            await msg_obj.edit(embed=embed, view=self)

    async def _handle_wave_clear(self, interaction: Interaction = None, message: discord.Message = None):
        """Called when monster HP drops to 0. Awards XP/Gold, decides next action."""
        rewards = calculate_rewards(self.player, self.monster)
        # Codex runs 35 waves in rapid succession — nerf to ~30% to keep Ascension premier
        wave_xp = int(rewards['xp'] * 0.30)
        wave_gold = int(rewards['gold'] * 0.30)
        self.player.exp += wave_xp
        self.cumulative_xp += wave_xp
        self.cumulative_gold += wave_gold
        await self.bot.database.users.modify_gold(self.user_id, wave_gold)

        # Level-up loop (mirrors ascent — handles multiple levels/ascensions at once)
        try:
            with open('assets/exp.json') as f:
                exp_table = json.load(f)
            while True:
                exp_threshold = exp_table["levels"].get(str(self.player.level), 999999999)
                if self.player.exp < exp_threshold:
                    break
                if self.player.level >= 100:
                    self.player.ascension += 1
                    self.player.exp -= exp_threshold
                    await self.bot.database.users.modify_currency(self.user_id, 'passive_points', 2)
                else:
                    self.player.level += 1
                    self.player.exp -= exp_threshold
                    atk_inc = random.randint(1, 5)
                    def_inc = random.randint(1, 5)
                    hp_inc = random.randint(1, 5)
                    self.player.base_attack += atk_inc
                    self.player.base_defence += def_inc
                    self.player.max_hp += hp_inc
                    # HP does not restore on level-up mid-run; max_hp increase is enough
                    await self.bot.database.users.modify_stat(self.user_id, 'attack', atk_inc)
                    await self.bot.database.users.modify_stat(self.user_id, 'defence', def_inc)
                    await self.bot.database.users.modify_stat(self.user_id, 'max_hp', hp_inc)
                    if self.player.level % 10 == 0:
                        await self.bot.database.users.modify_currency(self.user_id, 'passive_points', 2)
                    # Update the wave baseline so subsequent waves use the levelled stats
                    if self.chapter_wave_baseline:
                        self.chapter_wave_baseline['attack'] += atk_inc
                        self.chapter_wave_baseline['defence'] += def_inc
                    # Also update clean_stats so next chapter reset uses the levelled base
                    self.clean_stats['attack'] += atk_inc
                    self.clean_stats['defence'] += def_inc
                    self.clean_stats['max_hp'] += hp_inc
        except Exception:
            pass

        await self.bot.database.users.update_from_player_object(self.player)

        self.waves_cleared_this_run += 1

        # Respite check (after wave 3 and wave 6)
        if self.wave_num in (3, 6):
            await self._enter_respite(interaction, message)
            return

        # Chapter boss cleared (wave 7)
        if self.wave_num == 7:
            await self._handle_chapter_clear(interaction, message)
            return

        # Continue to next wave
        self.wave_num += 1
        await self._setup_next_wave(interaction, message)

    async def _enter_respite(self, interaction: Interaction = None, message: discord.Message = None):
        """Swap to respite state with 2 randomly weighted boons."""
        boons = roll_boons(2)
        reroll_available = self.chapter_idx not in self.reroll_used_chapters
        self.clear_items()
        self.add_item(BoonButton(boons[0], self, row=0))
        self.add_item(BoonButton(boons[1], self, row=1))
        if reroll_available:
            self.add_item(RerollButton(self))

        embed = self._respite_embed(boons, reroll_available=reroll_available)
        msg_obj = message or (await interaction.original_response() if interaction else None)
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
        # Reroll button intentionally not re-added — one use per chapter consumed

        embed = self._respite_embed(boons, reroll_available=False)
        await (await interaction.original_response()).edit(embed=embed, view=self)

    async def handle_boon_choice(self, interaction: Interaction, boon: CodexBoon):
        """Processes the player's respite boon selection."""
        await interaction.response.defer()
        result_msg = apply_respite_boon(
            self.player, boon, self.active_boons, self.clean_stats, self.run_state
        )

        self.clear_items()
        self._add_combat_buttons()

        self.wave_num += 1
        await self._setup_next_wave(message=await interaction.original_response())

    async def _handle_chapter_clear(self, interaction: Interaction = None, message: discord.Message = None):
        """Awards chapter completion, drops page, transitions to next chapter or run end."""
        # Log chapter clear
        await self.bot.database.codex.log_chapter_clear(
            self.user_id, self.current_chapter.id, perfect=False
        )
        self.chapters_cleared += 1

        # Page drop (5%)
        page_dropped = random.random() < 0.05
        if page_dropped:
            await self.bot.database.users.modify_currency(self.user_id, 'codex_pages', 1)
            self.page_drops.append(self.current_chapter.id)

        # Show chapter clear embed (no buttons during transition)
        embed = self._chapter_clear_embed(self.cumulative_xp, self.cumulative_gold, page_dropped)
        msg_obj = message or (await interaction.original_response() if interaction else None)
        if msg_obj:
            await msg_obj.edit(embed=embed, view=None)

        await asyncio.sleep(4)

        # Advance to next chapter or end run
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
        fragments = calculate_run_fragments(
            self.chapters_cleared,
            is_perfect=(self.waves_cleared_this_run == 35),
            fragment_multiplier=self.run_state.get('fragment_multiplier', 1.0),
        )
        await self.bot.database.users.modify_currency(self.user_id, 'codex_fragments', fragments)

        embed = self._summary_embed(fragments, len(self.page_drops))
        self.clear_items()
        self.stop()
        self.bot.state_manager.clear_active(self.user_id)

        if message:
            await message.edit(embed=embed, view=None)

    # ------------------------------------------------------------------
    # Defeat / Retreat
    # ------------------------------------------------------------------

    async def _handle_defeat(self, interaction: Interaction = None, message: discord.Message = None):
        """Run ends on defeat. No fragment rewards. XP penalty applied."""
        xp_loss = max(0, int(self.player.exp * 0.05))  # 5% XP loss (lighter than Ascension)
        self.player.exp = max(0, self.player.exp - xp_loss)
        self.player.current_hp = 1
        await self.bot.database.users.update_from_player_object(self.player)

        embed = discord.Embed(
            title=f"💀 Defeated — {self.current_chapter.name}",
            description=(
                f"**{self.player.name}** was slain on Wave {self.wave_num} "
                f"of Chapter {self.chapter_idx + 1}.\n"
                f"Chapters cleared: **{self.chapters_cleared}/5**\n"
                f"Lost **{xp_loss:,}** XP."
            ),
            color=discord.Color.red(),
        )
        embed.add_field(name="📚 XP Earned", value=f"{self.cumulative_xp:,}", inline=True)
        embed.add_field(name="💰 Gold Earned", value=f"{self.cumulative_gold:,}", inline=True)
        embed.add_field(name="Rewards", value="No Codex Fragments on defeat.", inline=False)

        self.clear_items()
        self.stop()
        self.bot.state_manager.clear_active(self.user_id)

        msg_obj = message or (await interaction.original_response() if interaction else None)
        if msg_obj:
            await msg_obj.edit(embed=embed, view=None)

    # ------------------------------------------------------------------
    # Combat button helpers
    # ------------------------------------------------------------------

    def _add_combat_buttons(self):
        """Clears and re-adds the standard combat buttons."""
        self.clear_items()
        self.add_item(self._attack_btn)
        self.add_item(self._heal_btn)
        self.add_item(self._auto_btn)
        self.add_item(self._retreat_btn)

    async def _refresh_ui(self, interaction: Interaction = None, message: discord.Message = None):
        embed = self._combat_embed()
        if interaction and not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=self)
        elif message:
            await message.edit(embed=embed, view=self)
        elif interaction:
            await interaction.edit_original_response(embed=embed, view=self)

    async def _execute_turn(self, message: discord.Message):
        p_log = engine.process_player_turn(self.player, self.monster)
        self.logs = {self.player.name: p_log}
        if self.monster.hp > 0:
            m_log = engine.process_monster_turn(self.player, self.monster)
            self.logs[self.monster.name] = m_log
        await self._check_state(message=message)

    async def _check_state(self, interaction: Interaction = None, message: discord.Message = None):
        if self.player.current_hp <= 0:
            await self._handle_defeat(interaction, message)
        elif self.monster.hp <= 0:
            await self._handle_wave_clear(interaction, message)
        else:
            await self._refresh_ui(interaction, message)

    # ------------------------------------------------------------------
    # Static combat buttons (attached as instance attributes so _add_combat_buttons works)
    # ------------------------------------------------------------------

    @ui.button(label="Attack", style=ButtonStyle.danger, emoji="⚔️", row=0)
    async def _attack_btn(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await self._execute_turn(message=interaction.message)

    @ui.button(label="Heal", style=ButtonStyle.success, emoji="🩹", row=0)
    async def _heal_btn(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        message = interaction.message
        heal_log = engine.process_heal(self.player, self.monster)
        self.logs = {"Heal": heal_log}
        if self.monster.hp > 0:
            m_log = engine.process_monster_turn(self.player, self.monster)
            self.logs[self.monster.name] = m_log
        await self._check_state(message=message)

    @ui.button(label="Auto Wave", style=ButtonStyle.primary, emoji="⏩", row=0)
    async def _auto_btn(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        message = interaction.message

        while self.player.current_hp > (self.player.max_hp * 0.2) and self.monster.hp > 0:
            for _ in range(10):
                if self.player.current_hp <= (self.player.max_hp * 0.2) or self.monster.hp <= 0:
                    break
                p_log = engine.process_player_turn(self.player, self.monster)
                m_log = ""
                if self.monster.hp > 0:
                    m_log = engine.process_monster_turn(self.player, self.monster)
                self.logs = {self.player.name: p_log, self.monster.name: m_log}

            if self.monster.hp > 0 and self.player.current_hp > (self.player.max_hp * 0.2):
                await self._refresh_ui(message=message)
                await asyncio.sleep(1.0)
            else:
                break

        if 0 < self.player.current_hp <= (self.player.max_hp * 0.2) and self.monster.hp > 0:
            self.logs["Auto-Wave"] = "🛑 Paused: Low HP Protection triggered!"
            await self._refresh_ui(message=message)
            await message.channel.send(
                f"<@{self.player.id}> ⚠️ Low HP Protection triggered — auto paused!",
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
        embed.add_field(name="📚 XP Earned (kept)", value=f"{self.cumulative_xp:,}", inline=True)
        embed.add_field(name="💰 Gold Earned (kept)", value=f"{self.cumulative_gold:,}", inline=True)
        await self.bot.database.users.update_from_player_object(self.player)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)


# ---------------------------------------------------------------------------
# CodexTomsView — Tome management
# ---------------------------------------------------------------------------

class CodexTomsView(ui.View):
    """Shows a player's 5 tome slots and allows upgrading/rerolling."""

    def __init__(self, bot, user_id: str, player: Player, fragments: int, pages: int, rerolls: int, chapter_history: dict):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.player = player
        self.fragments = fragments
        self.pages = pages
        self.rerolls = rerolls
        self.chapter_history = chapter_history
        self.selected_slot: int | None = None
        self._rebuild()

    def _rebuild(self):
        self.clear_items()
        tomes = self.player.codex_tomes
        slots = len(tomes)

        # Slot select (if any slots are unlocked)
        if slots > 0:
            options = [
                discord.SelectOption(
                    label=f"Slot {t.slot + 1}: {_PASSIVE_LABELS.get(t.passive_type, (t.passive_type, ''))[0]}",
                    value=str(t.slot),
                    description=f"Tier {t.tier}/5",
                )
                for t in tomes
            ]
            select = ui.Select(placeholder="Select a tome slot...", options=options, row=0)
            select.callback = self._on_slot_select
            self.add_item(select)

        # Unlock button (row 1)
        can_unlock = slots < 5 and self.pages > 0
        unlock_btn = ui.Button(
            label=f"Unlock Slot ({self.pages} page{'s' if self.pages != 1 else ''})",
            style=ButtonStyle.success,
            disabled=not can_unlock,
            row=1,
        )
        unlock_btn.callback = self._on_unlock
        self.add_item(unlock_btn)

        # Action buttons for selected slot (row 2)
        if self.selected_slot is not None:
            tome = next((t for t in tomes if t.slot == self.selected_slot), None)
            if tome:
                # Upgrade
                can_upgrade = tome.tier < 5 and self.fragments >= TOME_UPGRADE_COSTS[tome.tier]
                upgrade_cost = TOME_UPGRADE_COSTS[tome.tier] if tome.tier < 5 else 0
                upgrade_btn = ui.Button(
                    label=f"Upgrade T{tome.tier}→T{tome.tier+1} ({upgrade_cost}🔷 + 10m💰)",
                    style=ButtonStyle.primary,
                    disabled=not can_upgrade,
                    row=2,
                )
                upgrade_btn.callback = self._on_upgrade
                self.add_item(upgrade_btn)

                # Reroll value
                reroll_val_cost = get_reroll_cost(tome.tier)
                can_reroll_val = tome.tier > 0 and self.fragments >= reroll_val_cost
                reroll_val_btn = ui.Button(
                    label=f"Reroll Value ({reroll_val_cost}🔷 + 10m💰)",
                    style=ButtonStyle.secondary,
                    disabled=not can_reroll_val,
                    row=2,
                )
                reroll_val_btn.callback = self._on_reroll_value
                self.add_item(reroll_val_btn)

                # Reroll type (costs reroll token)
                can_reroll_type = self.rerolls > 0
                reroll_type_btn = ui.Button(
                    label=f"Reroll Type ({self.rerolls}🔁 + 10m💰)",
                    style=ButtonStyle.danger,
                    disabled=not can_reroll_type,
                    row=2,
                )
                reroll_type_btn.callback = self._on_reroll_type
                self.add_item(reroll_type_btn)

        # Exit (row 3)
        exit_btn = ui.Button(label="Close", style=ButtonStyle.secondary, row=3)
        exit_btn.callback = self._on_exit
        self.add_item(exit_btn)

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📚 Codex Tomes",
            color=discord.Color.dark_purple(),
        )
        embed.add_field(
            name="Resources",
            value=f"🔷 {self.fragments} Fragments  |  📄 {self.pages} Pages  |  🔁 {self.rerolls} Reroll Tokens",
            inline=False,
        )
        tomes = self.player.codex_tomes
        if not tomes:
            embed.add_field(name="No slots unlocked", value="Use a Codex Page to unlock your first slot.", inline=False)
        else:
            for tome in tomes:
                name, value = _tome_field(tome)
                embed.add_field(name=f"Slot {tome.slot + 1}: {name}", value=value, inline=True)
            unlocked = len(tomes)
            if unlocked < 5:
                for i in range(unlocked, 5):
                    embed.add_field(name=f"Slot {i + 1}: 🔒 Locked", value="Requires a Codex Page", inline=True)

        if self.selected_slot is not None:
            tome = next((t for t in tomes if t.slot == self.selected_slot), None)
            if tome:
                name, _ = _PASSIVE_LABELS.get(tome.passive_type, (tome.passive_type, ''))
                embed.set_footer(text=f"Selected: Slot {self.selected_slot + 1} — {name} (Tier {tome.tier}/5, Value {tome.value:.2f})")
        embed.set_thumbnail(url="https://i.imgur.com/qvqtxUC.png")
        return embed

    async def _refresh(self, interaction: Interaction):
        self._rebuild()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _on_slot_select(self, interaction: Interaction):
        self.selected_slot = int(interaction.data['values'][0])
        await self._refresh(interaction)

    async def _on_unlock(self, interaction: Interaction):
        await interaction.response.defer()
        tome = await self.bot.database.codex.unlock_tome_slot(self.user_id)
        if tome is None:
            await interaction.followup.send("All 5 slots are already unlocked.", ephemeral=True)
            return
        await self.bot.database.users.modify_currency(self.user_id, 'codex_pages', -1)
        self.pages -= 1
        self.player.codex_tomes = await self.bot.database.codex.get_tomes(self.user_id)
        self.selected_slot = tome.slot
        self._rebuild()
        await interaction.edit_original_response(embed=self._build_embed(), view=self)

    async def _on_upgrade(self, interaction: Interaction):
        await interaction.response.defer()
        tome = next((t for t in self.player.codex_tomes if t.slot == self.selected_slot), None)
        if not tome or tome.tier >= 5:
            return
        cost = TOME_UPGRADE_COSTS[tome.tier]
        if self.fragments < cost:
            await interaction.followup.send("Not enough Codex Fragments.", ephemeral=True)
            return
        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < 10_000_000:
            await interaction.followup.send("You need **10,000,000 gold** to upgrade a Tome tier.", ephemeral=True)
            return
        ok, new_val = await self.bot.database.codex.upgrade_tome(self.user_id, self.selected_slot)
        if ok:
            await self.bot.database.users.modify_currency(self.user_id, 'codex_fragments', -cost)
            await self.bot.database.users.modify_gold(self.user_id, -10_000_000)
            self.fragments -= cost
            self.player.codex_tomes = await self.bot.database.codex.get_tomes(self.user_id)
        self._rebuild()
        await interaction.edit_original_response(embed=self._build_embed(), view=self)

    async def _on_reroll_value(self, interaction: Interaction):
        await interaction.response.defer()
        tome = next((t for t in self.player.codex_tomes if t.slot == self.selected_slot), None)
        if not tome or tome.tier == 0:
            return
        cost = get_reroll_cost(tome.tier)
        if self.fragments < cost:
            await interaction.followup.send("Not enough Codex Fragments.", ephemeral=True)
            return
        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < 10_000_000:
            await interaction.followup.send("You need **10,000,000 gold** to reroll a Tome value.", ephemeral=True)
            return
        ok, _ = await self.bot.database.codex.reroll_tome_value(self.user_id, self.selected_slot)
        if ok:
            await self.bot.database.users.modify_currency(self.user_id, 'codex_fragments', -cost)
            await self.bot.database.users.modify_gold(self.user_id, -10_000_000)
            self.fragments -= cost
            self.player.codex_tomes = await self.bot.database.codex.get_tomes(self.user_id)
        self._rebuild()
        await interaction.edit_original_response(embed=self._build_embed(), view=self)

    async def _on_reroll_type(self, interaction: Interaction):
        await interaction.response.defer()
        if self.rerolls <= 0:
            await interaction.followup.send("No Reroll Tokens available.", ephemeral=True)
            return
        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < 10_000_000:
            await interaction.followup.send("You need **10,000,000 gold** to reroll a Tome type.", ephemeral=True)
            return
        ok, _ = await self.bot.database.codex.reroll_tome_type(self.user_id, self.selected_slot)
        if ok:
            await self.bot.database.users.modify_currency(self.user_id, 'codex_rerolls', -1)
            await self.bot.database.users.modify_gold(self.user_id, -10_000_000)
            self.rerolls -= 1
            self.player.codex_tomes = await self.bot.database.codex.get_tomes(self.user_id)
        self._rebuild()
        await interaction.edit_original_response(embed=self._build_embed(), view=self)

    async def _on_exit(self, interaction: Interaction):
        self.stop()
        menu = CodexMenuView(
            self.bot, self.user_id, self.player,
            self.fragments, self.pages, self.rerolls, self.chapter_history,
        )
        await interaction.response.edit_message(embed=menu.build_embed(), view=menu)

    async def on_timeout(self):
        pass


# ---------------------------------------------------------------------------
# CodexMenuView — entry point
# ---------------------------------------------------------------------------

class CodexMenuView(ui.View):
    def __init__(self, bot, user_id: str, player: Player,
                 fragments: int, pages: int, rerolls: int, chapter_history: dict):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.player = player
        self.fragments = fragments
        self.pages = pages
        self.rerolls = rerolls
        self.chapter_history = chapter_history

    def build_embed(self) -> discord.Embed:
        tomes = self.player.codex_tomes
        embed = discord.Embed(
            title="📖 The Codex",
            description=(
                "An onslaught of curated chapters, each more brutal than the last.\n"
                "Five chapters are drawn at random per run. Manage your Tomes for permanent power."
            ),
            color=discord.Color.dark_purple(),
        )
        embed.add_field(
            name="Resources",
            value=f"🔷 {self.fragments} Fragments  |  📄 {self.pages} Pages  |  🔁 {self.rerolls} Rerolls",
            inline=False,
        )
        total_clears = sum(v['clears'] for v in self.chapter_history.values())
        total_perfects = sum(v['perfect_clears'] for v in self.chapter_history.values())
        embed.add_field(name="Chapter Clears", value=str(total_clears), inline=True)
        embed.add_field(name="Perfect Clears", value=str(total_perfects), inline=True)
        embed.add_field(name="Tome Slots Unlocked", value=f"{len(tomes)}/5", inline=True)
        embed.set_thumbnail(url="https://i.imgur.com/OylfbeA.png")
        embed.set_footer(text="Level 100+ required to begin a run.")
        return embed

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    @ui.button(label="Begin Run", style=ButtonStyle.danger, emoji="📖", row=0)
    async def begin_run(self, interaction: Interaction, button: ui.Button):
        # Cooldown check (10 min, reduced by speedster boot)
        from datetime import datetime, timedelta
        CODEX_COOLDOWN = timedelta(minutes=10)
        temp_reduction = 0
        boot = await self.bot.database.equipment.get_equipped(self.user_id, "boot")
        if boot and boot[9] == "speedster":
            temp_reduction = boot[12] * 60
        cooldown_duration = max(timedelta(seconds=10), CODEX_COOLDOWN - timedelta(seconds=temp_reduction))
        existing_user = await self.bot.database.users.get(self.user_id, str(interaction.guild_id))
        last_combat = existing_user[24] if existing_user else None
        if last_combat:
            try:
                dt = datetime.fromisoformat(last_combat)
                if datetime.now() - dt < cooldown_duration:
                    rem = cooldown_duration - (datetime.now() - dt)
                    return await interaction.response.send_message(
                        f"Codex cooldown: **{rem.seconds // 60}m {rem.seconds % 60}s** remaining.",
                        ephemeral=True,
                    )
            except Exception:
                pass

        await interaction.response.defer()

        self.bot.state_manager.set_active(self.user_id, "codex")
        await self.bot.database.users.update_timer(self.user_id, 'last_combat')

        # Clear active task species — prevents slayer task completion and species-gated
        # emblem bonuses (slayer_dmg / slayer_def), which are tied to assigned tasks.
        # All other emblem and companion bonuses apply normally.
        self.player.active_task_species = None

        # Select 5 chapters for this run
        chapters = select_run_chapters(5)
        chapter = chapters[0]

        # Snapshot clean stats (after gear/tome bonuses are baked in, before any modifiers)
        clean_stats = snapshot_clean_stats(self.player)

        # Apply chapter 1 signature + generate wave 1 monster
        self.player.combat_ward = self.player.get_combat_ward_value()
        apply_signature_modifier(self.player, chapter)

        # Snapshot post-setup stats before combat passives fire
        wave_baseline = {
            'attack':     self.player.base_attack,
            'defence':    self.player.base_defence,
            'crit_target': self.player.base_crit_chance_target,
        }

        monster = await _generate_codex_wave_monster(self.player, chapter, 1)
        engine.apply_stat_effects(self.player, monster)
        start_logs = engine.apply_combat_start_passives(self.player, monster)

        view = CodexRunView(
            self.bot, self.user_id, self.player,
            chapters, monster, start_logs, clean_stats,
            chapter_wave_baseline=wave_baseline,
        )

        embed = view._combat_embed()
        self.stop()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        # Store message reference for auto-combat
        view._message_ref = msg

    @ui.button(label="Tomes", style=ButtonStyle.primary, emoji="📚", row=0)
    async def view_tomes(self, interaction: Interaction, button: ui.Button):
        tomes_view = CodexTomsView(
            self.bot, self.user_id, self.player,
            self.fragments, self.pages, self.rerolls, self.chapter_history,
        )
        self.stop()
        await interaction.response.edit_message(embed=tomes_view._build_embed(), view=tomes_view)

    @ui.button(label="Close", style=ButtonStyle.secondary, row=0)
    async def exit_btn(self, interaction: Interaction, button: ui.Button):
        self.stop()
        await interaction.response.defer()
        await interaction.delete_original_response()

    async def on_timeout(self):
        pass
