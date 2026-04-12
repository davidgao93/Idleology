import asyncio
import discord
from discord import Interaction, ButtonStyle
from discord.ui import View, Button
from core.skills.mechanics import SkillMechanics

# Seconds the player has to click Reel before the fish escapes.
BITE_WINDOW = 60


class FishingView(View):
    def __init__(self, bot, user_id: str, server_id: str, user_mention: str):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.user_mention = user_mention

        self.state = "idle"   # idle | casting | bite | escaped | result
        self.message: discord.Message | None = None
        self.skill_data = None
        self.user_data = None

        # Yield from last successful reel, mapped to display names.
        self.last_yield: dict[str, int] = {}

        self._bite_task: asyncio.Task | None = None
        self._escape_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

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
                "Cast your line to begin."
            )
            color = 0x4A90D9

        elif self.state == "casting":
            desc = (
                f"**Rod:** {tier.title()} Rod\n\n"
                "🌊 Your line is in the water...\n"
                "You'll be pinged when something bites."
            )
            color = 0x4A90D9

        elif self.state == "bite":
            desc = (
                "🐟 **A fish is on the line!**\n\n"
                f"Reel it in before it escapes!\n"
                f"*You have {BITE_WINDOW} seconds.*"
            )
            color = 0xFF8C00

        elif self.state == "escaped":
            desc = (
                "💨 The fish slipped the hook...\n\n"
                "Cast again to try your luck."
            )
            color = 0x888888

        else:  # result
            lines = [f"**{name}:** +{amt:,}" for name, amt in self.last_yield.items() if amt > 0]
            desc = "🐟 **You reeled it in!**\n\n" + ("\n".join(lines) or "Nothing caught.")
            color = 0x00CC44

        title_map = {
            "idle":     "🎣 Fishing",
            "casting":  "🎣 Fishing",
            "bite":     "🎣 Fishing — Something's Biting!",
            "escaped":  "🎣 Fishing — Got Away!",
            "result":   "🎣 Fishing — Catch!",
        }
        embed = discord.Embed(title=title_map[self.state], description=desc, color=color)
        if self.user_data:
            embed.set_thumbnail(url=self.user_data[7])
        return embed

    def setup_ui(self):
        self.clear_items()
        tier = self.rod_tier
        cost = SkillMechanics.get_entry_cost("fishing", tier)

        if self.state == "idle":
            can_afford = self.gold >= cost
            cast_btn = Button(
                label=f"Cast Line  ({cost:,} GP)",
                style=ButtonStyle.primary if can_afford else ButtonStyle.secondary,
                emoji="🎣",
                disabled=not can_afford,
                row=0,
            )
            cast_btn.callback = self.cast_callback
            self.add_item(cast_btn)

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
            reel_btn = Button(label="Reel In!", style=ButtonStyle.success, emoji="🐟", row=0)
            reel_btn.callback = self.reel_callback
            self.add_item(reel_btn)

        elif self.state in ("result", "escaped"):
            can_afford = self.gold >= cost
            recast_btn = Button(
                label=f"Recast  ({cost:,} GP)",
                style=ButtonStyle.primary if can_afford else ButtonStyle.secondary,
                emoji="🎣",
                disabled=not can_afford,
                row=0,
            )
            recast_btn.callback = self.cast_callback
            self.add_item(recast_btn)

        pack_btn = Button(label="Pack Up", style=ButtonStyle.danger, emoji="🎒", row=0)
        pack_btn.callback = self.pack_up_callback
        self.add_item(pack_btn)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def cast_callback(self, interaction: Interaction):
        await interaction.response.defer()
        await self.refresh_data()

        cost = SkillMechanics.get_entry_cost("fishing", self.rod_tier)
        if self.gold < cost:
            await interaction.followup.send("You don't have enough gold to buy bait!", ephemeral=True)
            return

        await self.bot.database.skills.charge_entry_cost(self.user_id, cost)
        await self.refresh_data()

        self.state = "casting"
        self.setup_ui()
        await interaction.edit_original_response(content=None, embed=self.get_embed(), view=self)

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

        yield_dict = SkillMechanics.calculate_yield("fishing", self.rod_tier)
        await self.bot.database.skills.update_batch(
            self.user_id, self.server_id, "fishing", yield_dict
        )

        info = SkillMechanics.get_skill_info("fishing")
        name_map = {col: label for col, label in info["resources"]}
        self.last_yield = {name_map.get(col, col): amt for col, amt in yield_dict.items()}

        self.state = "result"
        self.setup_ui()
        await self.refresh_data()
        await interaction.edit_original_response(content=None, embed=self.get_embed(), view=self)

    async def pack_up_callback(self, interaction: Interaction):
        self._cancel_tasks()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.edit_message(
            content=None,
            embed=discord.Embed(title="🎣 You packed up your rod.", color=0x888888),
            view=None,
        )
