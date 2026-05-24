from __future__ import annotations

import asyncio
import random
from typing import List, Optional

import discord
from discord import ButtonStyle, Interaction, ui

from core.images import (
    GACHA_BANNER_4STAR,
    GACHA_BANNER_5STAR,
    GACHA_BANNER_6STAR,
    PARTNERS_INTRO,
)
from core.models import Partner
from core.partners.data import PARTNER_DATA
from core.partners.mechanics import generate_skill_slots, roll_single, roll_ten
from core.partners.resources import _rarity_colour, _stars
from core.partners.ui import _build_partner_embed
from core.partners.views._helpers import PartnerBaseView

_RARITY_EMOJIS = {4: "💙", 5: "💛", 6: "❤️"}
_MAX_SIG_TIER = 5
_MAX_TICKET_GRANT = 10


async def _get_sig_lvl(bot, user_id: str, partner_id: int) -> int:
    row = await bot.database.partners.get_partner(user_id, partner_id)
    if not row:
        return 0
    return row[11]  # sig_combat_lvl column index


# ---------------------------------------------------------------------------
# PullResultView  (shown after a pull when there's at least one new partner)
# ---------------------------------------------------------------------------


class PullResultView(PartnerBaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        pull_view,
        new_partners: List[dict],
        highest_dup: Optional[dict] = None,
    ):
        super().__init__(bot, user_id)
        self.pull_view = pull_view
        self.new_partners = new_partners
        self.highest_dup = highest_dup
        self.current_index = 0
        self._update_buttons()

    def _update_buttons(self):
        self.clear_items()

        if len(self.new_partners) > 1:
            left = ui.Button(
                emoji="⬅️", style=ButtonStyle.gray, disabled=self.current_index == 0
            )
            left.callback = self._prev
            self.add_item(left)

            right = ui.Button(
                emoji="➡️",
                style=ButtonStyle.gray,
                disabled=self.current_index == len(self.new_partners) - 1,
            )
            right.callback = self._next
            self.add_item(right)

        again1 = ui.Button(
            label="Pull Again (1 ticket)", style=ButtonStyle.primary, row=1
        )
        again1.callback = self._pull_again
        self.add_item(again1)

        again10 = ui.Button(
            label="Pull ×10 (10 tickets)", style=ButtonStyle.success, row=1
        )
        again10.callback = self._pull_ten
        self.add_item(again10)

        back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back.callback = self._back
        self.add_item(back)

    def _build_embed(self) -> discord.Embed:
        if self.new_partners:
            data = self.new_partners[self.current_index]
            static = data["static"]
            rarity = data["rarity"]
            title = f"🎫 New Partner! {_stars(rarity)} {static['name']}"
        else:
            static = self.highest_dup["static"]
            rarity = self.highest_dup["rarity"]
            title = f"🎫 Pull Results — {_stars(rarity)} {static['name']} (Duplicate)"

        embed = discord.Embed(
            title=title,
            description=static.get("pull_message", "A new ally joins the fray!"),
            colour=_rarity_colour(rarity),
        )
        embed.set_image(url=static["image_url"])

        if len(self.new_partners) > 1:
            embed.set_footer(
                text=f"New partner {self.current_index + 1}/{len(self.new_partners)} • "
                f"Use arrows to browse"
            )
        else:
            embed.set_footer(text="Pull complete!")

        return embed

    async def _prev(self, interaction: Interaction):
        self.current_index = max(0, self.current_index - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _next(self, interaction: Interaction):
        self.current_index = min(len(self.new_partners) - 1, self.current_index + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _pull_again(self, interaction: Interaction):
        await self.pull_view._do_pull(interaction, count=1)
        self.stop()

    async def _pull_ten(self, interaction: Interaction):
        await self.pull_view._do_pull(interaction, count=10)
        self.stop()

    async def _back(self, interaction: Interaction):
        items = await self.bot.database.partners.get_items(self.user_id)
        pull_view = PullView(self.bot, self.user_id, self.pull_view.main_view)
        pull_view.message = self.message
        await interaction.response.edit_message(
            embed=pull_view.build_embed(items), view=pull_view
        )
        self.stop()


# ---------------------------------------------------------------------------
# PullView
# ---------------------------------------------------------------------------


class PullView(PartnerBaseView):
    def __init__(self, bot, user_id: str, main_view):
        super().__init__(bot, user_id)
        self.main_view = main_view

    def build_embed(self, items: dict) -> discord.Embed:
        embed = discord.Embed(
            title="🎫 Partner Pull",
            colour=0xFFD700,
        )
        embed.description = (
            "Spend **Guild Tickets** to recruit new partners!\n\n"
            "**Rates:**\n88% ★★★★\n11% ★★★★★\n1% ★★★★★★\n"
            "10-pull guarantees a 5★ partner."
        )
        embed.add_field(
            name="Your Tickets",
            value=f"🎫 **{items.get('guild_tickets', 0)}** tickets",
        )
        embed.add_field(
            name="Pity",
            value=f"**{items.get('pity_counter', 0)}/100**",
        )
        embed.set_image(url=PARTNERS_INTRO)
        return embed

    @ui.button(label="Pull ×1 (1 ticket)", style=ButtonStyle.primary)
    async def pull_one(self, interaction: Interaction, button: ui.Button):
        await self._do_pull(interaction, count=1)

    @ui.button(label="Pull ×10 (10 tickets)", style=ButtonStyle.success)
    async def pull_ten(self, interaction: Interaction, button: ui.Button):
        await self._do_pull(interaction, count=10)

    @ui.button(label="Back", style=ButtonStyle.secondary, row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        embed, items, partners = await self.main_view._fetch_fresh_data()
        await interaction.edit_original_response(embed=embed, view=self.main_view)
        self.stop()

    async def _do_pull(self, interaction: Interaction, count: int):
        ticket_cost = count
        ok = await self.bot.database.partners.spend_tickets(self.user_id, ticket_cost)
        if not ok:
            await interaction.response.send_message(
                f"Not enough tickets! You need **{ticket_cost}** 🎫.", ephemeral=True
            )
            return

        await interaction.response.defer()

        items = await self.bot.database.partners.get_items(self.user_id)
        pity = items["pity_counter"]

        if count == 1:
            rarity, new_pity = roll_single(pity)
            rarities = [rarity]
        else:
            rarities, new_pity = roll_ten(pity)

        await self.bot.database.partners.update_pity(self.user_id, new_pity)

        max_rarity = max(rarities)
        banner_urls = {
            4: GACHA_BANNER_4STAR,
            5: GACHA_BANNER_5STAR,
            6: GACHA_BANNER_6STAR,
        }
        banner_embed = discord.Embed(
            title="🎫 Recruiting...",
            description="The clerk hands you a scroll, you unfurl it...",
            colour=_rarity_colour(max_rarity),
        )
        banner_embed.set_image(url=banner_urls.get(max_rarity))
        await interaction.edit_original_response(embed=banner_embed, view=None)

        await asyncio.sleep(3)

        all_partners_by_rarity = {
            4: [pid for pid, d in PARTNER_DATA.items() if d["rarity"] == 4],
            5: [pid for pid, d in PARTNER_DATA.items() if d["rarity"] == 5],
            6: [pid for pid, d in PARTNER_DATA.items() if d["rarity"] == 6],
        }

        result_lines = []
        shards_combat = 0
        shards_dispatch = 0
        char_shards_gained: dict[int, int] = {}

        new_partners: List[Partner] = []
        highest_dup_rarity = 0
        highest_dup_static = None

        for rarity in rarities:
            pool = all_partners_by_rarity.get(rarity, all_partners_by_rarity[4])
            partner_id = random.choice(pool)
            static = PARTNER_DATA[partner_id]
            emoji = _RARITY_EMOJIS.get(rarity, "💙")

            already_owned = await self.bot.database.partners.owns_partner(
                self.user_id, partner_id
            )

            if not already_owned:
                co_slots = generate_skill_slots(rarity, "combat")
                di_slots = generate_skill_slots(rarity, "dispatch")
                await self.bot.database.partners.add_partner(
                    self.user_id, partner_id, co_slots, di_slots
                )
                result_lines.append(
                    f"{emoji} **NEW** — {_stars(rarity)} **{static['name']}**!"
                )

                row = await self.bot.database.partners.get_partner(
                    self.user_id, partner_id
                )
                if row:
                    partner_obj = Partner.from_row(row, static)
                    new_partners.append(partner_obj)
            else:
                if rarity == 6:
                    cur_sig = await _get_sig_lvl(self.bot, self.user_id, partner_id)
                    if cur_sig >= _MAX_SIG_TIER:
                        await self.bot.database.partners.add_tickets(
                            self.user_id, _MAX_TICKET_GRANT
                        )
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** (Sig MAX) → +{_MAX_TICKET_GRANT} 🎫"
                        )
                    else:
                        char_shards_gained[partner_id] = (
                            char_shards_gained.get(partner_id, 0) + 1
                        )
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** → +1 signature skill shard"
                        )
                elif rarity == 5:
                    if random.random() < 0.5:
                        shards_combat += 3
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** → +3 combat skill shards ⚔️"
                        )
                    else:
                        shards_dispatch += 3
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** → +3 dispatch skill shards 📋"
                        )
                else:
                    if random.random() < 0.5:
                        shards_combat += 1
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** → +1 combat skill shard ⚔️"
                        )
                    else:
                        shards_dispatch += 1
                        result_lines.append(
                            f"{emoji} {_stars(rarity)} **{static['name']}** → +1 dispatch skill shard 📋"
                        )

                if rarity > highest_dup_rarity:
                    highest_dup_rarity = rarity
                    highest_dup_static = static

        if shards_combat > 0:
            await self.bot.database.partners.add_combat_shards(
                self.user_id, shards_combat
            )
        if shards_dispatch > 0:
            await self.bot.database.partners.add_dispatch_shards(
                self.user_id, shards_dispatch
            )
        total_char_shards = sum(char_shards_gained.values())
        if total_char_shards > 0:
            await self.bot.database.partners.add_shard(
                self.user_id, 0, total_char_shards
            )

        items_after = await self.bot.database.partners.get_items(self.user_id)

        # Stage 2: Recap / Quote stage
        if count == 1:
            if new_partners:
                partner = new_partners[0]
                quote_embed = discord.Embed(
                    title="A partner has answered your call!",
                    description=f"{partner.pull_message}",
                    colour=_rarity_colour(partner.rarity),
                )
                if partner.display_image:
                    quote_embed.set_image(url=partner.display_image)
                await interaction.edit_original_response(embed=quote_embed, view=None)
            else:
                dup_embed = discord.Embed(
                    title=f"Duplicate — {_stars(highest_dup_rarity)} {highest_dup_static['name']}",
                    description="This partner has already joined you.",
                    colour=_rarity_colour(highest_dup_rarity),
                )
                dup_embed.set_image(url=highest_dup_static["image_url"])
                dup_embed.add_field(
                    name="Reward",
                    value="\n".join(result_lines[-1:]) or "Shard obtained",
                    inline=False,
                )
                await interaction.edit_original_response(embed=dup_embed, view=None)
        else:
            plethora_embed = discord.Embed(
                title="A plethora of partners have answered your call!",
                description="\n".join(result_lines) or "No results.",
                colour=0xFFD700,
            )
            plethora_embed.set_footer(
                text=f"Pity: {new_pity}/100  |  🎫 {items_after.get('guild_tickets', 0)} tickets"
            )
            await interaction.edit_original_response(embed=plethora_embed, view=None)

        await asyncio.sleep(2.5)

        # Stage 3: Final view
        if new_partners:
            if count == 1:
                final_view = SinglePullDetailView(
                    self.bot, self.user_id, new_partners[0], self
                )
            else:
                final_view = NewPartnersBrowserView(
                    self.bot, self.user_id, new_partners, self
                )
            final_view.message = self.message
            await interaction.edit_original_response(
                embed=final_view.build_embed(), view=final_view
            )
        else:
            if count == 1:
                recap_view = PullRecapView(self.bot, self.user_id, self)
                recap_view.message = self.message
                await interaction.edit_original_response(
                    embed=dup_embed, view=recap_view
                )
            else:
                recap_view = PullRecapView(self.bot, self.user_id, self)
                recap_view.message = self.message
                await interaction.edit_original_response(view=recap_view)
        # Stop this view so its timeout doesn't clobber the final view's buttons.
        self.stop()


# ---------------------------------------------------------------------------
# SinglePullDetailView
# ---------------------------------------------------------------------------


class SinglePullDetailView(PartnerBaseView):
    def __init__(self, bot, user_id: str, partner: Partner, pull_view):
        super().__init__(bot, user_id)
        self.partner = partner
        self.pull_view = pull_view

    def build_embed(self) -> discord.Embed:
        return _build_partner_embed(self.partner, {})

    @ui.button(label="Pull Again (1 ticket)", style=ButtonStyle.primary, row=1)
    async def pull_one(self, interaction: Interaction, button: ui.Button):
        await self.pull_view._do_pull(interaction, count=1)
        self.stop()

    @ui.button(label="Pull ×10 (10 tickets)", style=ButtonStyle.success, row=1)
    async def pull_ten(self, interaction: Interaction, button: ui.Button):
        await self.pull_view._do_pull(interaction, count=10)
        self.stop()

    @ui.button(label="Back", style=ButtonStyle.secondary, row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        items = await self.bot.database.partners.get_items(self.user_id)
        pull_view = PullView(self.bot, self.user_id, self.pull_view.main_view)
        pull_view.message = self.message
        await interaction.response.edit_message(
            embed=pull_view.build_embed(items), view=pull_view
        )
        self.stop()


# ---------------------------------------------------------------------------
# NewPartnersBrowserView
# ---------------------------------------------------------------------------


class NewPartnersBrowserView(PartnerBaseView):
    def __init__(self, bot, user_id: str, new_partners: List[Partner], pull_view):
        super().__init__(bot, user_id)
        self.new_partners = new_partners
        self.pull_view = pull_view
        self.current_index = 0
        self._update_buttons()

    def _update_buttons(self):
        self.clear_items()

        if len(self.new_partners) > 1:
            left = ui.Button(
                emoji="⬅️", style=ButtonStyle.gray, disabled=self.current_index == 0
            )
            left.callback = self._prev
            self.add_item(left)

            right = ui.Button(
                emoji="➡️",
                style=ButtonStyle.gray,
                disabled=self.current_index == len(self.new_partners) - 1,
            )
            right.callback = self._next
            self.add_item(right)

        one = ui.Button(label="Pull Again (1 ticket)", style=ButtonStyle.primary, row=1)
        one.callback = self._pull_one
        self.add_item(one)

        ten = ui.Button(label="Pull ×10 (10 tickets)", style=ButtonStyle.success, row=1)
        ten.callback = self._pull_ten
        self.add_item(ten)

        back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back.callback = self._back
        self.add_item(back)

    def build_embed(self) -> discord.Embed:
        partner = self.new_partners[self.current_index]
        embed = _build_partner_embed(partner, {})
        embed.title = (
            f"🎫 New Partner Acquired! {_stars(partner.rarity)} {partner.name}"
        )
        if len(self.new_partners) > 1:
            embed.set_footer(
                text=f"New partner {self.current_index + 1}/{len(self.new_partners)} • Use arrows to browse"
            )
        return embed

    async def _prev(self, interaction: Interaction):
        self.current_index = max(0, self.current_index - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _next(self, interaction: Interaction):
        self.current_index = min(len(self.new_partners) - 1, self.current_index + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _pull_one(self, interaction: Interaction):
        await self.pull_view._do_pull(interaction, count=1)
        self.stop()

    async def _pull_ten(self, interaction: Interaction):
        await self.pull_view._do_pull(interaction, count=10)
        self.stop()

    async def _back(self, interaction: Interaction):
        items = await self.bot.database.partners.get_items(self.user_id)
        pull_view = PullView(self.bot, self.user_id, self.pull_view.main_view)
        pull_view.message = self.message
        await interaction.response.edit_message(
            embed=pull_view.build_embed(items), view=pull_view
        )
        self.stop()


# ---------------------------------------------------------------------------
# PullRecapView  (10x all-duplicates case)
# ---------------------------------------------------------------------------


class PullRecapView(PartnerBaseView):
    def __init__(self, bot, user_id: str, pull_view):
        super().__init__(bot, user_id)
        self.pull_view = pull_view

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass

    @ui.button(label="Pull Again (1 ticket)", style=ButtonStyle.primary, row=1)
    async def pull_one(self, interaction: Interaction, button: ui.Button):
        await self.pull_view._do_pull(interaction, count=1)
        self.stop()

    @ui.button(label="Pull ×10 (10 tickets)", style=ButtonStyle.success, row=1)
    async def pull_ten(self, interaction: Interaction, button: ui.Button):
        await self.pull_view._do_pull(interaction, count=10)
        self.stop()

    @ui.button(label="Back", style=ButtonStyle.secondary, row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        items = await self.bot.database.partners.get_items(self.user_id)
        pull_view = PullView(self.bot, self.user_id, self.pull_view.main_view)
        pull_view.message = self.message
        await interaction.response.edit_message(
            embed=pull_view.build_embed(items), view=pull_view
        )
        self.stop()
