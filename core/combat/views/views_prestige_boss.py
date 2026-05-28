"""
Prestige Gathering Boss harvest views (Artisan Mastery Phase 2).

Shown after defeating a Meridian Golem, Drowned Leviathan, or Verdant Colossus.
Offers a one-time "Harvest" action that awards 2-5 matching remnants + 10 tripled ticks.
After harvesting, a Fight Again button is added inline (the Harvested! button stays visible).
"""

import random

import discord
from discord.ui import Button, button

from core.base_view import BaseView
from core.images import (
    MERIDIAN_GOLEM_DEFEAT,
    DROWNED_LEVIATHAN_DEFEAT,
    VERDANT_COLOSSUS_DEFEAT,
)
from core.skills.mastery import get_attunement_harvest_tripled_bonus


REMNANT_MAP = {
    "golem": ("geode_cores", "Geode Cores"),
    "leviathan": ("tide_relics", "Tide Relics"),
    "colossus": ("heartwood_shards", "Heartwood Shards"),
}


class PrestigeBossHarvestView(BaseView):
    """Custom post-combat view for prestige gathering bosses with a one-time harvest action.

    State contract:
      • By the time this view is shown, CombatView has already called
        state_manager.clear_active(), update_from_player_object(), save_jewel_state(),
        and self.stop().  This view does NOT own the "active" state.
      • Fight Again re-acquires "active" when clicked, exactly like PostCombatView.
    """

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player,
        monster,
        prestige_boss_type: str,
        rematch_callback=None,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.monster = monster
        self.prestige_boss_type = prestige_boss_type  # "golem", "leviathan", or "colossus"
        self.rematch_callback = rematch_callback
        self._harvested = False
        self._launching = False  # Re-entry guard for Fight Again

        self.remnant_col, self.remnant_name = REMNANT_MAP.get(
            prestige_boss_type, ("geode_cores", "Geode Cores")
        )

    # ------------------------------------------------------------------
    # Harvest
    # ------------------------------------------------------------------

    @button(label="Harvest Remnants", style=discord.ButtonStyle.success, emoji="⛏️")
    async def harvest_btn(self, interaction: discord.Interaction, btn: Button):
        if self._harvested:
            await interaction.response.defer()
            return

        await interaction.response.defer()

        # Roll 2-5 remnants (unaffected by bonuses, as per design)
        amount = random.randint(2, 5)
        await self.bot.database.skills.modify_remnants(
            self.user_id, self.server_id, {self.remnant_col: amount}
        )

        # Award +10 tripled ticks (base) + Grove's Reckoning bonus from Nature's Attunement
        skill_map = {"golem": "mining", "leviathan": "fishing", "colossus": "woodcutting"}
        skill = skill_map.get(self.prestige_boss_type, "mining")
        base_ticks = 10
        mrow = await self.bot.database.skills.get_mastery(self.user_id, self.server_id)
        extra = get_attunement_harvest_tripled_bonus(mrow)
        total_ticks = base_ticks + extra
        await self.bot.database.skills.add_tripled_ticks(
            self.user_id, self.server_id, skill, total_ticks
        )

        self._harvested = True
        btn.disabled = True
        btn.label = "Harvested!"

        # Add Fight Again button inline if stamina remains and rematch is wired up
        if self.rematch_callback:
            stamina_data = await self.bot.database.users.get_stamina(self.user_id)
            stamina = stamina_data.get("combat_stamina", 0)
            if stamina > 0:
                fight_btn = Button(
                    label=f"Fight Again  ⚡{stamina:g}",
                    style=discord.ButtonStyle.green,
                )
                fight_btn.callback = self._fight_again
                self.add_item(fight_btn)

        # Build result embed (single edit — Harvested! button stays visible)
        extra_ticks = total_ticks - base_ticks
        bonus_line = f" (+{extra_ticks} from Grove's Reckoning)" if extra_ticks > 0 else ""
        embed = discord.Embed(
            title=f"✨ {self.monster.name} Defeated!",
            description=(
                f"You have successfully overcome the ancient guardian.\n\n"
                f"**Harvest Complete!**\n"
                f"You obtained **{amount} {self.remnant_name}**.\n"
                f"Your next **{total_ticks}** passive {skill.title()} ticks "
                f"will yield **3×** resources{bonus_line}."
            ),
            color=0x2E8B57,
        )
        defeat_image = self.monster.image
        if self.prestige_boss_type == "golem":
            defeat_image = MERIDIAN_GOLEM_DEFEAT
        elif self.prestige_boss_type == "leviathan":
            defeat_image = DROWNED_LEVIATHAN_DEFEAT
        elif self.prestige_boss_type == "colossus":
            defeat_image = VERDANT_COLOSSUS_DEFEAT
        embed.set_thumbnail(url=defeat_image)
        embed.set_footer(text="Normal combat rewards have already been granted.")

        await interaction.edit_original_response(embed=embed, view=self)

    # ------------------------------------------------------------------
    # Fight Again
    # ------------------------------------------------------------------

    async def _fight_again(self, interaction: discord.Interaction):
        if self._launching:
            await interaction.response.defer()
            return
        self._launching = True

        await interaction.response.defer()

        # Lock all buttons immediately
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        if self.bot.state_manager.is_active(self.user_id):
            await interaction.followup.send(
                "You're already in an activity.", ephemeral=True
            )
            self.stop()
            return

        existing_user = await self.bot.database.users.get(self.user_id, self.server_id)
        if existing_user["combat_stamina"] <= 0:
            await interaction.followup.send("No stamina remaining!", ephemeral=True)
            self.stop()
            return

        from core.items.factory import load_player
        fresh_player = await load_player(self.user_id, existing_user, self.bot.database)
        self.bot.state_manager.set_active(self.user_id, "combat")
        await self.rematch_callback(
            interaction, self.user_id, self.server_id, existing_user, fresh_player
        )
        self.stop()
