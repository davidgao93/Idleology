"""
core/nether_market/views/holdings_view.py — Read-only breakdown of every item type
the player currently holds. The hub embed only shows held quantities for the 3
currently active offers; this lists everything, including items that have
rotated out and are only valued at true value in the meantime.
"""

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.images import VEX_PORTRAIT, VEX_THUMBNAIL
from core.nether_market.data import ITEM_POOL
from core.nether_market.mechanics import NetherMarketMechanics as M
from core.npc_voices import get_quip

_TIER_LABELS = (("cheap", "Cheap"), ("med", "Medium"), ("expensive", "Expensive"))


async def build_holdings_view(bot, user_id: str, server_id: str) -> "HoldingsView":
    rotation = await bot.database.nether_market.get_rotation(server_id)
    holdings = await bot.database.nether_market.get_holdings(user_id, server_id)
    profile = await bot.database.nether_market.get_or_create_profile(user_id, server_id)
    return HoldingsView(bot, user_id, server_id, holdings, rotation, profile)


class HoldingsView(BaseView):
    def __init__(
        self,
        bot,
        user_id,
        server_id,
        holdings: dict,
        rotation: dict | None,
        profile: dict,
    ):
        super().__init__(bot, user_id, server_id)
        self.holdings = holdings
        self.rotation = rotation
        self.profile = profile
        self._processing = False
        self._build_buttons()

    def build_embed(self) -> discord.Embed:
        active_offers = M.active_offers(self.rotation) if self.rotation else {}
        cap = M.get_holdings_cap(self.profile["mastery_nodes"])
        held_count = sum(self.holdings.values())
        total_value = M.compute_holdings_value(self.holdings, self.rotation)

        embed = discord.Embed(
            title="\U0001f4e6 Your Holdings", color=discord.Color.dark_purple()
        )
        embed.set_author(name="Vex, the Fence", icon_url=VEX_PORTRAIT)
        if VEX_THUMBNAIL:
            embed.set_thumbnail(url=VEX_THUMBNAIL)

        lines = []
        for tier_key, tier_label in _TIER_LABELS:
            for item in ITEM_POOL[tier_key]:
                qty = self.holdings.get(item["key"], 0)
                if qty <= 0:
                    continue
                is_active = item["key"] in active_offers
                price = active_offers.get(item["key"], item["true_value"])
                subtotal = price * qty
                tag = " \U0001f504" if is_active else ""
                lines.append(
                    f"**{qty}x** {item['name']} *({tier_label})*{tag} — {price:,} each = {subtotal:,}"
                )

        embed.description = (
            "\n".join(lines) if lines else "You aren't holding anything right now."
        )
        embed.add_field(name="Total Slots", value=f"{held_count} / {cap}", inline=True)
        embed.add_field(
            name="Total Value", value=f"\U0001f4b0 ~{total_value:,}", inline=True
        )
        embed.set_footer(
            text=f"{get_quip('nether_market_holdings')}\n"
            "\U0001f504 = currently one of the 6 active offers, sellable at that price"
        )
        return embed

    def _build_buttons(self):
        self.clear_items()
        back_btn = ui.Button(label="Back to Market", style=ButtonStyle.secondary, row=0)
        back_btn.callback = self.go_back
        self.add_item(back_btn)

    async def go_back(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()
        from core.nether_market.views.hub_view import build_hub_view

        view = await build_hub_view(self.bot, self.user_id, self.server_id)
        msg = await interaction.edit_original_response(
            embed=view.build_embed(), view=view
        )
        view.message = msg
        self.stop()
