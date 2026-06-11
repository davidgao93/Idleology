# core/settlement/views/town_hall.py
import discord
from datetime import datetime, timedelta
from discord import ButtonStyle, Interaction, ui

from core.images import SETTLEMENT_BUILDINGS
from core.settlement.mechanics import SettlementMechanics
from core.settlement.plots import get_meta_slots

from .base import SettlementBaseView

# Cost per Development Contract
_DC_GOLD = 5_000
_DC_TIMBER = 500
_DC_STONE = 500


_DC_DAILY_CAP = 10


class DCCraftModal(ui.Modal, title="Craft Development Contracts"):
    """Modal that lets the player specify how many DCs to craft (up to daily cap)."""

    quantity = ui.TextInput(
        label="Quantity (1–10)",
        placeholder="Enter a number between 1 and 10",
        min_length=1,
        max_length=2,
    )

    def __init__(self, parent_view: "TownHallView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        try:
            qty = int(self.quantity.value)
            if not (1 <= qty <= 10):
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "Please enter a whole number between **1** and **10**.",
                ephemeral=True,
            )

        pv = self.parent_view

        # --- Daily cap check ---
        crafted_today = await pv.bot.database.users.get_dc_crafted_today(pv.user_id)
        remaining_today = _DC_DAILY_CAP - crafted_today
        if remaining_today <= 0:
            return await interaction.response.send_message(
                f"You've reached the **{_DC_DAILY_CAP} DC** daily craft limit. Come back tomorrow!",
                ephemeral=True,
            )
        if qty > remaining_today:
            return await interaction.response.send_message(
                f"You can only craft **{remaining_today}** more DC(s) today "
                f"(daily limit: {_DC_DAILY_CAP}).",
                ephemeral=True,
            )

        cost_gold = qty * _DC_GOLD
        cost_timber = qty * _DC_TIMBER
        cost_stone = qty * _DC_STONE

        gold = await pv.bot.database.users.get_gold(pv.user_id)
        stl = pv.settlement
        if gold < cost_gold or stl.timber < cost_timber or stl.stone < cost_stone:
            return await interaction.response.send_message(
                f"Insufficient resources!\n"
                f"Need: 💰 {cost_gold:,}g | 🪵 {cost_timber:,} | 🪨 {cost_stone:,}\n"
                f"Have: 💰 {gold:,}g | 🪵 {stl.timber:,} | 🪨 {stl.stone:,}",
                ephemeral=True,
            )

        # Deduct resources
        changes = {"timber": -cost_timber, "stone": -cost_stone}
        await pv.bot.database.settlement.commit_production(
            pv.user_id, pv.parent.server_id, changes
        )
        await pv.bot.database.users.modify_gold(pv.user_id, -cost_gold)
        await pv.bot.database.users.modify_development_contracts(pv.user_id, qty)
        await pv.bot.database.users.add_dc_crafted_today(pv.user_id, qty)

        # Update local state
        pv.settlement.timber -= cost_timber
        pv.settlement.stone -= cost_stone
        pv.dc_count += qty
        pv.dc_crafted_today += qty

        embed = pv.build_embed()
        embed.title = (
            f"✅ Town Hall — Crafted {qty}× "
            f"Development Contract{'s' if qty != 1 else ''}!"
        )
        embed.colour = discord.Color.green()
        await interaction.response.edit_message(content=None, embed=embed, view=pv)


class TownHallView(SettlementBaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        settlement,
        parent_view,
        dc_count: int = 0,
        dc_crafted_today: int = 0,
    ):
        super().__init__(bot, user_id)
        self.settlement = settlement
        self.parent = parent_view
        self.dc_count = dc_count
        self.dc_crafted_today = dc_crafted_today
        self._processing = False
        self.setup_ui()

    def build_embed(self):
        tier = self.settlement.town_hall_tier
        meta_cap = get_meta_slots(tier)
        meta_used = sum(1 for b in self.settlement.buildings if b.is_meta)

        desc = (
            f"**Level:** {tier}/7\n"
            f"**Meta Building Slots:** {meta_used}/{meta_cap}\n"
            f"**Follower Cap Buff:** +{tier * 10}%\n"
            f"📜 **Development Contracts:** {self.dc_count}"
        )

        embed = discord.Embed(
            title="🏛️ Town Hall",
            description=desc,
            color=discord.Color.dark_blue(),
        )

        # DC crafting info — compute time until next midnight reset
        remaining_today = max(0, _DC_DAILY_CAP - self.dc_crafted_today)
        now = datetime.now()
        next_midnight = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        secs_left = int((next_midnight - now).total_seconds())
        h, _r = divmod(secs_left, 3600)
        m, s = divmod(_r, 60)
        reset_str = f"{h}h:{m:02d}m:{s:02d}s"
        embed.add_field(
            name="📜 Craft Development Contracts",
            value=(
                f"Cost per DC: 💰 {_DC_GOLD:,}g | "
                f"🪵 {_DC_TIMBER:,} Timber | "
                f"🪨 {_DC_STONE:,} Stone\n"
                f"Daily crafts remaining: **{remaining_today}/{_DC_DAILY_CAP}** "
                f"*(resets in {reset_str})*\n"
                "Use DCs to develop new settlement plots."
            ),
            inline=False,
        )

        if tier < 7:
            costs = self._get_upgrade_cost(tier + 1)
            cost_str = (
                f"🪵 {costs['timber']:,} | 🪨 {costs['stone']:,} | 💰 {costs['gold']:,}"
            )
            if "specials" in costs:
                reqs = [f"{s['name']} ×{s['qty']}" for s in costs["specials"]]
                cost_str += f"\n✨ **Requires:** {', '.join(reqs)}"

            embed.add_field(
                name="Upgrade Benefits",
                value=(
                    f"Meta Slots: {meta_cap} ➡️ **{meta_cap + 1}**\n"
                    f"Follower Cap: +{tier * 10}% ➡️ **+{(tier + 1) * 10}%**"
                ),
                inline=False,
            )
            embed.add_field(name="Upgrade Cost", value=cost_str, inline=False)
        else:
            embed.add_field(
                name="Status", value="🌟 Maximum Tier Reached", inline=False
            )

        embed.set_thumbnail(url=SETTLEMENT_BUILDINGS["town_hall"])
        return embed

    def _get_upgrade_cost(self, target_tier: int) -> dict:
        return SettlementMechanics.get_upgrade_cost("town_hall", target_tier - 1)

    def setup_ui(self):
        self.clear_items()

        btn_craft = ui.Button(
            label="Craft Development Contracts",
            style=ButtonStyle.blurple,
            emoji="📜",
            row=0,
        )
        btn_craft.callback = self.craft_dcs
        self.add_item(btn_craft)

        btn_up = ui.Button(
            label="Upgrade Hall",
            style=ButtonStyle.success,
            emoji="⬆️",
            disabled=(self.settlement.town_hall_tier >= 7),
            row=0,
        )
        btn_up.callback = self.upgrade
        self.add_item(btn_up)

        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def craft_dcs(self, interaction: Interaction):
        modal = DCCraftModal(self)
        await interaction.response.send_modal(modal)

    async def upgrade(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        target_tier = self.settlement.town_hall_tier + 1
        costs = self._get_upgrade_cost(target_tier)

        if (
            self.settlement.timber < costs["timber"]
            or self.settlement.stone < costs["stone"]
        ):
            self._processing = False
            return await interaction.response.send_message(
                "Insufficient Timber or Stone!", ephemeral=True
            )

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < costs["gold"]:
            self._processing = False
            return await interaction.response.send_message(
                "Insufficient Gold!", ephemeral=True
            )

        if "specials" in costs:
            for sp in costs["specials"]:
                owned = await self.bot.database.users.get_currency(
                    self.user_id, sp["key"]
                )
                if owned < sp["qty"]:
                    self._processing = False
                    return await interaction.response.send_message(
                        f"Need {sp['qty']}× {sp['name']}! (You have {owned})",
                        ephemeral=True,
                    )

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        if "specials" in costs:
            for sp in costs["specials"]:
                await self.bot.database.users.modify_currency(
                    self.user_id, sp["key"], -sp["qty"]
                )

        changes = {
            "timber": -costs["timber"],
            "stone": -costs["stone"],
        }
        await self.bot.database.settlement.commit_production(
            self.user_id, self.parent.server_id, changes
        )
        await self.bot.database.users.modify_gold(self.user_id, -costs["gold"])
        await self.bot.database.settlement.upgrade_town_hall(
            self.user_id, self.parent.server_id
        )

        self.settlement.town_hall_tier += 1
        self.settlement.timber -= costs["timber"]
        self.settlement.stone -= costs["stone"]
        self._processing = False
        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def go_back(self, interaction: Interaction):
        self.parent._rebuild_ui()
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()
