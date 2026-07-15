import asyncio
import random
from dataclasses import asdict

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.codex.mechanics import (
    CodexBoon,
    CodexChapter,
    apply_hp_entry_cap,
    apply_per_wave_boons,
    apply_respite_boon,
    apply_signature_modifier,
    calculate_run_fragments,
    calculate_wave_monster_level,
    get_wave_modifier_counts,
    restore_clean_stats,
    roll_boons,
)
from core.combat import ui as combat_ui
from core.combat.calc.hit_calc import calculate_crit_chance
from core.combat.combat_log import CombatLogger
from core.combat.economy.experience import ExperienceManager
from core.combat.economy.rewards import calculate_rewards
from core.combat.mobgen.gen_mob import generate_ascent_monster
from core.combat.turns import engine
from core.emojis import (
    CODEX_FRAGMENT_EMOJI,
    CODEX_PAGE_EMOJI,
    CODEX_TOME_EMOJI,
    DODGE_EVASION,
    GOLD_COIN,
    STAT_ATK,
    STAT_BLOCK,
    STAT_DEF,
    STAT_FDR,
    STAT_HP,
    STAT_PDR,
    STAT_WARD,
)
from core.images import CODEX_BOON, CODEX_CHAPTERS
from core.models import Monster, Player


def build_wave_baseline(player: Player) -> dict:
    """Snapshot of base stats after chapter/boon setup but before combat
    passives fire. Shared by run start (menu_view), wave setup, and resume."""
    return {
        "bonus_crit": player.bonus_crit,
        "bonus_max_hp": player.bonus_max_hp,
        "bonus_def": player.bonus_def,
        "combat_ward": player.combat_ward,
        "atk_multiplier": player.atk_multiplier,
        "def_multiplier": player.def_multiplier,
        "crit_multiplier": player.crit_multiplier,
        "chapter_hit_penalty": player.chapter_hit_penalty,
        "chapter_pdr_reduction": player.chapter_pdr_reduction,
        "chapter_ward_gen_mult": player.chapter_ward_gen_mult,
        "chapter_crit_dmg_reduction": player.chapter_crit_dmg_reduction,
        "chapter_hp_entry_pct": player.chapter_hp_entry_pct,
        "codex_atk_pct": player.codex_atk_pct,
        "codex_def_pct": player.codex_def_pct,
        "codex_max_hp_pct": player.codex_max_hp_pct,
        "codex_crit_flat": player.codex_crit_flat,
    }


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


class CodexCombatRow(discord.ui.ActionRow["CodexRunView"]):
    """Row 0: Attack / Auto / Full Send. Thin dispatchers — logic lives on
    CodexRunView so it stays easy to follow and share with the auto-battle /
    full-send loops, which drive the same methods directly."""

    @discord.ui.button(label="Attack", style=ButtonStyle.danger, emoji="⚔️")
    async def attack_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_attack(interaction)

    @discord.ui.button(label="Auto", style=ButtonStyle.primary, emoji="⏩")
    async def auto_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_auto(interaction)

    @discord.ui.button(
        label="Full Send", style=ButtonStyle.danger, emoji="💀", disabled=True
    )
    async def full_send_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_full_send(interaction)


class CodexMetaRow(discord.ui.ActionRow["CodexRunView"]):
    """Row 1: Save & Exit / Abandon."""

    @discord.ui.button(label="Save & Exit", style=ButtonStyle.secondary, emoji="💾")
    async def retreat_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_retreat(interaction)

    @discord.ui.button(label="Abandon", style=ButtonStyle.danger, emoji="🗑️")
    async def abandon_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_abandon(interaction)


class CodexRunView(BaseLayoutView):
    """
    Manages a complete Codex run (5 chapters × 7 waves each).
    State machine: "combat" | "respite" | "chapter_transition" | "done"

    HP persistence contract
    -----------------------
    player.current_hp is mutated in-memory during every wave and is only
    written to the DB at three points:
      - _handle_defeat: resets to full HP for the next chapter and saves.
      - _handle_run_complete: saves at run end (XP + HP settled).
      - _retreat_btn: saves immediately so the retreated HP is the DB value.

    This is intentional: HP carries across waves and chapters within a single
    session.  In addition, the run itself is checkpointed to the codex_runs
    table at every chapter boundary (run start, chapter clear, defeat, and
    Save & Exit) via to_snapshot()/_save_run().  If the bot restarts mid-run,
    /codex offers to resume from the start of the current chapter — no new
    Antique Tome required.  There is no checkpoint between waves by design;
    mid-chapter progress (and its unbanked XP/gold) rolls back to the chapter
    start on resume.

    View timeout
    ------------
    BaseLayoutView.timeout is None (no auto-expiry).  Players must explicitly retreat
    or finish; they cannot idle-timeout their way out of a damaged HP state.
    A shard resume clears StateManager so the player can start a new run, but
    the in-progress run is abandoned and any unsaved HP damage from that session
    is lost (they return to the last DB-persisted value).
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
        server_id: str = "",
        player_avatar_url: str | None = None,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.chapters = chapters
        self.chapter_idx = 0
        self.wave_num = 1
        self.monster = initial_monster
        self.logs = start_logs or {}
        self.player_avatar_url = player_avatar_url

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

        # Whether the CURRENT chapter's signature was nullified (the
        # sig_nullify_next flag is consumed at wave-1 setup; a mid-chapter
        # Save & Exit must re-set it so resume re-nullifies the chapter).
        self._current_chapter_nullified = False

        self.combat_logger = CombatLogger(player, initial_monster)
        self.combat_logger.log_combat_start(player, initial_monster)

        self.row1 = CodexCombatRow()
        self.row2 = CodexMetaRow()

        self._update_full_send_state()
        self._sync_items(self._combat_layout())

    # ------------------------------------------------------------------
    # Run persistence (chapter-boundary snapshots)
    # ------------------------------------------------------------------

    def to_snapshot(self, at_chapter_start: bool = False) -> dict:
        """Serialise the run for DB persistence.

        With ``at_chapter_start=True`` (mid-chapter Save & Exit) the current
        chapter's XP/gold gains are rolled back to the chapter-start values,
        since resume restarts the chapter at wave 1 — otherwise the same
        waves could be re-earned."""
        run_state = dict(self.run_state)
        if at_chapter_start and self._current_chapter_nullified:
            run_state["sig_nullify_next"] = True
        return {
            "chapter_idx": self.chapter_idx,
            "chapters": [asdict(ch) for ch in self.chapters],
            "active_boons": [asdict(b) for b in self.active_boons],
            "run_state": run_state,
            "reroll_used_chapters": sorted(self.reroll_used_chapters),
            "chapters_cleared": self.chapters_cleared,
            "waves_cleared_this_run": self.waves_cleared_this_run,
            "deaths": self.deaths,
            "cumulative_xp": (
                self.chapter_start_xp if at_chapter_start else self.cumulative_xp
            ),
            "cumulative_gold": (
                self.chapter_start_gold if at_chapter_start else self.cumulative_gold
            ),
            "cleared_chapter_indices": sorted(self.cleared_chapter_indices),
            "page_drops": list(self.page_drops),
            "current_hp": self.player.current_hp,
            "run_penalties": {
                "atk": self.player.run_atk_penalty,
                "def": self.player.run_def_penalty,
                "crit": self.player.run_crit_penalty,
                "max_hp_bonus": self.player.run_max_hp_bonus,
            },
        }

    async def _save_run(self, at_chapter_start: bool = False):
        """Persist the snapshot; a save failure must never kill the run."""
        try:
            await self.bot.database.codex.upsert_run(
                self.user_id, self.server_id, self.to_snapshot(at_chapter_start)
            )
        except Exception as e:
            self.bot.logger.error(f"[Codex] run save failed for {self.user_id}: {e}")

    @classmethod
    async def resume_from_snapshot(
        cls,
        bot,
        user_id: str,
        player: Player,
        snap: dict,
        server_id: str = "",
        player_avatar_url: str | None = None,
    ) -> "CodexRunView":
        """Rebuild a run from a chapter-boundary snapshot, restarting the
        current chapter at wave 1 (mirrors begin_run's chapter setup)."""

        def _mods(pairs):
            return [tuple(p) for p in pairs]

        chapters = [
            CodexChapter(
                **{
                    **d,
                    "player_mods": _mods(d.get("player_mods", [])),
                    "monster_mods": _mods(d.get("monster_mods", [])),
                }
            )
            for d in snap["chapters"]
        ]
        active_boons = [CodexBoon(**b) for b in snap.get("active_boons", [])]
        run_state = dict(snap.get("run_state", {}))
        chapter_idx = int(snap.get("chapter_idx", 0))
        chapter = chapters[chapter_idx]

        player.active_task_species = None

        # Run-wide penalties from one-shot boons (fragment_boost downsides,
        # max_hp_boost) — these live on player.run, not in active_boons.
        rp = snap.get("run_penalties", {})
        player.run_atk_penalty = rp.get("atk", 0)
        player.run_def_penalty = rp.get("def", 0)
        player.run_crit_penalty = rp.get("crit", 0)
        player.run_max_hp_bonus = rp.get("max_hp_bonus", 0)

        # Chapter-start setup, mirroring _setup_next_wave's wave-1 branch
        restore_clean_stats(player)
        player.combat_ward = player.get_combat_ward_value()
        nullified = bool(run_state.get("sig_nullify_next", False))
        if nullified:
            run_state["sig_nullify_next"] = False
        else:
            apply_signature_modifier(player, chapter)
        apply_per_wave_boons(player, active_boons)

        # Restore HP after max-HP modifiers so clamping is correct. min()
        # with the live DB value blocks both directions of HP arbitrage
        # (heal outside and resume, or save at full and tank a hit outside).
        saved_hp = int(snap.get("current_hp", 0))
        if saved_hp > 0:
            player.current_hp = max(
                1, min(saved_hp, player.current_hp, player.total_max_hp)
            )

        wave_baseline = build_wave_baseline(player)

        from core.combat.turns.boundary import reset_combat_transients

        reset_combat_transients(player)

        monster = await _generate_codex_wave_monster(player, chapter, 1)
        engine.apply_stat_effects(player, monster)
        start_logs = engine.apply_combat_start_passives(player, monster)
        apply_hp_entry_cap(player)

        view = cls(
            bot,
            user_id,
            player,
            chapters,
            monster,
            start_logs,
            chapter_wave_baseline=wave_baseline,
            server_id=server_id,
            player_avatar_url=player_avatar_url,
        )
        view.chapter_idx = chapter_idx
        view.active_boons = active_boons
        view.run_state = run_state
        view._current_chapter_nullified = nullified
        view.reroll_used_chapters = set(snap.get("reroll_used_chapters", []))
        view.chapters_cleared = int(snap.get("chapters_cleared", 0))
        view.waves_cleared_this_run = int(snap.get("waves_cleared_this_run", 0))
        view.deaths = int(snap.get("deaths", 0))
        view.cumulative_xp = int(snap.get("cumulative_xp", 0))
        view.cumulative_gold = int(snap.get("cumulative_gold", 0))
        view.chapter_start_xp = view.cumulative_xp
        view.chapter_start_gold = view.cumulative_gold
        view.cleared_chapter_indices = set(snap.get("cleared_chapter_indices", []))
        view.page_drops = list(snap.get("page_drops", []))
        # chapter_idx/run_state were patched after __init__'s own render used
        # their defaults — re-sync now that the resumed state is in place.
        view._sync_items(view._combat_layout())
        return view

    @property
    def current_chapter(self) -> CodexChapter:
        return self.chapters[self.chapter_idx]

    # ------------------------------------------------------------------
    # Layout / item sync (Components V2)
    # ------------------------------------------------------------------

    def _sync_items(self, container=None, *, interactive: bool = True):
        """Rebuilds the LayoutView's top-level items: the display Container
        plus the two combat action rows. row1/row2 keep their identity across
        rebuilds so button .disabled state set mid-loop carries over.
        interactive=False drops the button rows entirely (terminal frames:
        chapter clear / defeat pause before the next wave/chapter loads)."""
        container = container if container is not None else self._combat_layout()
        self.clear_items()
        self.add_item(container)
        if interactive:
            self.add_item(self.row1)
            self.add_item(self.row2)

    def _signature_text(self) -> str:
        """Human-readable line describing the CURRENT chapter's signature.

        Correctly reflects self._current_chapter_nullified — shows the
        struck-through label instead of the full effect description when this
        chapter's signature was skipped via a sig_nullify boon (apply_signature_
        modifier was never called for it, so none of its effects are actually
        active). Also hints if the NEXT chapter's signature is queued to be
        nullified. Shared by the combat embed and the respite embed so they
        never show inconsistent signature info.
        """
        chapter = self.current_chapter
        if self._current_chapter_nullified:
            sig_text = f"Signature: ~~{chapter.signature_label}~~ (Nullified)"
        else:
            sig_text = f"Signature: {chapter.signature_label} — {chapter.signature_description}"
        if (
            self.run_state.get("sig_nullify_next")
            and self.chapter_idx < len(self.chapters) - 1
        ):
            next_name = self.chapters[self.chapter_idx + 1].name
            sig_text += f" | ⚡ Next chapter '{next_name}' signature NULLIFIED"
        return sig_text

    def _combat_layout(self) -> discord.ui.Container:
        chapter = self.current_chapter
        title = (
            f"{CODEX_TOME_EMOJI} Codex — {chapter.name} | Wave {self.wave_num}/7 "
            f"(Chapter {self.chapter_idx + 1}/5)"
        )
        container = combat_ui.create_combat_layout(
            self.player,
            self.monster,
            self.logs,
            title_override=title,
            player_avatar_url=self.player_avatar_url,
        )
        container.accent_color = discord.Color.dark_purple()
        container.add_item(discord.ui.TextDisplay(f"-# {self._signature_text()}"))
        return container

    def _snapshot_wave_baseline(self):
        """Snapshot base stats after chapter/boon setup but before combat passives fire.
        Restored at the top of every wave so combat-start passives (sturdy, omnipotent,
        absorb, juggernaut, gilded_hunger, diabolic_pact, cursed_precision, Enfeeble,
        Impenetrable) don't compound across waves."""
        self.chapter_wave_baseline = build_wave_baseline(self.player)

    def _restore_wave_baseline(self):
        """Reset per-combat bonuses and restore the post-setup snapshot before
        combat passives fire.  base_attack/defence are never mutated so only
        the bonus accumulator and multipliers need restoring."""
        if not self.chapter_wave_baseline:
            return
        self.player.reset_combat_bonus()
        self.player.bonus_crit = self.chapter_wave_baseline["bonus_crit"]
        self.player.bonus_max_hp = self.chapter_wave_baseline.get("bonus_max_hp", 0)
        self.player.bonus_def = self.chapter_wave_baseline.get("bonus_def", 0)
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
        self.player.codex_atk_pct = self.chapter_wave_baseline.get("codex_atk_pct", 0.0)
        self.player.codex_def_pct = self.chapter_wave_baseline.get("codex_def_pct", 0.0)
        self.player.codex_max_hp_pct = self.chapter_wave_baseline.get(
            "codex_max_hp_pct", 0.0
        )
        self.player.codex_crit_flat = self.chapter_wave_baseline.get(
            "codex_crit_flat", 0
        )
        # Safety: current_hp must never exceed the (possibly now-lower) restored
        # Max HP — e.g. entering respite right after a fight where combat-start
        # passives (Ward Inoculation, etc.) had temporarily inflated Max HP well
        # above this chapter baseline. The tighter "Enter each fight at X% HP"
        # cap is intentionally NOT re-applied here — it only makes sense against
        # the FINAL post-combat-start Max HP for the wave that's about to begin,
        # which isn't known yet at this point. See apply_hp_entry_cap(), called
        # after apply_combat_start_passives() in _setup_next_wave.
        self.player.current_hp = min(self.player.current_hp, self.player.total_max_hp)

    def _projected_ward(self) -> int:
        """Ward the player will have at the start of the next wave."""
        return self.chapter_wave_baseline.get("combat_ward", self.player.combat_ward)

    def _run_modifiers_text(self) -> str:
        """Compact summary of all active run-level stat modifiers.

        ATK/DEF/Max HP/Crit read directly from the authoritative codex_atk_pct/
        codex_def_pct/codex_max_hp_pct/codex_crit_flat fields (current chapter's
        signature + all active boons, already combined — see
        core/codex/mechanics.py) instead of re-summing active_boons by hand, so
        this can't drift from what get_total_attack/defence/max_hp/
        current_crit_chance actually apply — and, as a side effect, now
        includes the current chapter's signature, which the old hand-summed
        version omitted entirely. FDR similarly reads the dedicated boon_fdr
        accumulator. Ward/Page Rate have no dedicated accumulator field, so
        those two stay hand-summed from active_boons.

        This only covers the NUMERIC stat pool (ATK/DEF/Max HP/Crit/FDR/Ward/
        Page Rate/Fragments/run bonuses) — non-poolable signature-only effects
        (hit_flat, crit_dmg_pct, pdr_pct, ward_gen_pct, hp_entry_pct,
        ward_disable) have no boon counterpart to combine with and are fully
        covered by the chapter signature's own description instead — see
        _signature_text(), shown separately in the respite embed.
        """
        p = self.player
        parts = []

        ward_boost = sum(b.value for b in self.active_boons if b.type == "ward_boost")
        page_rate_boost = sum(
            b.value for b in self.active_boons if b.type == "page_rate_boost"
        )

        atk_pct = p.codex_atk_pct * 100
        if atk_pct:
            parts.append(f"ATK {atk_pct:+.0f}%")
        if p.run_atk_penalty:
            parts.append(f"ATK −{p.run_atk_penalty}")

        def_pct = p.codex_def_pct * 100
        if def_pct:
            parts.append(f"DEF {def_pct:+.0f}%")
        if p.run_def_penalty:
            parts.append(f"DEF −{p.run_def_penalty}")

        max_hp_pct = p.codex_max_hp_pct * 100
        if max_hp_pct:
            parts.append(f"Max HP {max_hp_pct:+.0f}%")

        if p.codex_crit_flat:
            parts.append(f"Crit {p.codex_crit_flat:+d}")
        if p.run_crit_penalty:
            parts.append(f"Crit −{p.run_crit_penalty}")

        if p.boon_fdr:
            parts.append(f"FDR +{p.boon_fdr}")
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
            parts.append(f"{CODEX_PAGE_EMOJI} Page (this chapter)")
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

        # Hit chance — canonical getter (matches the stats page exactly:
        # 95% base cap, essence hit_pct, Alchemy Enrage, Deadeye, emblem,
        # companion, and Codex chapter_hit_penalty are all included).
        if p.get_glove_corrupted_essence() == "neet":
            hit_total = 0
        else:
            hit_total = p.get_total_hit_chance()

        # Crit chance — includes piercing passive + partner bonus (matches engine)
        crit_chance = calculate_crit_chance(p)

        # Crit multiplier — canonical getter (matches the stats page exactly).
        # chapter_crit_dmg_reduction is intentionally NOT part of this total —
        # same treatment as Nullifying, applied downstream at damage-calc time
        # rather than baked into the "stat" itself.
        crit_multi = p.get_weapon_crit_multi()

        block = p.get_total_block()
        evasion = p.get_total_evasion()

        hp_line = f"{STAT_HP} **{p.current_hp:,}/{eff_max_hp:,}**"
        proj_ward = self._projected_ward()
        if proj_ward > 0:
            hp_line += f"  {STAT_WARD} Ward (next wave): **{proj_ward:,}**"
        stats_block = (
            f"{STAT_ATK} ATK: **{atk:,}**  {STAT_DEF} DEF: **{def_:,}**\n"
            f"{hp_line}\n"
            f"🎯 Hit: **{hit_total}%**  🗡️ Crit: **{crit_chance}%**  ×{crit_multi:.2f}"
        )
        if fdr > 0 or pdr > 0:
            stats_block += f"\n{STAT_FDR} FDR: **{fdr}**  {STAT_PDR} PDR: **{pdr}%**"
        if block > 0 or evasion > 0:
            be_parts = []
            if block > 0:
                be_parts.append(f"{STAT_BLOCK} Block: **{block}%**")
            if evasion > 0:
                be_parts.append(f"{DODGE_EVASION} Evasion: **{evasion}%**")
            stats_block += "\n" + "  ".join(be_parts)

        reroll_hint = (
            "\n*(🔄 Reroll available — one use per chapter)*"
            if reroll_available
            else ""
        )
        embed = discord.Embed(
            title=f"⚗️ Respite — {chapter.name}",
            description=(
                f"A moment of stillness between the waves.\n"
                f"Here are your flat stats (no combat start bonuses):\n"
                f"{stats_block}\n\n"
                f"Choose a modifier:{reroll_hint}"
            ),
            color=discord.Color.teal(),
        )
        embed.set_thumbnail(url=CODEX_BOON)
        for i, boon in enumerate(boons, 1):
            field_name = f"Option {i}: {boon.label}"
            if boon.downside_label:
                field_name += f"  ⚠️ {boon.downside_label}"
            embed.add_field(name=field_name, value=boon.description, inline=False)
        # Shown separately from "Run Modifiers" below — this chapter's raw
        # signature (monster buffs + player debuffs, including hit/crit-dmg/
        # PDR/ward-gen/"enter at X% HP" effects that have no numeric stat-pool
        # equivalent to combine with a boon), same text as the in-combat embed.
        embed.add_field(
            name=f"{CODEX_TOME_EMOJI} Chapter Signature",
            value=self._signature_text().removeprefix("Signature: "),
            inline=False,
        )
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
        embed.add_field(name=f"{GOLD_COIN} Gold", value=f"{gold:,}", inline=True)
        if page_dropped:
            embed.add_field(
                name=f"{CODEX_PAGE_EMOJI} Codex Page",
                value="A Codex Page dropped!",
                inline=False,
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
                name=f"{CODEX_TOME_EMOJI} Next: {next_ch.name}",
                value=sig_info,
                inline=False,
            )
            embed.set_footer(text="Continuing in 4 seconds...")
        else:
            embed.set_footer(text="Run complete! Finalising in 4 seconds...")
        return embed

    def _summary_embed(
        self,
        fragments: int,
        pages_dropped: int,
        exp_changes: dict,
        quest_msgs: list | None = None,
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
            title=f"{CODEX_TOME_EMOJI} Codex Run Complete",
            description=description,
            color=discord.Color.gold() if is_perfect else discord.Color.blurple(),
        )
        embed.add_field(
            name="📚 Total XP", value=f"{self.cumulative_xp:,}", inline=True
        )
        embed.add_field(
            name=f"{GOLD_COIN} Total Gold",
            value=f"{self.cumulative_gold:,}",
            inline=True,
        )
        if exp_changes["ascensions_gained"]:
            embed.add_field(
                name="✨ Ascensions",
                value=str(exp_changes["ascensions_gained"]),
                inline=True,
            )
        embed.add_field(
            name=f"{CODEX_FRAGMENT_EMOJI} Fragments Earned",
            value=str(fragments),
            inline=True,
        )
        if pages_dropped > 0:
            embed.add_field(
                name=f"{CODEX_PAGE_EMOJI} Codex Pages",
                value=str(pages_dropped),
                inline=True,
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
        if quest_msgs:
            embed.add_field(
                name="📋 Quest Progress", value="\n".join(quest_msgs), inline=False
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
            self._current_chapter_nullified = nullify
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
        apply_hp_entry_cap(self.player)

        self.combat_logger = CombatLogger(self.player, self.monster)
        self.combat_logger.log_combat_start(self.player, self.monster)

        self._update_buttons()
        self._sync_items(self._combat_layout())

        msg_obj = message or (
            await interaction.original_response() if interaction else None
        )
        if msg_obj:
            await msg_obj.edit(view=self)

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

    def _build_respite_rows(
        self, boons: list[CodexBoon], reroll_available: bool
    ) -> list[discord.ui.ActionRow]:
        """One ActionRow per boon (label can run long) plus an optional
        reroll row. Built fresh each respite/reroll since the boon choices
        are randomised per call."""
        rows = []
        for boon in boons:
            label = boon.label
            if boon.downside_label:
                label = f"{label} / ⚠️ {boon.downside_label}"
            row = discord.ui.ActionRow()
            btn = discord.ui.Button(label=label[:80], style=ButtonStyle.primary)
            btn.callback = self._make_boon_callback(boon)
            row.add_item(btn)
            rows.append(row)
        if reroll_available:
            row = discord.ui.ActionRow()
            btn = discord.ui.Button(
                label="Reroll Choices", style=ButtonStyle.secondary, emoji="🔄"
            )
            btn.callback = self.handle_reroll
            row.add_item(btn)
            rows.append(row)
        return rows

    def _make_boon_callback(self, boon: CodexBoon):
        async def callback(interaction: Interaction):
            await self.handle_boon_choice(interaction, boon)

        return callback

    def _sync_respite_items(self, boons: list[CodexBoon], reroll_available: bool):
        self.clear_items()
        self.add_item(
            combat_ui.embed_to_container(
                self._respite_embed(boons, reroll_available=reroll_available)
            )
        )
        for row in self._build_respite_rows(boons, reroll_available):
            self.add_item(row)

    async def _enter_respite(
        self, interaction: Interaction = None, message: discord.Message = None
    ):
        """Swap to respite state with 2 randomly weighted boons."""
        self._boon_processing = False
        # Wipe mid-fight transient noise (stacks, ward changes, etc.) left over
        # from the wave that just ended before showing stats — respite should
        # display the clean chapter baseline the next wave will actually start
        # from, matching the stats page's methodology, not whatever combat-start
        # passives happened to be active when the last monster died.
        self._restore_wave_baseline()
        boons = roll_boons(2)
        reroll_available = self.chapter_idx not in self.reroll_used_chapters
        self._sync_respite_items(boons, reroll_available)

        msg_obj = message or (
            await interaction.original_response() if interaction else None
        )
        if msg_obj:
            await msg_obj.edit(view=self)

    async def handle_reroll(self, interaction: Interaction):
        """Re-rolls both boon choices (once per chapter)."""
        await interaction.response.defer()
        self.reroll_used_chapters.add(self.chapter_idx)
        boons = roll_boons(2)
        self._sync_respite_items(boons, reroll_available=False)
        await (await interaction.original_response()).edit(view=self)

    async def handle_boon_choice(self, interaction: Interaction, boon: CodexBoon):
        """Processes the player's respite boon selection."""
        if self._boon_processing:
            await interaction.response.defer()
            return
        self._boon_processing = True
        await interaction.response.defer()
        apply_respite_boon(self.player, boon, self.active_boons, self.run_state)

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
        self._sync_items(combat_ui.embed_to_container(embed), interactive=False)
        msg_obj = message or (
            await interaction.original_response() if interaction else None
        )
        if msg_obj:
            await msg_obj.edit(view=self)

        await asyncio.sleep(4)

        next_idx = self.chapter_idx + 1
        if next_idx >= len(self.chapters):
            await self._handle_run_complete(msg_obj)
            return

        self.chapter_idx = next_idx
        self.wave_num = 1
        await self._save_run()  # checkpoint: cleared chapter banked

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

        quest_msgs = []
        try:
            from core.quests.mechanics import tick_quest_progress

            quest_msgs = await tick_quest_progress(
                self.bot, self.user_id, getattr(self, "server_id", ""), "codex_complete"
            )
        except Exception as e:
            print(f"[Quest tick error in codex]: {e}")

        # Atomic: deleting the saved run is the re-entry guard — a crash
        # between granting and deleting would let the run be resumed and
        # re-completed for duplicate fragments.
        async with self.bot.database.transaction():
            await self.bot.database.users.modify_currency(
                self.user_id, "codex_fragments", fragments
            )
            await self.bot.database.users.modify_gold(
                self.user_id, self.cumulative_gold
            )
            await self.bot.database.codex.delete_run(self.user_id, self.server_id)

        exp_changes = await ExperienceManager.add_experience(
            self.bot,
            self.user_id,
            self.player,
            self.cumulative_xp,
            server_id=self.server_id,
        )
        await self.bot.database.users.update_from_player_object(self.player)

        embed = self._summary_embed(
            fragments, len(self.page_drops), exp_changes, quest_msgs=quest_msgs
        )
        self.stop()
        self.bot.state_manager.clear_active(
            self.user_id
        )  # session-terminating exit from CodexRunView (set in begin_run)

        if message:
            lobby_view = CodexRunCompleteView(
                self.bot,
                self.user_id,
                self.player,
                embed,
                server_id=self.server_id,
                player_avatar_url=self.player_avatar_url,
            )
            await message.edit(view=lobby_view)

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
            name=f"{GOLD_COIN} Gold Forfeited",
            value=f"{chapter_gold_lost:,}",
            inline=True,
        )
        embed.add_field(name="💀 Deaths", value=str(self.deaths), inline=True)

        self._sync_items(combat_ui.embed_to_container(embed), interactive=False)
        msg_obj = message or (
            await interaction.original_response() if interaction else None
        )
        if msg_obj:
            await msg_obj.edit(view=self)

        await asyncio.sleep(4)

        if is_last_chapter:
            await self._handle_run_complete(msg_obj)
            return

        self.chapter_idx = next_idx
        self.wave_num = 1
        await self._save_run()  # checkpoint: death rolled back, next chapter
        if msg_obj:
            await self._setup_next_wave(message=msg_obj)

    # ------------------------------------------------------------------
    # Combat button helpers
    # ------------------------------------------------------------------

    def _update_buttons(self):
        """Re-enables every combat button, then re-applies Full Send's own
        HP-gated lock. Called after any state change that might have left
        buttons disabled mid-loop (Auto/Full Send) or stale from a previous
        wave."""
        for child in (*self.row1.children, *self.row2.children):
            child.disabled = False
        self._update_full_send_state()

    def _update_full_send_state(self):
        """Full Send unlocks once HP is at/below Auto's low-HP protection threshold (20%)."""
        self.row1.full_send_btn.disabled = not (
            0 < self.player.current_hp <= self.player.total_max_hp * 0.2
        )

    async def _refresh_ui(
        self, interaction: Interaction = None, message: discord.Message = None
    ):
        self._sync_items(self._combat_layout())
        if interaction and not interaction.response.is_done():
            await interaction.response.edit_message(view=self)
        elif message:
            await message.edit(view=self)
        elif interaction:
            await interaction.edit_original_response(view=self)

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
            self._update_full_send_state()
            await self._refresh_ui(interaction, message)

    # ------------------------------------------------------------------
    # Combat button handlers (dispatched from CodexCombatRow / CodexMetaRow)
    # ------------------------------------------------------------------

    async def _on_attack(self, interaction: Interaction):
        await interaction.response.defer()
        await self._execute_turn(message=interaction.message)

    async def _on_auto(self, interaction: Interaction):
        await interaction.response.defer()
        message = interaction.message

        # Disable all buttons for the duration of the auto loop
        for child in (*self.row1.children, *self.row2.children):
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
            self._update_buttons()
            self.logs["Auto-Wave"] = "🛑 Paused: Low HP Protection triggered!"
            await self._refresh_ui(message=message)
            await message.channel.send(
                f"<@{self.user_id}> ⚠️ Low HP Protection triggered — auto paused! "
                "**Full Send** is now available if you want to gamble on finishing the fight.",
                delete_after=15,
            )
        else:
            await self._check_state(message=message)

    async def _on_full_send(self, interaction: Interaction):
        """Unlocked at low HP (same threshold Auto warns on). Repeats attacks with
        no HP floor until the monster is defeated or the player dies."""
        await interaction.response.defer()
        message = interaction.message

        for child in (*self.row1.children, *self.row2.children):
            child.disabled = True
        await message.edit(view=self)

        while self.player.current_hp > 0 and self.monster.hp > 0:
            for _ in range(10):
                if self.player.current_hp <= 0 or self.monster.hp <= 0:
                    break
                p_log = engine.process_player_turn(self.player, self.monster)
                self.combat_logger.log_player_turn(p_log, self.monster)
                m_log = ""
                if self.monster.hp > 0:
                    m_log = engine.process_monster_turn(self.player, self.monster)
                    self.combat_logger.log_monster_turn(m_log, self.player)
                self.logs = {self.player.name: p_log, self.monster.name: m_log}

            if self.player.current_hp > 0 and self.monster.hp > 0:
                await self._refresh_ui(message=message)
                await asyncio.sleep(1.0)

        await self._check_state(message=message)

    async def _on_retreat(self, interaction: Interaction):
        """Persist the run and leave. Resume via /codex restarts the current
        chapter at wave 1 (this chapter's unbanked XP/gold are rolled back)."""
        await self._save_run(at_chapter_start=True)
        await self.bot.database.users.update_from_player_object(self.player)
        self.bot.state_manager.clear_active(
            self.user_id
        )  # session-terminating Save & Exit (top-level for "codex" active)
        self.stop()

        embed = discord.Embed(
            title="💾 Codex Run Saved",
            description=(
                f"**{self.player.name}** steps out of the Codex.\n"
                f"Chapters cleared so far: **{self.chapters_cleared}/5**.\n"
                f"Use **/codex → Resume Run** to continue from the start of "
                f"**Chapter {self.chapter_idx + 1}** — no Tome required."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="📚 XP Banked", value=f"{self.chapter_start_xp:,}", inline=True
        )
        embed.add_field(
            name=f"{GOLD_COIN} Gold Banked",
            value=f"{self.chapter_start_gold:,}",
            inline=True,
        )
        lobby_view = CodexRunCompleteView(
            self.bot,
            self.user_id,
            self.player,
            embed,
            server_id=self.server_id,
            player_avatar_url=self.player_avatar_url,
        )
        await interaction.response.edit_message(view=lobby_view)

    async def _on_abandon(self, interaction: Interaction):
        confirm = CodexAbandonConfirmView(self.bot, self)
        await interaction.response.edit_message(view=confirm)


class CodexAbandonConfirmRow(discord.ui.ActionRow["CodexAbandonConfirmView"]):
    @discord.ui.button(label="Abandon Run", style=ButtonStyle.danger, emoji="🗑️")
    async def confirm_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_confirm(interaction)

    @discord.ui.button(label="Cancel", style=ButtonStyle.secondary, emoji="↩️")
    async def cancel_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_cancel(interaction)


class CodexAbandonConfirmView(BaseLayoutView):
    """Confirmation gate for permanently discarding a Codex run."""

    def __init__(self, bot, run_view: "CodexRunView"):
        super().__init__(bot, parent=run_view)
        self.run_view = run_view
        self.row = CodexAbandonConfirmRow()

        embed = discord.Embed(
            title="🗑️ Abandon this run?",
            description=(
                "The saved run is **deleted** — no rewards, and the Antique "
                "Tome is **not** refunded.\n"
                f"Chapters cleared: {run_view.chapters_cleared}/5 | "
                f"XP: {run_view.cumulative_xp:,} | Gold: {run_view.cumulative_gold:,} "
                "— all lost."
            ),
            color=discord.Color.red(),
        )
        self.add_item(combat_ui.embed_to_container(embed))
        self.add_item(self.row)

    async def _on_confirm(self, interaction: Interaction):
        rv = self.run_view
        await self.bot.database.codex.delete_run(rv.user_id, rv.server_id)
        await self.bot.database.users.update_from_player_object(rv.player)
        self.bot.state_manager.clear_active(rv.user_id)  # session-terminating Abandon
        rv.stop()
        self.stop()

        embed = discord.Embed(
            title=f"{CODEX_TOME_EMOJI} Codex Abandoned",
            description=(
                f"**{rv.player.name}** abandoned the run.\n"
                f"Chapters cleared: **{rv.chapters_cleared}/5** — No rewards."
            ),
            color=discord.Color.light_grey(),
        )
        embed.add_field(
            name="📚 XP Accumulated (lost)",
            value=f"{rv.cumulative_xp:,}",
            inline=True,
        )
        embed.add_field(
            name=f"{GOLD_COIN} Gold Accumulated (lost)",
            value=f"{rv.cumulative_gold:,}",
            inline=True,
        )
        lobby_view = CodexRunCompleteView(
            self.bot,
            rv.user_id,
            rv.player,
            embed,
            server_id=rv.server_id,
            player_avatar_url=rv.player_avatar_url,
        )
        await interaction.response.edit_message(view=lobby_view)

    async def _on_cancel(self, interaction: Interaction):
        self.stop()
        self.run_view._sync_items(self.run_view._combat_layout())
        await interaction.response.edit_message(view=self.run_view)


class CodexLobbyReturnRow(discord.ui.ActionRow["CodexRunCompleteView"]):
    @discord.ui.button(label="Back to Lobby", style=ButtonStyle.primary, emoji="📖")
    async def back_to_lobby_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_back_to_lobby(interaction)


class CodexRunCompleteView(BaseLayoutView):
    """Shown after a Codex run ends (complete, retreat, or abandon) — lets
    the player jump back to the lobby. `header_embed` supplies the
    outcome-specific summary (Run Complete / Saved / Abandoned)."""

    def __init__(
        self,
        bot,
        user_id: str,
        player: Player,
        header_embed: discord.Embed,
        server_id: str = "",
        player_avatar_url: str | None = None,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.player_avatar_url = player_avatar_url
        self._processing = False
        self.row = CodexLobbyReturnRow()
        self.add_item(combat_ui.embed_to_container(header_embed))
        self.add_item(self.row)

    async def _on_back_to_lobby(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        from core.codex.views.menu_view import CodexMenuView

        cur = await self.bot.database.users.get_all_currencies(self.user_id)
        try:
            chapter_history = await self.bot.database.codex.get_chapter_clears(
                self.user_id
            )
        except Exception:
            chapter_history = {}

        saved_run = await self.bot.database.codex.get_run(self.user_id, self.server_id)

        menu = CodexMenuView(
            self.bot,
            self.user_id,
            self.player,
            cur["codex_fragments"],
            cur["codex_pages"],
            cur["codex_rerolls"],
            chapter_history,
            antique_tomes=cur["antique_tome"],
            server_id=self.server_id,
            saved_run=saved_run,
            player_avatar_url=self.player_avatar_url,
        )
        self.stop()
        await interaction.edit_original_response(view=menu)
