import asyncio
import random
import discord
from discord import Interaction, ButtonStyle
from discord.ui import View, Button
from core.skills.mechanics import SkillMechanics

# Probability that a gnarled knot blocks the next swing.
KNOT_CHANCE = 0.25


class ForestryView(View):
    def __init__(self, bot, user_id: str, server_id: str):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id

        self.state = "idle"   # idle | chopping | cooldown | ready
        self.message: discord.Message | None = None
        self.skill_data = None
        self.user_data = None

        self.swings_remaining = 0
        self.knot_blocking = False

        # Yield from last felled tree, mapped to display names.
        self.last_yield: dict[str, int] = {}

        self._cooldown_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

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
        return self.user_data[6] if self.user_data else 0

    def _progress_bar(self) -> str:
        total = SkillMechanics.get_swings_needed(self.axe_tier)
        done = total - self.swings_remaining
        return "🟩" * done + "⬛" * self.swings_remaining

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
            knot_line = (
                "\n\n⚠️ **A gnarled knot is blocking your swing!** Clear it first."
                if self.knot_blocking else ""
            )
            desc = (
                f"**Axe:** {tier.title()} Axe\n\n"
                f"{self._progress_bar()}\n"
                f"**{self.swings_remaining} swing(s) remaining**"
                f"{knot_line}"
            )
            color = 0x5A8A3C
            title = "🪓 Forestry — Chopping"

        elif self.state == "cooldown":
            cooldown = SkillMechanics.get_forestry_cooldown(tier)
            lines = [f"**{name}:** +{amt:,}" for name, amt in self.last_yield.items() if amt > 0]
            result_text = "\n".join(lines) or "Nothing gathered."
            mins, secs = divmod(cooldown, 60)
            desc = (
                f"🌲 **Timber!**\n\n{result_text}\n\n"
                f"*Waiting for the area to clear... ({mins}m {secs:02d}s)*"
            )
            color = 0xA0522D
            title = "🪓 Forestry — Tree Felled!"

        else:  # ready
            desc = "The area has cleared.\n\nChop another tree or pack up."
            color = 0x5A8A3C
            title = "🪓 Forestry — Ready"

        embed = discord.Embed(title=title, description=desc, color=color)
        if self.user_data:
            embed.set_thumbnail(url=self.user_data[7])
        return embed

    def setup_ui(self):
        self.clear_items()
        tier = self.axe_tier
        cost = SkillMechanics.get_entry_cost("forestry", tier)

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
            if self.knot_blocking:
                knot_btn = Button(
                    label="Clear Knot", style=ButtonStyle.danger, emoji="⚠️", row=0
                )
                knot_btn.callback = self.knot_callback
                self.add_item(knot_btn)
            else:
                swing_btn = Button(
                    label="Swing!", style=ButtonStyle.primary, emoji="🪓", row=0
                )
                swing_btn.callback = self.swing_callback
                self.add_item(swing_btn)

        elif self.state == "cooldown":
            waiting_btn = Button(
                label="Waiting...", style=ButtonStyle.secondary, emoji="⏳", disabled=True, row=0
            )
            self.add_item(waiting_btn)

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

        pack_btn = Button(label="Pack Up", style=ButtonStyle.danger, emoji="🎒", row=0)
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
        self.knot_blocking = False
        self.state = "chopping"
        self.setup_ui()
        await interaction.edit_original_response(embed=self.get_embed(), view=self)

    async def swing_callback(self, interaction: Interaction):
        await interaction.response.defer()
        self.swings_remaining -= 1

        if self.swings_remaining <= 0:
            # Tree felled — calculate yield and start cooldown.
            yield_dict = SkillMechanics.calculate_yield("woodcutting", self.axe_tier)
            await self.bot.database.skills.update_batch(
                self.user_id, self.server_id, "woodcutting", yield_dict
            )
            info = SkillMechanics.get_skill_info("woodcutting")
            name_map = {col: label for col, label in info["resources"]}
            self.last_yield = {name_map.get(col, col): amt for col, amt in yield_dict.items()}

            self.state = "cooldown"
            self.setup_ui()
            await self.refresh_data()
            await interaction.edit_original_response(embed=self.get_embed(), view=self)

            cooldown = SkillMechanics.get_forestry_cooldown(self.axe_tier)
            self._cooldown_task = asyncio.create_task(self._run_cooldown(cooldown))
            return

        # Random knot check before the next swing.
        self.knot_blocking = random.random() < KNOT_CHANCE
        self.setup_ui()
        await interaction.edit_original_response(embed=self.get_embed(), view=self)

    async def knot_callback(self, interaction: Interaction):
        await interaction.response.defer()
        self.knot_blocking = False
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
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(title="🪓 You packed up your axe.", color=0x888888),
            view=None,
        )
