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

import json

import discord
from discord import ButtonStyle, Interaction, ui

from core.alchemy.mechanics import (
    DistillationMechanics,
    get_passive_name_emoji,
    get_passive_info,
)
from core.base_view import BaseView
from core.images import ALCHEMY_HUB


async def _get_alchemy_context(bot, user_id: str, server_id: str):
    """Small helper to fetch common alchemy state."""
    level = await bot.database.alchemy.get_level(user_id)
    dust = await bot.database.alchemy.get_cosmic_dust(user_id)
    return level, dust


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
    ):
        super().__init__(bot, user_id, server_id)
        self.alchemy_level = alchemy_level
        self.cosmic_dust = cosmic_dust
        self.session: dict = {}
        self._processing = False
        self._excluded_passive_types: list = excluded_passive_types or []
        # Session is loaded asynchronously via _ensure_session() when the view is started.

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
        dur = s.get("duration_mod", 0.0)
        val = s.get("value_mod", 0.0)

        embed = discord.Embed(
            title="🧪 Potion Distillation", color=discord.Color.purple()
        )
        embed.set_thumbnail(url=ALCHEMY_HUB)

        # ------------------------------------------------------------------
        # BASE CHOICE (initial 3 skills) — show brief desc + roll ranges for each
        # ------------------------------------------------------------------
        if step == 0 and not base:
            embed.description = (
                "You stand before the Great Alembic.\n\n"
                "**Step 1: Choose the core essence** — the base passive (skill) you will distill over the next 9 steps. "
                "Each choice below shows what the final passive does and the possible roll ranges for its strength and duration.\n\n"
                "After choosing, 8 reagent steps remain. Each reagent step has its own special properties (shown on the next screen)."
            )
            bases = DistillationMechanics.get_prepared_core_choices(s)
            for b in bases:
                embed.add_field(
                    name=f"{b['emoji']} {b['name']}",
                    value=b.get("desc", "Powerful distilled passive."),
                    inline=False,
                )
            embed.set_footer(text="Pick one. You cannot change the core later.")
            return embed

        # ------------------------------------------------------------------
        # REAGENT STEP
        # ------------------------------------------------------------------
        base_info = DistillationMechanics.POWERFUL_PASSIVES.get(base, {})
        display_step = max(
            1, step
        )  # after base choice we are on reagent step 1 even if internal counter is still 0

        safe_dust = max(0, self.cosmic_dust)
        projected_val, projected_dur = DistillationMechanics.project_values(s)
        passive_preview = DistillationMechanics.format_distilled_passive(
            base, projected_val, projected_dur
        )

        embed.description = (
            f"**Step {display_step} / {DistillationMechanics.STEPS}**\n"
            f"**Core:** {base_info.get('emoji', '⚗️')} **{base_info.get('name', base)}**\n\n"
            f"{passive_preview}\n\n"
            f"**Cosmic Dust:** ✨ {safe_dust:,}\n\n"
            'Choose a reagent below. The special properties for this step are listed under "Reagent Properties (this step)". '
            "Button labels preview the dust cost and resulting balance."
        )

        # Show the 3 special properties for the reagents this step (key per user spec)
        try:
            props = DistillationMechanics.get_prepared_reagent_options(s, step)
        except Exception:
            props = DistillationMechanics.get_reagent_options_for_step(s, step)

        if props:
            prop_lines = []
            for p in props:
                emoji = p.get("emoji", "⚗️")
                name = p.get("name", "Reagent")
                prop = p.get("property_desc") or p.get("desc", "Standard outcome.")
                prop_lines.append(f"{emoji} **{name}** — {prop}")
            embed.add_field(
                name="Reagent Properties (this step)",
                value="\n".join(prop_lines),
                inline=False,
            )

        # Active modifiers
        mods = s.get("active_modifiers", {})
        if mods:
            mod_lines = []
            if mods.get("free_next_steps"):
                mod_lines.append(f"🌿 Next {mods['free_next_steps']} step(s) are free")
            if mods.get("future_free_but_unlucky"):
                mod_lines.append("🌑 Future steps are free but **unlucky**")
            if mods.get("all_future_free"):
                mod_lines.append("✨ **All future steps cost no dust**")
            if mod_lines:
                embed.add_field(
                    name="Active Effects", value="\n".join(mod_lines), inline=False
                )

        # History
        history = s.get("history", [])[-4:]
        if history:
            h = "\n".join(
                f"• Step {h['step']}: {h.get('reagent', '?')} → {h.get('gain', '?')}"
                for h in history
            )
            embed.add_field(name="Recent Steps", value=h, inline=False)

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
                    label=f"{b['emoji']} {b['name']}",
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
                after = max(0, current - cost)
                cost_part = f"(-{cost}✨) " if cost > 0 else "(free) "
                label = f"{ch['emoji']} {ch['name']} {cost_part}({current}->{after})"
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

            # If we just advanced, prepare the properties for the *next* step now (so next embed/buttons are consistent)
            if s.get("step", 0) < DistillationMechanics.STEPS:
                DistillationMechanics.prepare_reagent_options(s, s.get("step", 0))

            # Build embed for the new state
            embed = self._build_embed()
            embed.colour = discord.Color.gold()
            embed.add_field(
                name=f"Step {result['step']} Result",
                value="\n".join(result.get("messages", [])),
                inline=False,
            )

            self._setup_current_buttons()
            self._processing = False

            if s.get("step", 0) >= DistillationMechanics.STEPS:
                await self._finalize_and_show_result(interaction, embed)
            else:
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

        # Place in first empty slot, or overwrite slot 1 if all full.
        passives = await self.bot.database.alchemy.get_potion_passives(self.user_id)
        occupied = {p["slot"] for p in passives}
        slot_count = 5
        slot = next((sl for sl in range(1, slot_count + 1) if sl not in occupied), 1)

        # Save with the actual distilled duration so the hub displays it correctly.
        await self.bot.database.alchemy.set_passive(
            self.user_id, slot, base_type, final_val, final_dur
        )

        await self._clear_session()

        # Edit original in-progress message to a clean "done" state (no buttons).
        done_embed = discord.Embed(
            title="✨ Distillation Complete!",
            description=(
                f"**{emoji} {name}** has been placed in **Slot {slot}**.\n"
                "Your new elixir details are in the message below."
            ),
            color=discord.Color.gold(),
        )
        await interaction.edit_original_response(embed=done_embed, view=None)

        # Send the full result as a separate followup message with the hub.
        from core.alchemy.views import _hub_from_db

        hub = await _hub_from_db(self.bot, self.user_id, self.server_id)
        result_embed = hub.build_embed()
        result_embed.title = "⚗️ Alchemy — New Elixir Ready"
        result_embed.colour = discord.Color.gold()
        result_embed.insert_field_at(
            0,
            name=f"✨ {emoji} {name} (distilled)",
            value=f"*{final_desc}*\nPlaced in **Slot {slot}**.",
            inline=False,
        )

        try:
            msg = await interaction.followup.send(
                embed=result_embed, view=hub, ephemeral=False
            )
            hub.message = msg
        except Exception:
            pass

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


# Convenience launcher (similar to _build_synthesis_hub)
async def start_distillation(
    bot,
    user_id: str,
    server_id: str,
    interaction: Interaction,
    excluded_passive_types: list | None = None,
):
    level, dust = await _get_alchemy_context(bot, user_id, server_id)
    view = PotionDistillationView(
        bot, user_id, server_id, level, dust, excluded_passive_types
    )
    await view.start(interaction)
