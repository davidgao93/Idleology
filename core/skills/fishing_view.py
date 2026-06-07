import asyncio

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.base_view import BaseView
from core.skills.mechanics import SkillMechanics

# Seconds the player has to click Reel before the fish escapes.
BITE_WINDOW = 60


class FishingView(BaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        user_mention: str,
        *,
        parent_gather_view=None,
    ):
        super().__init__(bot, user_id, server_id)
        self.user_mention = user_mention
        self.parent_gather_view = parent_gather_view

        self.state = "idle"  # idle | casting | bite | escaped | result
        self.skill_data = None
        self.user_data = None

        # Yield from last successful reel, mapped to display names.
        self.last_yield: dict[str, int] = {}

        # Session depth: approach choice + Focus streak
        self.approach: str = "steady"   # "steady" | "aggressive"
        self.focus_streak: int = 0
        self.session_quality: str = "none"
        self.session_momentum: int = 0

        self._bite_task: asyncio.Task | None = None
        self._escape_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        self._cancel_tasks()
        try:
            await self.message.edit(view=None)
        except Exception:
            pass

    def _cancel_tasks(self):
        if self._bite_task:
            self._bite_task.cancel()
        if self._escape_task:
            self._escape_task.cancel()

    async def refresh_data(self):
        self.skill_data = await self.bot.database.skills.get_data(
            self.user_id, self.server_id, "fishing"
        )
        self.user_data = await self.bot.database.users.get(self.user_id, self.server_id)

    @property
    def rod_tier(self) -> str:
        return self.skill_data[2] if self.skill_data else "desiccated"

    @property
    def gold(self) -> int:
        return self.user_data[6] if self.user_data else 0

    def _focus_bar(self) -> str:
        if self.focus_streak == 0:
            return ""
        icons = min(self.focus_streak, 7) * "🔥"
        return f"Focus: {icons} ×{self.focus_streak}"

    def _quality_line(self) -> str:
        labels = {"good": "🌟 Good", "great": "⭐ Great", "masterful": "✨ Masterful"}
        label = labels.get(self.session_quality)
        if not label:
            return ""
        mom_txt = f"  (+{self.session_momentum} min Momentum)" if self.session_momentum else ""
        return f"\n**Session Quality:** {label}{mom_txt}"

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------

    def get_embed(self) -> discord.Embed:
        tier = self.rod_tier
        cost = SkillMechanics.get_entry_cost("fishing", tier)

        if self.state == "idle":
            desc = (
                f"**Rod:** {tier.title()} Rod\n"
                f"**Bait Cost:** {cost:,} GP\n"
                f"**Balance:** {self.gold:,} GP\n\n"
                "Choose your approach and cast your line."
            )
            color = 0x4A90D9

        elif self.state == "casting":
            focus = self._focus_bar()
            approach_label = "⚡ Aggressive" if self.approach == "aggressive" else "🎣 Steady"
            desc = (
                f"**Rod:** {tier.title()} Rod  ·  {approach_label}\n"
                + (f"{focus}\n\n" if focus else "\n")
                + "🌊 Your line is in the water...\n"
                "You'll be pinged when something bites."
            )
            color = 0x4A90D9

        elif self.state == "bite":
            focus = self._focus_bar()
            desc = (
                "🐟 **A fish is on the line!**\n\n"
                f"Reel it in before it escapes!\n"
                f"*You have {BITE_WINDOW} seconds.*"
                + (f"\n\n{focus}" if focus else "")
            )
            color = 0xFF8C00

        elif self.state == "escaped":
            penalty = " (streak reduced)" if self.approach == "aggressive" and self.focus_streak > 0 else ""
            desc = (
                f"💨 The fish slipped the hook...{penalty}\n\n"
                "Cast again to try your luck."
            )
            if self._focus_bar():
                desc += f"\n{self._focus_bar()}"
            color = 0x888888

        else:  # result
            lines = [
                f"**{name}:** +{amt:,}"
                for name, amt in self.last_yield.items()
                if amt > 0
            ]
            focus = self._focus_bar()
            desc = "🐟 **You reeled it in!**\n\n" + (
                "\n".join(lines) or "Nothing caught."
            )
            if focus:
                desc += f"\n\n{focus}"
            desc += self._quality_line()
            color = 0x00CC44

        title_map = {
            "idle": "🎣 Fishing",
            "casting": "🎣 Fishing",
            "bite": "🎣 Fishing — Something's Biting!",
            "escaped": "🎣 Fishing — Got Away!",
            "result": "🎣 Fishing — Catch!",
        }
        embed = discord.Embed(
            title=title_map[self.state], description=desc, color=color
        )
        if self.user_data:
            embed.set_thumbnail(url=self.user_data[7])
        return embed

    def setup_ui(self):
        self.clear_items()
        tier = self.rod_tier
        cost = SkillMechanics.get_entry_cost("fishing", tier)
        back_label = "← Gathering" if self.parent_gather_view else "Pack Up"

        if self.state == "idle":
            can_afford = self.gold >= cost
            steady_btn = Button(
                label=f"🎣 Steady Cast  ({cost:,} GP)",
                style=ButtonStyle.primary if can_afford else ButtonStyle.secondary,
                disabled=not can_afford,
                row=0,
            )
            steady_btn.callback = self._make_cast_callback("steady")
            self.add_item(steady_btn)

            agg_btn = Button(
                label=f"⚡ Aggressive Cast  ({cost:,} GP)",
                style=ButtonStyle.success if can_afford else ButtonStyle.secondary,
                disabled=not can_afford,
                row=0,
            )
            agg_btn.callback = self._make_cast_callback("aggressive")
            self.add_item(agg_btn)

        elif self.state == "casting":
            waiting_btn = Button(
                label="Waiting for bite...",
                style=ButtonStyle.secondary,
                emoji="🌊",
                disabled=True,
                row=0,
            )
            self.add_item(waiting_btn)

        elif self.state == "bite":
            reel_btn = Button(
                label="Reel In!", style=ButtonStyle.success, emoji="🐟", row=0
            )
            reel_btn.callback = self.reel_callback
            self.add_item(reel_btn)

        elif self.state in ("result", "escaped"):
            can_afford = self.gold >= cost
            steady_btn = Button(
                label=f"🎣 Steady  ({cost:,} GP)",
                style=ButtonStyle.primary if can_afford else ButtonStyle.secondary,
                disabled=not can_afford,
                row=0,
            )
            steady_btn.callback = self._make_cast_callback("steady")
            self.add_item(steady_btn)

            agg_btn = Button(
                label=f"⚡ Aggressive  ({cost:,} GP)",
                style=ButtonStyle.success if can_afford else ButtonStyle.secondary,
                disabled=not can_afford,
                row=0,
            )
            agg_btn.callback = self._make_cast_callback("aggressive")
            self.add_item(agg_btn)

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

    def _make_cast_callback(self, approach: str):
        async def callback(interaction: Interaction):
            await self._cast(interaction, approach)
        return callback

    async def _cast(self, interaction: Interaction, approach: str):
        await interaction.response.defer()
        await self.refresh_data()

        cost = SkillMechanics.get_entry_cost("fishing", self.rod_tier)
        if self.gold < cost:
            await interaction.followup.send(
                "You don't have enough gold to buy bait!", ephemeral=True
            )
            return

        await self.bot.database.skills.charge_entry_cost(self.user_id, cost)
        await self.refresh_data()

        self.approach = approach
        self.state = "casting"
        self.setup_ui()
        await interaction.edit_original_response(
            content=None, embed=self.get_embed(), view=self
        )

        wait = SkillMechanics.get_fishing_wait(self.rod_tier)
        self._bite_task = asyncio.create_task(self._wait_for_bite(wait))

    async def _wait_for_bite(self, seconds: int):
        try:
            await asyncio.sleep(seconds)
            self.state = "bite"
            self.setup_ui()
            await self.message.edit(
                content=self.user_mention,
                embed=self.get_embed(),
                view=self,
            )
            self._escape_task = asyncio.create_task(self._fish_escape())
        except asyncio.CancelledError:
            pass

    async def _fish_escape(self):
        try:
            await asyncio.sleep(BITE_WINDOW)
            if self.state == "bite":
                # Streak penalty: aggressive cuts streak in half, steady resets
                if self.approach == "aggressive":
                    self.focus_streak = max(0, self.focus_streak // 2)
                else:
                    self.focus_streak = 0
                self.state = "escaped"
                self.setup_ui()
                await self.refresh_data()
                await self.message.edit(content=None, embed=self.get_embed(), view=self)
        except asyncio.CancelledError:
            pass

    async def reel_callback(self, interaction: Interaction):
        await interaction.response.defer()
        if self._escape_task:
            self._escape_task.cancel()

        # Increment focus streak
        self.focus_streak += 1

        # Compute quality and yield bonus
        self.session_quality = SkillMechanics.calculate_fishing_quality(
            self.focus_streak, self.approach
        )

        # Base yield, then apply quality and aggressive bonuses
        yield_dict = SkillMechanics.calculate_yield("fishing", self.rod_tier)
        if self.approach == "aggressive":
            # +15% bonus for aggressive approach on top of quality
            yield_dict = {k: max(1, int(v * 1.15)) for k, v in yield_dict.items()}
        yield_dict = SkillMechanics.apply_quality_to_yield(yield_dict, self.session_quality)

        await self.bot.database.skills.update_batch(
            self.user_id, self.server_id, "fishing", yield_dict
        )

        # Bank momentum if quality earned any
        self.session_momentum = SkillMechanics.get_momentum_minutes(self.session_quality)
        if self.session_momentum > 0:
            try:
                max_mom = SkillMechanics.MAX_MOMENTUM_MINUTES.get("fishing", 300)
                await self.bot.database.skills.add_session_momentum(
                    self.user_id, self.server_id, "fishing",
                    self.session_momentum, max_mom,
                )
            except Exception:
                pass

        # Masterful sessions grant a small amount of settlement Zeal (non-critical)
        if self.session_quality == "masterful":
            try:
                await self.bot.database.settlement.add_zeal(self.user_id, 5)
            except Exception:
                pass

        # Pristine Catch: on Masterful sessions, award 1 extra unit of the highest tier bone
        if self.session_quality == "masterful":
            bonus_col = {
                "desiccated": "desiccated_bones",
                "regular": "regular_bones",
                "sturdy": "sturdy_bones",
                "reinforced": "reinforced_bones",
                "titanium": "titanium_bones",
            }.get(self.rod_tier)
            if bonus_col:
                bonus = {bonus_col: 1}
                await self.bot.database.skills.update_batch(
                    self.user_id, self.server_id, "fishing", bonus
                )
                yield_dict[bonus_col] = yield_dict.get(bonus_col, 0) + 1

        info = SkillMechanics.get_skill_info("fishing")
        name_map = {col: label for col, label in info["resources"]}
        self.last_yield = {
            name_map.get(col, col): amt for col, amt in yield_dict.items()
        }
        if self.session_quality == "masterful":
            self.last_yield["✨ Pristine Catch"] = 1  # flavor label in result embed

        self.state = "result"
        self.setup_ui()
        await self.refresh_data()
        await interaction.edit_original_response(
            content=None, embed=self.get_embed(), view=self
        )

    async def pack_up_callback(self, interaction: Interaction):
        self._cancel_tasks()

        if self.parent_gather_view:
            summary = ""
            if self.session_quality != "none":
                labels = {"good": "🌟 Good", "great": "⭐ Great", "masterful": "✨ Masterful"}
                summary = f"**Last Fishing Session:** {labels[self.session_quality]}"
                if self.session_momentum:
                    summary += f" — +{self.session_momentum} min Momentum banked."
            self.stop()
            await self.parent_gather_view.refresh_and_resume(interaction, summary)
        else:
            self.bot.state_manager.clear_active(self.user_id)
            self.stop()
            await interaction.response.edit_message(
                content=None,
                embed=discord.Embed(title="🎣 You packed up your rod.", color=0x888888),
                view=None,
            )
