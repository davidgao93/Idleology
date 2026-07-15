from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction, ui

from core.images import PARTNERS_SKILLS
from core.models import Partner
from core.partners.data import AFFINITY_STORIES
from core.partners.mechanics import next_available_story, portrait_unlocked
from core.partners.resources import _rarity_colour, _stars
from core.partners.views._helpers import PartnerBaseView

# ---------------------------------------------------------------------------
# AffinityStoryView
# ---------------------------------------------------------------------------


class AffinityStoryView(PartnerBaseView):
    def __init__(
        self, bot, user_id: str, partner: Partner, story_idx: int, affinity_view
    ):
        super().__init__(bot, user_id)
        self.partner = partner
        self.story_idx = story_idx
        self.affinity_view = affinity_view
        self._processing = False
        read_btn = ui.Button(label="Acknowledge", style=ButtonStyle.success)
        read_btn.callback = self._acknowledge
        self.add_item(read_btn)
        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary)
        back_btn.callback = self._back
        self.add_item(back_btn)

    def build_embed(self) -> discord.Embed:
        story_data = AFFINITY_STORIES.get(
            (self.partner.partner_id, self.story_idx),
            {
                "title": f"Story {self.story_idx}/4",
                "text": "*(Story placeholder — content coming soon.)*",
                "image_url": None,
            },
        )

        embed = discord.Embed(
            title=f"💞 {self.partner.name} — {story_data['title']}",
            description=story_data["text"],
            colour=_rarity_colour(self.partner.rarity),
        )

        image_url = story_data.get("image_url")
        if image_url:
            embed.set_image(url=image_url)
        elif self.partner.display_image:
            embed.set_thumbnail(url=self.partner.display_image)

        return embed

    async def _acknowledge(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        await self.bot.database.partners.update_affinity_story_seen(
            self.user_id, self.partner.partner_id, self.story_idx
        )
        self.partner.affinity_story_seen = self.story_idx
        for p in self.affinity_view.partners:
            if p.partner_id == self.partner.partner_id:
                p.affinity_story_seen = self.story_idx
        self.affinity_view._refresh()
        embed = self.affinity_view.build_embed()
        if portrait_unlocked(self.partner.affinity_encounters, self.story_idx):
            embed.add_field(
                name="🖼️ Portrait Unlocked!",
                value=f"Use **Switch Portrait** on {self.partner.name}'s detail page to toggle their new portrait.",
                inline=False,
            )
        else:
            embed.set_footer(text=f"The bond with {self.partner.name} grows stronger.")
        await interaction.edit_original_response(embed=embed, view=self.affinity_view)

    async def _back(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=self.affinity_view.build_embed(), view=self.affinity_view
        )


# ---------------------------------------------------------------------------
# AffinityView
# ---------------------------------------------------------------------------


class AffinityView(PartnerBaseView):
    def __init__(self, bot, user_id: str, partners_6star: list, items: dict, main_view):
        super().__init__(bot, user_id)
        self.partners = partners_6star
        self.items = items
        self.main_view = main_view
        self._refresh()

    def _refresh(self):
        self.clear_items()
        selectable = [p for p in self.partners if p.affinity_story_seen < 4]
        if selectable:
            options = []
            for p in selectable:
                story_idx = next_available_story(
                    p.affinity_encounters, p.affinity_story_seen
                )
                indicator = " ✨" if story_idx else ""
                portrait_tag = (
                    " 🖼️"
                    if portrait_unlocked(p.affinity_encounters, p.affinity_story_seen)
                    else ""
                )
                options.append(
                    discord.SelectOption(
                        label=f"{p.name}{indicator}",
                        value=str(p.partner_id),
                        description=f"{p.affinity_encounters} encounters | {p.affinity_story_seen}/4 stories{portrait_tag}",
                    )
                )
            select = ui.Select(
                placeholder="Select a partner to view their story…", options=options
            )
            select.callback = self._on_select
            self.add_item(select)
        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back_btn.callback = self._back
        self.add_item(back_btn)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="💞 Partner Affinity", colour=0xFF6B6B)
        embed.set_thumbnail(url=PARTNERS_SKILLS)
        lines = []
        for p in self.partners:
            story_idx = next_available_story(
                p.affinity_encounters, p.affinity_story_seen
            )
            portrait_tag = (
                " 🖼️"
                if portrait_unlocked(p.affinity_encounters, p.affinity_story_seen)
                else ""
            )
            new_tag = " ✨ **New story!**" if story_idx else ""
            lines.append(
                f"{_stars(6)} **{p.name}** — {p.affinity_encounters} encounters "
                f"({p.affinity_story_seen}/4 stories){portrait_tag}{new_tag}"
            )
        embed.description = (
            "\n".join(lines) if lines else "You have no 6★ partners yet."
        )
        embed.set_footer(text="✨ = new story available  |  🖼️ = alt portrait unlocked")
        return embed

    async def _on_select(self, interaction: Interaction):
        await interaction.response.defer()
        partner_id = int(interaction.data["values"][0])
        partner = next((p for p in self.partners if p.partner_id == partner_id), None)
        if not partner:
            return
        story_idx = next_available_story(
            partner.affinity_encounters, partner.affinity_story_seen
        )
        if not story_idx:
            await interaction.followup.send(
                f"No new stories available for **{partner.name}** yet. "
                f"Take them into more combat encounters!",
                ephemeral=True,
            )
            return
        view = AffinityStoryView(self.bot, self.user_id, partner, story_idx, self)
        view.message = self.message
        await interaction.edit_original_response(embed=view.build_embed(), view=view)

    async def _back(self, interaction: Interaction):
        await interaction.response.defer()
        embed, items, partners = await self.main_view._fetch_fresh_data()
        await interaction.edit_original_response(embed=embed, view=self.main_view)
