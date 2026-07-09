"""
core/alchemy/distillation_views.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
9-step Potion Distillation (Sage Elixir style) — the new deep crafting system
for powerful, encounter-changing potion passives.

Replaces the old instant "Synthesize" fantasy with meaningful repeated choices,
Cosmic Dust costs, and random events that create high-variance exciting outcomes.

All views extend BaseView. Session state is persisted in the DB so players can
log out and resume.
"""

import discord
from discord import ButtonStyle, Interaction, ui

from core.alchemy.mechanics import (
    DistillationMechanics,
    get_passive_name_emoji,
)
from core.base_view import BaseView
from core.emojis import COSMIC_DUST, POTION
from core.images import ELYNDRA_PORTRAIT, ELYNDRA_THUMBNAIL
from core.npc_voices import get_quip


async def _get_alchemy_context(bot, user_id: str, server_id: str):
    """Small helper to fetch common alchemy state."""
    level = await bot.database.alchemy.get_level(user_id)
    dust = await bot.database.alchemy.get_cosmic_dust(user_id)
    return level, dust


def _pct_bar(frac: float, width: int = 10) -> str:
    filled = max(0, min(width, round(frac * width)))
    return "█" * filled + "░" * (width - filled)


class PotionDistillationView(BaseView):
    """
    The main interactive 9-step distillation view.
    """

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        alchemy_level: int,
        cosmic_dust: int,
        excluded_passive_types: list | None = None,
        target_slot: int | None = None,
    ):
        super().__init__(bot, user_id, server_id)
        self.alchemy_level = alchemy_level
        self.cosmic_dust = cosmic_dust
        self.session: dict = {}
        self._processing = False
        self._excluded_passive_types: list = excluded_passive_types or []
        self._target_slot: int | None = target_slot

    async def _ensure_session(self):
        # Always load latest from DB to ensure persistence across steps (e.g. base choice)
        row = await self.bot.database.alchemy.get_distillation(
            self.user_id, self.server_id
        )
        if row:
            self.session = row["data"] or {}
            self.session["step"] = row.get("step", 0)
        else:
            self.session = DistillationMechanics.start_distillation(
                self.alchemy_level, self._excluded_passive_types
            )
            if self._target_slot is not None:
                self.session["target_slot"] = self._target_slot
            await self._save_session()

        # Keep dust fresh for accurate (current->after) previews on buttons.
        # Guardrail: if negative (from any previous bug or desync), reset to 0.
        try:
            fresh = await self.bot.database.alchemy.get_cosmic_dust(self.user_id)
            if fresh < 0:
                # Reset to 0 in DB
                delta = -fresh
                await self.bot.database.alchemy.modify_cosmic_dust(self.user_id, delta)
                fresh = 0
            self.cosmic_dust = fresh
        except Exception:
            pass

    async def _save_session(self):
        await self.bot.database.alchemy.upsert_distillation(
            self.user_id, self.server_id, self.session.get("step", 0), self.session
        )

    async def _clear_session(self):
        await self.bot.database.alchemy.delete_distillation(
            self.user_id, self.server_id
        )
        self.session = {}
        self.bot.state_manager.clear_active(self.user_id)

    def _build_embed(self) -> discord.Embed:
        s = self.session
        step = s.get("step", 0)
        base = s.get("base_type")

        embed = discord.Embed(
            title=f"{POTION} Potion Distillation", color=discord.Color.purple()
        )
        embed.set_author(name="Master Alchemist Elyndra", icon_url=ELYNDRA_PORTRAIT)
        embed.set_thumbnail(url=ELYNDRA_THUMBNAIL)

        # ------------------------------------------------------------------
        # BASE CHOICE (initial 3 skills) — show brief desc + roll ranges for each
        # ------------------------------------------------------------------
        if step == 0 and not base:
            embed.description = (
                f"*{get_quip('alchemy')}*\n\n"
                "I've prepared three formulations. Each one will anchor the elixir's core effect — "
                "choose carefully, because once the distillation begins, there's no going back.\n\n"
                "The next nine steps determine how potent your result is. "
                "Each reagent step carries its own properties — read them before you commit."
            )
            bases = DistillationMechanics.get_prepared_core_choices(s)
            for b in bases:
                embed.add_field(
                    name=f"{b['emoji']} {b['name']}",
                    value=b.get("desc", "Powerful distilled passive."),
                    inline=False,
                )
            embed.set_footer(text="Your choice is final. Make it count.")
            return embed

        # ------------------------------------------------------------------
        # REAGENT STEP
        # ------------------------------------------------------------------
        base_info = DistillationMechanics.POWERFUL_PASSIVES.get(base, {})
        # step is the number of reagent steps *completed*, so the current choice is step+1
        display_step = min(step + 1, DistillationMechanics.STEPS)

        safe_dust = max(0, self.cosmic_dust)
        projected_val, projected_dur = DistillationMechanics.project_values(s)
        passive_preview = DistillationMechanics.format_distilled_passive(
            base, projected_val, projected_dur
        )

        # Compute bar fractions directly from raw accumulators to avoid rounding
        # artifacts from back-calculating through project_values' rounded output.
        raw_max = DistillationMechanics.get_raw_max(s)
        val_frac = (
            min(1.0, max(0.0, s.get("value_mod", 0.0)) / raw_max)
            if raw_max > 0
            else 0.0
        )
        dur_frac = (
            min(1.0, max(0.0, s.get("duration_mod", 0.0)) / raw_max)
            if raw_max > 0
            else 0.0
        )
        val_pct = int(val_frac * 100)
        dur_pct = int(dur_frac * 100)

        is_last_step = display_step >= DistillationMechanics.STEPS
        step_note = (
            "⚠️ **Final step — choose well.**"
            if is_last_step
            else "Pick a reagent — each carries a different property this step."
        )
        embed.description = (
            f"**Step {display_step} / {DistillationMechanics.STEPS}** · {COSMIC_DUST} {safe_dust:,} dust\n"
            f"**Core:** {base_info.get('emoji', '⚗️')} **{base_info.get('name', base)}**\n\n"
            f"{passive_preview}\n\n"
            f"`Power   ` {_pct_bar(val_frac)} {val_pct}%\n"
            f"`Duration` {_pct_bar(dur_frac)} {dur_pct}%\n\n"
            f"{step_note}"
        )

        # Show the 3 special properties for the reagents this step (key per user spec)
        try:
            props = DistillationMechanics.get_prepared_reagent_options(s, step)
        except Exception:
            props = DistillationMechanics.get_reagent_options_for_step(s, step)

        if props:
            prop_lines = []
            for p in props:
                r_emoji = p.get("emoji", "⚗️")
                r_name = p.get("name", "Reagent")
                event = p.get("event", {})
                e_name = event.get("name", "Standard")
                e_desc = p.get("property_desc") or event.get(
                    "desc", "Standard outcome."
                )
                prop_lines.append(f"{r_emoji} {r_name} — **{e_name}**: {e_desc}")
            embed.add_field(
                name="Reagent Properties",
                value="\n".join(prop_lines),
                inline=False,
            )

        # Active modifiers
        mods = s.get("active_modifiers", {})
        mod_lines = []
        if mods.get("free_next_steps"):
            n = mods["free_next_steps"]
            if n == 1:
                mod_lines.append("🌿 **This step** costs no dust")
            else:
                mod_lines.append(
                    f"🌿 **This step** costs no dust *(+{n - 1} more after)*"
                )
        if mods.get("all_future_free"):
            mod_lines.append(f"{COSMIC_DUST} **All remaining steps cost no dust**")
        future_mult = mods.get("future_cost_mult")
        if future_mult and future_mult < 1.0:
            pct_off = int((1.0 - future_mult) * 100)
            mod_lines.append(f"💸 This and future steps cost **{pct_off}% less** dust")
        if mods.get("lucky"):
            mod_lines.append("🍀 **This step** is lucky")
        if mod_lines:
            embed.add_field(
                name="Active Effects", value="\n".join(mod_lines), inline=False
            )

        # History
        history = s.get("history", [])[-4:]
        if history:
            h_lines = []
            for h in history:
                label = h.get("reagent_label") or h.get("reagent", "?")
                h_lines.append(f"• Step {h['step']}: {label} → {h.get('gain', '?')}")
            embed.add_field(name="Recent Steps", value="\n".join(h_lines), inline=False)

        return embed

    def _setup_current_buttons(self):
        """Clear and add the appropriate choice buttons (base or reagents) based on current session state.
        Reagent buttons now include dust previews (current->after) and use the pre-chosen properties for the step.
        """
        self.clear_items()
        s = self.session
        step = s.get("step", 0)
        base = s.get("base_type")

        if step == 0 and not base:
            # Base choice phase — short labels; full desc + ranges live in the embed.
            # Use the prepared list so the buttons exactly match the fields shown above.
            bases = DistillationMechanics.get_prepared_core_choices(s)
            for i, b in enumerate(bases):
                btn = ui.Button(
                    label=b["name"],
                    emoji=b["emoji"],
                    style=ButtonStyle.primary,
                    row=i // 3,
                )
                btn.callback = self._make_base_callback(i)
                self.add_item(btn)
        else:
            # Reagent step: use the *prepared* (fixed for this step) options so embed/buttons/apply all agree
            try:
                choices = DistillationMechanics.get_prepared_reagent_options(s, step)
            except Exception:
                choices = DistillationMechanics.get_reagent_options_for_step(s, step)

            current = max(0, self.cosmic_dust)
            for i, ch in enumerate(choices):
                cost = ch.get("effective_cost", 0)
                cost_part = f" (-{cost}{COSMIC_DUST})" if cost > 0 else " (free)"
                label = f"{ch['emoji']} {ch['name']}{cost_part}"
                style = (
                    ButtonStyle.secondary
                    if ch["key"] == "blue"
                    else (
                        ButtonStyle.success
                        if ch["key"] == "green"
                        else ButtonStyle.danger
                    )
                )
                # Disable choices the player literally cannot afford (prevents negative dust).
                # Properties that set cost_mult=0 or free_next will correctly produce cost=0 and stay enabled.
                can_afford = (cost <= 0) or (cost <= current)
                btn = ui.Button(
                    label=label[:80],
                    style=style,
                    row=i // 3,
                    disabled=not can_afford,
                )
                btn.callback = self._make_reagent_callback(i)
                self.add_item(btn)

        # Always offer abandon
        abandon = ui.Button(
            label="Abandon Distillation", style=ButtonStyle.danger, emoji="🗑️", row=2
        )
        abandon.callback = self._on_abandon
        self.add_item(abandon)

    async def _send_choices(self, interaction: Interaction):
        """Send or update the view with the current choices."""
        await self._ensure_session()
        s = self.session

        # Guard: session already complete (e.g. bot restart with step=9 in DB).
        # Show confirm/abandon instead of reagent buttons so the player can't do a 10th step.
        if s.get("step", 0) >= DistillationMechanics.STEPS and s.get("base_type"):
            confirm_view = _ConfirmOrAbandonView(
                self.bot, self.user_id, self.server_id, self
            )
            embed = self._build_embed()
            embed.set_footer(
                text="Distillation complete — confirm to keep this passive, or abandon the run."
            )
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=confirm_view)
            else:
                await interaction.response.edit_message(embed=embed, view=confirm_view)
            self.stop()
            return

        # Lock in the 3 core choices for this presentation (prevents re-randomizing between
        # embed fields, button labels, and the click handler that assigns base_type).
        if s.get("step", 0) == 0 and not s.get("base_type"):
            DistillationMechanics.prepare_core_choices(s)
            await self._save_session()

        embed = self._build_embed()
        self._setup_current_buttons()

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    def _make_base_callback(self, idx: int):
        async def cb(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            self._processing = True
            await interaction.response.defer()

            await self._ensure_session()
            s = self.session

            # Use the *exact same* prepared list that was used to build the embed fields and buttons.
            # This guarantees the button the user clicked corresponds to the passive whose
            # description they saw and that we store the correct base_type.
            cores = DistillationMechanics.get_prepared_core_choices(s)
            if 0 <= idx < len(cores):
                self.session["base_type"] = cores[idx]["key"]
            else:
                # Fallback (should never happen)
                self.session["base_type"] = list(
                    DistillationMechanics.POWERFUL_PASSIVES.keys()
                )[0]

            self.session["step"] = 0  # will become 1 on first reagent apply

            # Clean up the transient draft list
            s.pop("core_choices", None)

            # Prepare the 3 reagent properties for the *first* reagent step
            DistillationMechanics.prepare_reagent_options(self.session, 0)

            await self._save_session()

            embed = self._build_embed()
            self._setup_current_buttons()
            self._processing = False
            await interaction.edit_original_response(embed=embed, view=self)

        return cb

    def _make_reagent_callback(self, idx: int):
        async def cb(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            self._processing = True
            await interaction.response.defer()

            await self._ensure_session()
            s = self.session
            current_step = s.get("step", 0)

            # Guard: stale button click after session already completed (race with self.stop()).
            if current_step >= DistillationMechanics.STEPS:
                confirm_view = _ConfirmOrAbandonView(
                    self.bot, self.user_id, self.server_id, self
                )
                embed = self._build_embed()
                embed.set_footer(
                    text="Distillation complete — confirm to keep this passive, or abandon the run."
                )
                await interaction.edit_original_response(embed=embed, view=confirm_view)
                self.stop()
                self._processing = False
                return

            # Get the *exact* property set that was shown for this step (guarantees button <-> effect match)
            try:
                opts = DistillationMechanics.get_prepared_reagent_options(
                    s, current_step
                )
            except Exception:
                opts = DistillationMechanics.get_reagent_options_for_step(
                    s, current_step
                )

            chosen_event = None
            preview_cost = 0
            if 0 <= idx < len(opts):
                chosen_event = opts[idx].get("event")
                preview_cost = opts[idx].get("effective_cost", 0)

            # Apply using the property the user actually selected
            result = DistillationMechanics.apply_step(
                s, idx, pre_chosen_event=chosen_event
            )

            # Dust guardrail: never let cost push us negative. Charge only what we have.
            # result["cost"] may already be adjusted by refunds etc.
            cost = result.get("cost", preview_cost)
            if cost > 0:
                actual = min(cost, max(0, self.cosmic_dust))
                if actual > 0:
                    await self.bot.database.alchemy.modify_cosmic_dust(
                        self.user_id, -actual
                    )
                    self.cosmic_dust = max(0, self.cosmic_dust - actual)

            await self._save_session()

            # Prepare properties for the *next* step and save again immediately.
            # Without this second save, _ensure_session on the next click reloads the old
            # (pre-preparation) options from DB and the fallback regenerates different random
            # events from what the buttons actually show — causing every property mismatch bug.
            if s.get("step", 0) < DistillationMechanics.STEPS:
                DistillationMechanics.prepare_reagent_options(s, s.get("step", 0))
                await self._save_session()

            # Build embed for the new state
            embed = self._build_embed()
            embed.colour = discord.Color.gold()
            embed.add_field(
                name=f"Step {result['step']} Result",
                value="\n".join(result.get("messages", [])),
                inline=False,
            )

            self._processing = False

            if s.get("step", 0) >= DistillationMechanics.STEPS:
                # Show last step's result with confirm/abandon buttons before writing the passive
                confirm_view = _ConfirmOrAbandonView(
                    self.bot, self.user_id, self.server_id, self
                )
                embed.set_footer(
                    text="Distillation complete — confirm to keep this passive, or abandon the run."
                )
                await interaction.edit_original_response(embed=embed, view=confirm_view)
                self.stop()
            else:
                self._setup_current_buttons()
                await interaction.edit_original_response(embed=embed, view=self)

        return cb

    async def _finalize_and_show_result(
        self, interaction: Interaction, previous_embed: discord.Embed
    ):
        s = self.session
        base_type, final_val, final_dur = DistillationMechanics.finalize(s)

        name, emoji = get_passive_name_emoji(base_type)
        final_desc = DistillationMechanics.format_distilled_passive(
            base_type, final_val, final_dur
        )

        # Resolve the target slot.
        passives = await self.bot.database.alchemy.get_potion_passives(self.user_id)
        passive_by_slot = {p["slot"]: p for p in passives}
        occupied = set(passive_by_slot.keys())
        slot_count = 5
        target = s.get("target_slot")
        if target and 1 <= target <= slot_count:
            slot = target
        else:
            slot = next(
                (sl for sl in range(1, slot_count + 1) if sl not in occupied), 1
            )

        # If the slot is occupied, offer a keep-or-replace choice instead of writing directly.
        if slot in occupied:
            old_p = passive_by_slot[slot]
            old_name, old_emoji = get_passive_name_emoji(old_p["passive_type"])
            from core.alchemy.mechanics import AlchemyMechanics

            old_desc = AlchemyMechanics.format_passive(
                old_p["passive_type"],
                old_p["passive_value"],
                old_p.get("passive_duration", 2.0),
            )
            choice_view = _KeepOrReplaceView(
                self.bot,
                self.user_id,
                self.server_id,
                slot=slot,
                new_base_type=base_type,
                new_val=final_val,
                new_dur=final_dur,
                distill_view=self,
            )
            choice_embed = discord.Embed(
                title=f"{POTION} Distillation Complete — Choose Your Passive",
                color=discord.Color.gold(),
            )
            choice_embed.set_author(
                name="Master Alchemist Elyndra", icon_url=ELYNDRA_PORTRAIT
            )
            choice_embed.set_thumbnail(url=ELYNDRA_THUMBNAIL)
            choice_embed.description = (
                f"*The ritual is done. Slot {slot} is already occupied — you decide what stays.*\n\n"
                f"**New:** {emoji} **{name}**\n{final_desc}\n\n"
                f"**Current:** {old_emoji} **{old_name}**\n{old_desc}"
            )
            await interaction.edit_original_response(
                embed=choice_embed, view=choice_view
            )
            self.stop()
            return

        # Slot is empty — write directly.
        await self._write_passive_and_show_hub(
            interaction, slot, base_type, final_val, final_dur, name, emoji, final_desc
        )

    async def _write_passive_and_show_hub(
        self,
        interaction: Interaction,
        slot: int,
        base_type: str,
        final_val: float,
        final_dur: float,
        name: str,
        emoji: str,
        final_desc: str,
    ):
        await self.bot.database.alchemy.set_passive(
            self.user_id, slot, base_type, final_val, final_dur
        )
        await self._clear_session()

        from core.alchemy.views import _hub_from_db

        hub = await _hub_from_db(self.bot, self.user_id, self.server_id)
        result_embed = hub.build_embed()
        result_embed.title = f"{POTION} Alchemy — New Elixir Ready"
        result_embed.colour = discord.Color.gold()
        result_embed.insert_field_at(
            0,
            name=f"✨ {emoji} {name} (distilled)",
            value=f"{final_desc}\nPlaced in **Slot {slot}**.",
            inline=False,
        )
        msg = await interaction.edit_original_response(embed=result_embed, view=hub)
        hub.message = msg
        self.stop()

    async def _on_abandon(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        await self._clear_session()
        self._processing = False

        from core.alchemy.views import _hub_from_db

        view = await _hub_from_db(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        embed.title = "🗑️ Distillation Abandoned"
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    # Entry point used by other views
    async def start(self, interaction: Interaction):
        # Ensure we are marked active for the distillation flow
        self.bot.state_manager.set_active(self.user_id, "alchemy_distill")
        await self._ensure_session()
        await self._send_choices(interaction)


class _ConfirmOrAbandonView(BaseView):
    """Shown after the final distillation step so the player can see the result before committing."""

    def __init__(
        self, bot, user_id: str, server_id: str, distill_view: "PotionDistillationView"
    ):
        super().__init__(bot, user_id, server_id)
        self._distill_view = distill_view
        self._processing = False

    @ui.button(label="Confirm Distillation", style=ButtonStyle.green, emoji="✨")
    async def confirm(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        await self._distill_view._finalize_and_show_result(interaction, None)
        self.stop()

    @ui.button(label="Abandon", style=ButtonStyle.danger, emoji="🗑️")
    async def abandon(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        await self._distill_view._clear_session()

        from core.alchemy.views import _hub_from_db

        hub = await _hub_from_db(self.bot, self.user_id, self.server_id)
        embed = hub.build_embed()
        embed.title = "🗑️ Distillation Abandoned"
        msg = await interaction.edit_original_response(embed=embed, view=hub)
        hub.message = msg
        self.stop()


class _KeepOrReplaceView(BaseView):
    """Shown at the end of distillation when the target slot is already occupied."""

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        slot: int,
        new_base_type: str,
        new_val: float,
        new_dur: float,
        distill_view: "PotionDistillationView",
    ):
        super().__init__(bot, user_id, server_id)
        self._slot = slot
        self._new_base_type = new_base_type
        self._new_val = new_val
        self._new_dur = new_dur
        self._distill_view = distill_view
        self._processing = False

    @ui.button(label="Use New Passive", style=ButtonStyle.green, emoji="✨")
    async def use_new(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        new_name, new_emoji = get_passive_name_emoji(self._new_base_type)
        new_desc = DistillationMechanics.format_distilled_passive(
            self._new_base_type, self._new_val, self._new_dur
        )
        await self._distill_view._write_passive_and_show_hub(
            interaction,
            self._slot,
            self._new_base_type,
            self._new_val,
            self._new_dur,
            new_name,
            new_emoji,
            new_desc,
        )
        self.stop()

    @ui.button(label="Keep Current", style=ButtonStyle.secondary, emoji="🔒")
    async def keep_old(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        await self._distill_view._clear_session()

        from core.alchemy.views import _hub_from_db

        hub = await _hub_from_db(self.bot, self.user_id, self.server_id)
        embed = hub.build_embed()
        embed.title = f"{POTION} Alchemy — Passive Kept"
        msg = await interaction.edit_original_response(embed=embed, view=hub)
        hub.message = msg
        self.stop()


# Convenience launcher (similar to _build_synthesis_hub)
async def start_distillation(
    bot,
    user_id: str,
    server_id: str,
    interaction: Interaction,
    excluded_passive_types: list | None = None,
    target_slot: int | None = None,
):
    level, dust = await _get_alchemy_context(bot, user_id, server_id)
    view = PotionDistillationView(
        bot,
        user_id,
        server_id,
        level,
        dust,
        excluded_passive_types,
        target_slot=target_slot,
    )
    await view.start(interaction)
