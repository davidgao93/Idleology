"""
core/nether_market/views/browse_view.py — Target list (players + NPC vendors) and
the confirm-attack step that spends a plunder charge before opening PlunderView.
"""

import time

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.nether_market.data import NPC_VENDORS, WEALTH_TIERS
from core.nether_market.mechanics import NetherMarketMechanics as M

_PAGE_SIZE = 5


async def build_browse_view(bot, user_id: str, server_id: str) -> "BrowseListView":
    """Fetches every player who has a Nether Market profile plus the 6 NPC vendors,
    computes each target's wealth tier / shield status, and returns a fresh browse view."""
    rotation = await bot.database.nether_market.get_rotation(server_id)

    targets: list[dict] = []
    for candidate_id in await bot.database.nether_market.get_all_user_ids(server_id):
        if candidate_id == user_id:
            continue
        holdings = await bot.database.nether_market.get_holdings(candidate_id, server_id)
        if not holdings:
            continue  # nothing to plunder — exclude per design doc §15
        value = M.compute_holdings_value(holdings, rotation)
        profile = await bot.database.nether_market.get_or_create_profile(candidate_id, server_id)
        shielded = await bot.database.nether_market.is_shielded(candidate_id, server_id)
        targets.append(
            {
                "kind": "player",
                "user_id": candidate_id,
                "tier_index": M.get_wealth_tier(value),
                "last_plundered_at": profile["last_plundered_at"],
                "shielded": shielded,
                "shield_expires_at": profile["shield_expires_at"],
            }
        )

    for npc in NPC_VENDORS:
        targets.append({"kind": "npc", "npc": npc})

    attacker_profile = await bot.database.nether_market.get_or_create_profile(user_id, server_id)
    regen_seconds = M.get_charge_regen_seconds(attacker_profile["mastery_nodes"])
    charges, new_ts = M.calculate_charges(
        attacker_profile["plunder_charges"], attacker_profile["last_charge_time"], regen_seconds
    )
    if (charges, new_ts) != (attacker_profile["plunder_charges"], attacker_profile["last_charge_time"]):
        await bot.database.nether_market.restore_charges(user_id, server_id, charges, new_ts)
        attacker_profile["plunder_charges"] = charges
        attacker_profile["last_charge_time"] = new_ts

    return BrowseListView(bot, user_id, server_id, targets, attacker_profile)


class BrowseListView(BaseView):
    def __init__(self, bot, user_id, server_id, targets: list[dict], attacker_profile: dict):
        super().__init__(bot, user_id, server_id)
        self.targets = targets
        self.attacker_profile = attacker_profile
        self.current_page = 0
        self.total_pages = max(1, (len(targets) + _PAGE_SIZE - 1) // _PAGE_SIZE)
        self._processing = False
        self._display_names: dict[str, str] = {}
        self._build_buttons()

    async def _resolve_name(self, uid: str) -> str:
        if uid in self._display_names:
            return self._display_names[uid]
        try:
            user = await self.bot.fetch_user(int(uid))
            name = user.display_name
        except Exception:
            name = f"Unknown ({uid})"
        self._display_names[uid] = name
        return name

    def _page_targets(self) -> list[dict]:
        start = self.current_page * _PAGE_SIZE
        return self.targets[start : start + _PAGE_SIZE]

    async def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="\U0001f3af Browse Targets", color=discord.Color.dark_purple())
        charges = self.attacker_profile["plunder_charges"]
        embed.add_field(name="Plunder Charges", value=f"{charges} / {M.MAX_CHARGES}", inline=True)

        lines = []
        for i, target in enumerate(self._page_targets(), start=1):
            if target["kind"] == "npc":
                npc = target["npc"]
                tier_name = WEALTH_TIERS[npc["tier_index"]]["name"]
                lines.append(f"**[{i}]** {npc['name']} *(NPC)* — Tier: **{tier_name}**")
            else:
                name = await self._resolve_name(target["user_id"])
                tier_name = WEALTH_TIERS[target["tier_index"]]["name"]
                last = target["last_plundered_at"]
                last_str = "Never" if not last else f"<t:{int(last)}:R>"
                status = ""
                if target["shielded"]:
                    remaining = int(target["shield_expires_at"] - time.time())
                    status = f" \U0001f6e1️ Shielded ({max(0, remaining) // 3600}h left)"
                lines.append(
                    f"**[{i}]** {name} — Tier: **{tier_name}** — Last plundered: {last_str}{status}"
                )
        embed.description = "\n".join(lines) if lines else "No targets available right now."
        embed.set_footer(text=f"Page {self.current_page + 1} / {self.total_pages}")
        return embed

    def _build_buttons(self):
        self.clear_items()
        for i, target in enumerate(self._page_targets()):
            btn = ui.Button(label=str(i + 1), style=ButtonStyle.primary, row=0)
            btn.callback = self._make_select_callback(target)
            self.add_item(btn)

        if self.total_pages > 1:
            prev_btn = ui.Button(label="Prev", row=1, disabled=self.current_page == 0)
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)
            next_btn = ui.Button(
                label="Next", row=1, disabled=self.current_page == self.total_pages - 1
            )
            next_btn.callback = self.next_page
            self.add_item(next_btn)

        back_btn = ui.Button(label="Back to Market", style=ButtonStyle.secondary, row=2)
        back_btn.callback = self.go_back
        self.add_item(back_btn)

    def _make_select_callback(self, target: dict):
        async def _callback(interaction: Interaction):
            if self._processing:
                return await interaction.response.defer()
            await self._attempt_select(interaction, target)

        return _callback

    async def _attempt_select(self, interaction: Interaction, target: dict):
        if self.attacker_profile["plunder_charges"] <= 0:
            return await interaction.response.send_message(
                "You're out of plunder charges. They regenerate over time.", ephemeral=True
            )
        if target["kind"] == "player" and target["shielded"]:
            return await interaction.response.send_message(
                "That target is currently shielded from plunder attempts.", ephemeral=True
            )

        self._processing = True
        await interaction.response.defer()
        confirm_view = ConfirmAttackView(self.bot, self.user_id, self.server_id, target, self)
        await interaction.edit_original_response(
            embed=await confirm_view.build_embed(), view=confirm_view
        )

    async def prev_page(self, interaction: Interaction):
        self.current_page = max(0, self.current_page - 1)
        self._build_buttons()
        await interaction.response.edit_message(embed=await self.build_embed(), view=self)

    async def next_page(self, interaction: Interaction):
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self._build_buttons()
        await interaction.response.edit_message(embed=await self.build_embed(), view=self)

    async def go_back(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()
        from core.nether_market.views.hub_view import build_hub_view

        view = await build_hub_view(self.bot, self.user_id, self.server_id)
        msg = await interaction.edit_original_response(embed=view.build_embed(), view=view)
        view.message = msg
        self.stop()


class ConfirmAttackView(BaseView):
    """Confirmation step before a plunder charge is spent — cancel returns to the
    browse list unchanged (nothing has been consumed yet)."""

    def __init__(self, bot, user_id, server_id, target: dict, browse_view: BrowseListView):
        super().__init__(bot, user_id, server_id)
        self.target = target
        self.browse_view = browse_view
        self._processing = False

    async def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Confirm Plunder Attempt", color=discord.Color.orange())
        if self.target["kind"] == "npc":
            name = self.target["npc"]["name"]
        else:
            name = await self.browse_view._resolve_name(self.target["user_id"])
        embed.description = (
            f"Attack **{name}**? This will spend **1 plunder charge** and start a "
            "Mastermind session — the code is fresh and only used for this attempt."
        )
        return embed

    @ui.button(label="Confirm", style=ButtonStyle.danger)
    async def confirm(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()

        await self.bot.database.nether_market.consume_charge(self.user_id, self.server_id)
        attacker_profile = await self.bot.database.nether_market.get_or_create_profile(
            self.user_id, self.server_id
        )

        from core.nether_market.views.plunder_view import build_plunder_view

        view = await build_plunder_view(self.bot, self.user_id, self.server_id, self.target, attacker_profile)
        msg = await interaction.edit_original_response(embed=view.build_embed(), view=view)
        view.message = msg
        self.stop()

    @ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()
        self.browse_view._processing = False
        msg = await interaction.edit_original_response(
            embed=await self.browse_view.build_embed(), view=self.browse_view
        )
        self.browse_view.message = msg
        self.stop()
