"""
core/nether_market/views/hub_view.py — Nether Market Buy/Sell hub (the "Market" tab).
Browse and Mastery are separate sibling views navigated to via buttons (same
child-view-swap discipline as core/alchemy/views.py:AlchemyHubView).
"""

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.images import VEX_PORTRAIT, VEX_THUMBNAIL
from core.nether_market.data import WEALTH_TIERS
from core.nether_market.mechanics import NetherMarketMechanics as M
from core.npc_voices import get_quip

_TIER_LABELS = (("cheap", "Cheap"), ("med", "Medium"), ("expensive", "Expensive"))
_VARIANT_LABELS = (("lo", "Bargain"), ("hi", "Premium"))


async def build_hub_view(bot, user_id: str, server_id: str) -> "NetherMarketHubView":
    """Fetches all Nether Market state from the DB and returns a fresh hub view.
    Rolls an initial rotation on first-ever use for a server, and also re-rolls
    if an existing rotation predates the lo/hi expansion (NULL new columns)."""
    rotation = await bot.database.nether_market.get_rotation(server_id)
    if rotation is None or rotation.get("cheap_lo_item") is None:
        rolled = M.roll_rotation()
        await bot.database.nether_market.save_rotation(server_id, **rolled)
        rotation = await bot.database.nether_market.get_rotation(server_id)

    holdings = await bot.database.nether_market.get_holdings(user_id, server_id)
    profile = await bot.database.nether_market.get_or_create_profile(user_id, server_id)
    gold = await bot.database.users.get_gold(user_id)
    plunder_notice = await bot.database.nether_market.pop_plunder_notice(user_id, server_id)

    return NetherMarketHubView(
        bot, user_id, server_id, rotation, holdings, profile, gold, plunder_notice
    )


class NetherMarketHubView(BaseView):
    def __init__(self, bot, user_id, server_id, rotation, holdings, profile, gold, plunder_notice=None):
        super().__init__(bot, user_id, server_id)
        self.rotation = rotation
        self.holdings = holdings
        self.profile = profile
        self.gold = gold
        self.plunder_notice = plunder_notice
        self._processing = False
        self._build_buttons()

    @property
    def cap(self) -> int:
        return M.get_holdings_cap(self.profile["mastery_nodes"])

    @property
    def held_count(self) -> int:
        return sum(self.holdings.values())

    def build_embed(self) -> discord.Embed:
        value = M.compute_holdings_value(self.holdings, self.rotation)
        tier_name = WEALTH_TIERS[M.get_wealth_tier(value)]["name"]
        show_true_value = bool(self.profile["mastery_nodes"].get("trunk_market_sense"))

        embed = discord.Embed(title="\U0001f573️ Nether Market", color=discord.Color.dark_purple())
        embed.set_author(name="Vex, the Fence", icon_url=VEX_PORTRAIT)
        if VEX_THUMBNAIL:
            embed.set_thumbnail(url=VEX_THUMBNAIL)
        embed.set_footer(text=get_quip("nether_market"))

        lines = []
        for tier_key, label in _TIER_LABELS:
            for variant_key, variant_label in _VARIANT_LABELS:
                item_key = self.rotation[f"{tier_key}_{variant_key}_item"]
                price = self.rotation[f"{tier_key}_{variant_key}_price"]
                item = M.get_item(item_key)
                dev = M.deviation_pct(price, item["true_value"])
                sign = "+" if dev >= 0 else ""
                held = self.holdings.get(item_key, 0)
                line = f"**[{label} · {variant_label}]** {item['name']} — \U0001f4b0 {price:,} ({sign}{dev:.0f}%)"
                if show_true_value:
                    line += f"  *(true: {item['true_value']:,})*"
                if held:
                    line += f"\nYou hold: **{held}**"
                lines.append(line)
        embed.description = "\n\n".join(lines)

        embed.add_field(name="Gold", value=f"\U0001f4b0 {self.gold:,}", inline=True)
        embed.add_field(
            name="Holdings", value=f"{self.held_count} / {self.cap} slots (worth ~{value:,})", inline=True
        )
        embed.add_field(name="Wealth Tier", value=f"**{tier_name}**", inline=True)
        embed.add_field(name="Nether Marks", value=f"\U0001f536 {self.profile['nether_marks']}", inline=True)

        if self.plunder_notice:
            notice = self.plunder_notice
            item_lines = []
            for item_key, qty in notice.get("items", {}).items():
                item = M.get_item(item_key)
                name = item["name"] if item else item_key
                item_lines.append(f"{qty}x {name}")
            haul_parts = []
            if item_lines:
                haul_parts.append(", ".join(item_lines))
            if notice.get("overflow_gold"):
                haul_parts.append(f"\U0001f4b0 {notice['overflow_gold']:,} gold (overflow)")
            haul = "; ".join(haul_parts) if haul_parts else "nothing of value"
            embed.insert_field_at(
                0,
                name="⚠️ You Were Plundered!",
                value=(
                    f"**{notice.get('attacker_name', 'Someone')}** cracked your vault "
                    f"<t:{int(notice['timestamp'])}:R> and made off with {haul}."
                ),
                inline=False,
            )
            self.plunder_notice = None  # only ever shown on the first render of this view
        return embed

    def _build_buttons(self):
        self.clear_items()
        for row, (tier_key, label) in enumerate(_TIER_LABELS):
            for variant_key, variant_label in _VARIANT_LABELS:
                item_key = self.rotation[f"{tier_key}_{variant_key}_item"]
                price = self.rotation[f"{tier_key}_{variant_key}_price"]

                buy_btn = ui.Button(
                    label=f"Buy {label} ({variant_label})", style=ButtonStyle.green, row=row
                )
                buy_btn.callback = self._make_buy_callback(item_key, price)
                self.add_item(buy_btn)

                held = self.holdings.get(item_key, 0)
                sell_btn = ui.Button(
                    label=f"Sell {label} ({variant_label})",
                    style=ButtonStyle.red,
                    row=row,
                    disabled=held <= 0,
                )
                sell_btn.callback = self._make_sell_callback(item_key, price)
                self.add_item(sell_btn)

        holdings_btn = ui.Button(label="Holdings", style=ButtonStyle.blurple, emoji="\U0001f4e6", row=3)
        holdings_btn.callback = self.open_holdings
        self.add_item(holdings_btn)

        browse_btn = ui.Button(label="Browse Targets", style=ButtonStyle.blurple, emoji="\U0001f3af", row=3)
        browse_btn.callback = self.open_browse
        self.add_item(browse_btn)

        mastery_btn = ui.Button(label="Tricks of the Trade", style=ButtonStyle.blurple, emoji="\U0001f3ad", row=3)
        mastery_btn.callback = self.open_mastery
        self.add_item(mastery_btn)

        close_btn = ui.Button(label="Close", style=ButtonStyle.secondary, emoji="✖️", row=3)
        close_btn.callback = self.handle_close
        self.add_item(close_btn)

    def _make_buy_callback(self, item_key: str, price: int):
        async def _callback(interaction: Interaction):
            if self._processing:
                return await interaction.response.defer()
            self._processing = True
            await interaction.response.send_modal(BuyModal(item_key, price, self))

        return _callback

    def _make_sell_callback(self, item_key: str, price: int):
        async def _callback(interaction: Interaction):
            if self._processing:
                return await interaction.response.defer()
            self._processing = True
            await interaction.response.send_modal(SellModal(item_key, price, self))

        return _callback

    async def open_holdings(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()
        from core.nether_market.views.holdings_view import build_holdings_view

        view = await build_holdings_view(self.bot, self.user_id, self.server_id)
        msg = await interaction.edit_original_response(embed=view.build_embed(), view=view)
        view.message = msg
        self.stop()

    async def open_browse(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()
        from core.nether_market.views.browse_view import build_browse_view

        view = await build_browse_view(self.bot, self.user_id, self.server_id)
        msg = await interaction.edit_original_response(embed=await view.build_embed(), view=view)
        view.message = msg
        self.stop()

    async def open_mastery(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()
        from core.nether_market.views.mastery_view import build_mastery_view

        view = await build_mastery_view(self.bot, self.user_id, self.server_id)
        msg = await interaction.edit_original_response(embed=view.build_embed(), view=view)
        view.message = msg
        self.stop()

    async def handle_close(self, interaction: Interaction):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.defer()
        await interaction.delete_original_response()

    async def refresh(self, interaction: Interaction):
        """Re-fetches state and re-renders in place (used after buy/sell)."""
        self.holdings = await self.bot.database.nether_market.get_holdings(self.user_id, self.server_id)
        self.profile = await self.bot.database.nether_market.get_or_create_profile(self.user_id, self.server_id)
        self.gold = await self.bot.database.users.get_gold(self.user_id)
        self._build_buttons()
        self._processing = False
        await interaction.edit_original_response(embed=self.build_embed(), view=self)


class BuyModal(ui.Modal, title="Buy Curiosity"):
    quantity_input = ui.TextInput(
        label="Quantity", placeholder="e.g. 5", min_length=1, max_length=4, required=True
    )

    def __init__(self, item_key: str, price: int, parent_view: NetherMarketHubView):
        super().__init__()
        item = M.get_item(item_key)
        self.quantity_input.placeholder = f"{item['name'][:60]} @ {price:,} each"
        self.item_key = item_key
        self.price = price
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        try:
            qty = int(self.quantity_input.value.strip())
            if qty <= 0:
                raise ValueError
        except ValueError:
            self.parent_view._processing = False
            return await interaction.response.send_message(
                "Enter a positive whole number.", ephemeral=True
            )

        bot = self.parent_view.bot
        user_id = self.parent_view.user_id
        server_id = self.parent_view.server_id

        cap = M.get_holdings_cap(self.parent_view.profile["mastery_nodes"])
        held_count = await bot.database.nether_market.get_holdings_count(user_id, server_id)
        if held_count + qty > cap:
            self.parent_view._processing = False
            return await interaction.response.send_message(
                f"That would exceed your holdings cap ({held_count}/{cap}).", ephemeral=True
            )

        cost = self.price * qty
        if not await bot.database.users.deduct_gold_atomic(user_id, cost):
            self.parent_view._processing = False
            return await interaction.response.send_message("You don't have enough gold.", ephemeral=True)

        await bot.database.nether_market.modify_holdings(user_id, server_id, self.item_key, qty)
        await interaction.response.defer()
        await self.parent_view.refresh(interaction)


class SellModal(ui.Modal, title="Sell Curiosity"):
    quantity_input = ui.TextInput(
        label="Quantity", placeholder="e.g. 5", min_length=1, max_length=4, required=True
    )

    def __init__(self, item_key: str, price: int, parent_view: NetherMarketHubView):
        super().__init__()
        item = M.get_item(item_key)
        self.quantity_input.placeholder = f"{item['name'][:60]} @ {price:,} each"
        self.item_key = item_key
        self.price = price
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        try:
            qty = int(self.quantity_input.value.strip())
            if qty <= 0:
                raise ValueError
        except ValueError:
            self.parent_view._processing = False
            return await interaction.response.send_message(
                "Enter a positive whole number.", ephemeral=True
            )

        bot = self.parent_view.bot
        user_id = self.parent_view.user_id
        server_id = self.parent_view.server_id

        holdings = await bot.database.nether_market.get_holdings(user_id, server_id)
        held = holdings.get(self.item_key, 0)
        if qty > held:
            self.parent_view._processing = False
            return await interaction.response.send_message(
                f"You only hold {held} of that.", ephemeral=True
            )

        await bot.database.nether_market.modify_holdings(user_id, server_id, self.item_key, -qty)
        await bot.database.users.modify_gold(user_id, self.price * qty)
        await interaction.response.defer()
        await self.parent_view.refresh(interaction)
