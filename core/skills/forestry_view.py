import asyncio
import random
import time

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.base_view import BaseView
from core.images import MASTERY_WOODCUTTING
from core.skills.mechanics import SkillMechanics

# Probability that any knot blocks the next swing.
KNOT_CHANCE = 0.25
# Of those, 70% are simple knots (1 click) and 30% are tight knots (2 clicks: Pry → Clear).
TIGHT_KNOT_FRACTION = 0.30


class ForestryView(BaseView):
    def __init__(self, bot, user_id: str, server_id: str, *, parent_gather_view=None):
        super().__init__(bot, user_id, server_id)
        self.parent_gather_view = parent_gather_view

        self.state = "idle"  # idle | chopping | cooldown | ready
        self.skill_data = None
        self.user_data = None

        self.swings_remaining = 0
        # Knot state: None | "knot" (1-click clear) | "tight_knot_pry" (needs Pry first) | "tight_knot_clear" (needs final Clear)
        self.knot_state: str | None = None

        # Yield from last felled tree, mapped to display names.
        self.last_yield: dict[str, int] = {}

        # Session depth: rhythm tracking
        self.rhythm_hits: int = 0
        self.total_swings: int = 0
        self.enter_time: float | None = None
        self.last_swing_time: float | None = None
        self.session_quality: str = "none"
        self.session_momentum: int = 0

        self._cooldown_task: asyncio.Task | None = None
        self._cooldown_start_time: float = 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        if self._cooldown_task:
            self._cooldown_task.cancel()
        try:
            await self.message.edit(view=None)
        except Exception:
            pass

    async def refresh_data(self):
        self.skill_data = await self.bot.database.skills.get_data(
            self.user_id, self.server_id, "woodcutting"
        )
        self.user_data = await self.bot.database.users.get(self.user_id, self.server_id)

    @property
    def axe_tier(self) -> str:
        return self.skill_data[2] if self.skill_data else "flimsy"

    @property
    def gold(self) -> int:
        return self.user_data["gold"] if self.user_data else 0

    def _progress_bar(self) -> str:
        total = SkillMechanics.get_swings_needed(self.axe_tier)
        done = total - self.swings_remaining
        return "🟩" * done + "⬛" * self.swings_remaining

    def _rhythm_bar(self) -> str:
        if self.total_swings == 0:
            return ""
        pct = self.rhythm_hits / self.total_swings
        filled = round(pct * 10)
        bar = "█" * filled + "░" * (10 - filled)
        return f"Rhythm: `{bar}` {int(pct * 100)}%"

    def _quality_line(self) -> str:
        labels = {"good": "🌟 Good", "great": "⭐ Great", "masterful": "✨ Masterful"}
        label = labels.get(self.session_quality)
        if not label:
            return ""
        mom_txt = (
            f"  (+{self.session_momentum} min Momentum)"
            if self.session_momentum
            else ""
        )
        return f"\n**Session Quality:** {label}{mom_txt}"

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------

    def get_embed(self) -> discord.Embed:
        tier = self.axe_tier
        cost = SkillMechanics.get_entry_cost("forestry", tier)

        if self.state == "idle":
            desc = (
                f"**Axe:** {tier.title()} Axe\n"
                f"**Pass Cost:** {cost:,} GP\n"
                f"**Balance:** {self.gold:,} GP\n\n"
                "Purchase a forestry pass to enter the woods."
            )
            color = 0x5A8A3C
            title = "🪓 Forestry"

        elif self.state == "chopping":
            if self.knot_state == "knot":
                knot_line = (
                    "\n\n⚠️ **A gnarled knot is blocking your swing!** Clear it first."
                )
            elif self.knot_state == "tight_knot_pry":
                knot_line = (
                    "\n\n🪝 **Tough knot jammed in the wood!** Pry it loose first."
                )
            elif self.knot_state == "tight_knot_clear":
                knot_line = "\n\n⚠️ **Knot loosened — now clear it away!**"
            else:
                knot_line = ""
            rhythm = self._rhythm_bar()
            desc = (
                f"**Axe:** {tier.title()} Axe\n\n"
                f"{self._progress_bar()}\n"
                f"**{self.swings_remaining} swing(s) remaining**"
                + (f"\n{rhythm}" if rhythm else "")
                + knot_line
            )
            color = 0x5A8A3C
            title = "🪓 Forestry — Chopping"

        elif self.state == "cooldown":
            cooldown = SkillMechanics.get_forestry_cooldown(tier)
            lines = [
                f"**{name}:** +{amt:,}"
                for name, amt in self.last_yield.items()
                if amt > 0
            ]
            result_text = "\n".join(lines) or "Nothing gathered."
            mins, secs = divmod(cooldown, 60)
            desc = (
                f"🌲 **Timber!**\n\n{result_text}"
                + self._quality_line()
                + f"\n\n*Waiting for the area to clear... ({mins}m {secs:02d}s)*"
            )
            color = 0xA0522D
            title = "🪓 Forestry — Tree Felled!"

        else:  # ready
            desc = "The area has cleared.\n\nChop another tree or pack up."
            color = 0x5A8A3C
            title = "🪓 Forestry — Ready"

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_thumbnail(url=MASTERY_WOODCUTTING)
        return embed

    def setup_ui(self):
        self.clear_items()
        tier = self.axe_tier
        cost = SkillMechanics.get_entry_cost("forestry", tier)
        back_label = "← Gathering" if self.parent_gather_view else "Pack Up"

        if self.state == "idle":
            can_afford = self.gold >= cost
            enter_btn = Button(
                label=f"Enter Forest  ({cost:,} GP)",
                style=ButtonStyle.success if can_afford else ButtonStyle.secondary,
                emoji="🌲",
                disabled=not can_afford,
                row=0,
            )
            enter_btn.callback = self.enter_callback
            self.add_item(enter_btn)

        elif self.state == "chopping":
            if self.knot_state == "knot":
                knot_btn = Button(
                    label="Clear Knot", style=ButtonStyle.danger, emoji="⚠️", row=0
                )
                knot_btn.callback = self.knot_callback
                self.add_item(knot_btn)
            elif self.knot_state == "tight_knot_pry":
                pry_btn = Button(
                    label="Pry Loose", style=ButtonStyle.danger, emoji="🪝", row=0
                )
                pry_btn.callback = self.pry_callback
                self.add_item(pry_btn)
            elif self.knot_state == "tight_knot_clear":
                clear_btn = Button(
                    label="Clear Away", style=ButtonStyle.secondary, emoji="⚠️", row=0
                )
                clear_btn.callback = self.knot_callback
                self.add_item(clear_btn)
            else:
                swing_btn = Button(
                    label="Swing!", style=ButtonStyle.primary, emoji="🪓", row=0
                )
                swing_btn.callback = self.swing_callback
                self.add_item(swing_btn)

        elif self.state == "cooldown":
            waiting_btn = Button(
                label="Waiting...",
                style=ButtonStyle.secondary,
                emoji="⏳",
                disabled=True,
                row=0,
            )
            self.add_item(waiting_btn)
            # Block leaving during cooldown to prevent timer bypass exploit
            cooldown_total = SkillMechanics.get_forestry_cooldown(tier)
            elapsed = max(0.0, time.time() - self._cooldown_start_time)
            remaining = max(0, int(cooldown_total - elapsed))
            mins, secs = divmod(remaining, 60)
            leave_btn = Button(
                label=f"⏳ Area Clearing ({mins}m {secs:02d}s)",
                style=ButtonStyle.secondary,
                disabled=True,
                row=0,
            )
            self.add_item(leave_btn)
            return  # skip the normal pack_btn below

        elif self.state == "ready":
            can_afford = self.gold >= cost
            again_btn = Button(
                label=f"Chop Again  ({cost:,} GP)",
                style=ButtonStyle.success if can_afford else ButtonStyle.secondary,
                emoji="🌲",
                disabled=not can_afford,
                row=0,
            )
            again_btn.callback = self.enter_callback
            self.add_item(again_btn)

        pack_btn = Button(
            label=back_label,
            style=ButtonStyle.danger,
            emoji="🎒" if not self.parent_gather_view else None,
            row=0,
        )
        pack_btn.callback = self.pack_up_callback
        self.add_item(pack_btn)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def enter_callback(self, interaction: Interaction):
        await interaction.response.defer()
        await self.refresh_data()

        cost = SkillMechanics.get_entry_cost("forestry", self.axe_tier)
        if self.gold < cost:
            await interaction.followup.send(
                "You don't have enough gold for a forestry pass!", ephemeral=True
            )
            return

        await self.bot.database.skills.charge_entry_cost(self.user_id, cost)
        await self.refresh_data()

        self.swings_remaining = SkillMechanics.get_swings_needed(self.axe_tier)
        self.knot_state = None
        self.rhythm_hits = 0
        self.total_swings = 0
        self.enter_time = time.time()
        self.last_swing_time = None
        self.state = "chopping"
        self.setup_ui()
        await interaction.edit_original_response(embed=self.get_embed(), view=self)

    async def swing_callback(self, interaction: Interaction):
        await interaction.response.defer()

        # Rhythm check: timely if within FORESTRY_RHYTHM_WINDOW seconds of last action
        now = time.time()
        ref = (
            self.last_swing_time
            if self.last_swing_time is not None
            else self.enter_time
        )
        if ref is not None and (now - ref) <= SkillMechanics.FORESTRY_RHYTHM_WINDOW:
            self.rhythm_hits += 1
        self.total_swings += 1
        self.last_swing_time = now

        self.swings_remaining -= 1

        if self.swings_remaining <= 0:
            # Tree felled — compute quality and apply yield bonus
            self.session_quality = SkillMechanics.calculate_forestry_quality(
                self.rhythm_hits, self.total_swings
            )

            yield_dict = SkillMechanics.calculate_yield("woodcutting", self.axe_tier)
            yield_dict = SkillMechanics.apply_quality_to_yield(
                yield_dict, self.session_quality
            )

            await self.bot.database.skills.update_batch(
                self.user_id, self.server_id, "woodcutting", yield_dict
            )

            # Bank momentum
            self.session_momentum = SkillMechanics.get_momentum_minutes(
                self.session_quality
            )
            if self.session_momentum > 0:
                try:
                    max_mom = SkillMechanics.MAX_MOMENTUM_MINUTES.get(
                        "woodcutting", 300
                    )
                    await self.bot.database.skills.add_session_momentum(
                        self.user_id,
                        self.server_id,
                        "woodcutting",
                        self.session_momentum,
                        max_mom,
                    )
                except Exception:
                    pass

            # Masterful sessions grant a small amount of settlement Zeal (non-critical)
            if self.session_quality == "masterful":
                try:
                    await self.bot.database.settlement.add_zeal(self.user_id, self.server_id, 5)
                except Exception:
                    pass

            # Old Growth: on Masterful sessions, award 1 extra unit of the highest tier log
            if self.session_quality == "masterful":
                bonus_col = {
                    "flimsy": "oak_logs",
                    "carved": "willow_logs",
                    "chopping": "mahogany_logs",
                    "magic": "magic_logs",
                    "felling": "idea_logs",
                }.get(self.axe_tier)
                if bonus_col:
                    bonus = {bonus_col: 1}
                    await self.bot.database.skills.update_batch(
                        self.user_id, self.server_id, "woodcutting", bonus
                    )
                    yield_dict[bonus_col] = yield_dict.get(bonus_col, 0) + 1

            info = SkillMechanics.get_skill_info("woodcutting")
            name_map = {col: label for col, label in info["resources"]}
            self.last_yield = {
                name_map.get(col, col): amt for col, amt in yield_dict.items()
            }
            if self.session_quality == "masterful":
                self.last_yield["🌳 Old Growth"] = 1  # flavor label in result embed

            self._cooldown_start_time = time.time()
            self.state = "cooldown"
            self.setup_ui()
            await self.refresh_data()
            await interaction.edit_original_response(embed=self.get_embed(), view=self)

            cooldown = SkillMechanics.get_forestry_cooldown(self.axe_tier)
            self._cooldown_task = asyncio.create_task(self._run_cooldown(cooldown))
            return

        # Random knot check before the next swing.
        if random.random() < KNOT_CHANCE:
            if random.random() < TIGHT_KNOT_FRACTION:
                self.knot_state = "tight_knot_pry"  # 2-click: Pry then Clear
            else:
                self.knot_state = "knot"  # 1-click: Clear
        else:
            self.knot_state = None
        self.setup_ui()
        await interaction.edit_original_response(embed=self.get_embed(), view=self)

    async def pry_callback(self, interaction: Interaction):
        """First action on a tight knot — loosen it, then player must Clear."""
        await interaction.response.defer()
        self.knot_state = "tight_knot_clear"
        self.setup_ui()
        await interaction.edit_original_response(embed=self.get_embed(), view=self)

    async def knot_callback(self, interaction: Interaction):
        """Clear a standard knot or the final stage of a tight knot."""
        await interaction.response.defer()
        self.knot_state = None
        self.setup_ui()
        await interaction.edit_original_response(embed=self.get_embed(), view=self)

    async def _run_cooldown(self, seconds: int):
        try:
            await asyncio.sleep(seconds)
            self.state = "ready"
            self.setup_ui()
            await self.refresh_data()
            await self.message.edit(embed=self.get_embed(), view=self)
        except asyncio.CancelledError:
            pass

    async def pack_up_callback(self, interaction: Interaction):
        if self._cooldown_task:
            self._cooldown_task.cancel()

        if self.parent_gather_view:
            summary = ""
            if self.session_quality != "none":
                labels = {
                    "good": "🌟 Good",
                    "great": "⭐ Great",
                    "masterful": "✨ Masterful",
                }
                summary = f"**Last Chopping Session:** {labels[self.session_quality]}"
                if self.session_momentum:
                    summary += f" — +{self.session_momentum} min Momentum banked."
            self.stop()
            await self.parent_gather_view.refresh_and_resume(interaction, summary)
        else:
            self.bot.state_manager.clear_active(self.user_id)
            self.stop()
            await interaction.response.edit_message(
                embed=discord.Embed(title="🪓 You packed up your axe.", color=0x888888),
                view=None,
            )
