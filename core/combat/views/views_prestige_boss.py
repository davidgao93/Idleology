"""
Prestige Gathering Boss harvest views (Artisan Mastery Phase 2).

Shown after defeating a Meridian Golem, Drowned Leviathan, or Verdant Colossus.
Offers a one-time "Harvest" action that awards 2-5 matching remnants + 10 tripled ticks.
"""

import random

import discord
from discord.ui import Button, button

from core.base_view import BaseView
from core.skills.mastery import get_attunement_harvest_tripled_bonus


REMNANT_MAP = {
    "golem": ("geode_cores", "Geode Cores"),
    "leviathan": ("tide_relics", "Tide Relics"),
    "colossus": ("heartwood_shards", "Heartwood Shards"),
}


class PrestigeBossHarvestView(BaseView):
    """Custom post-combat view for prestige gathering bosses with a one-time harvest action."""

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

        self.remnant_col, self.remnant_name = REMNANT_MAP.get(
            prestige_boss_type, ("geode_cores", "Geode Cores")
        )

    async def on_timeout(self):
        try:
            await self.message.edit(view=None)
        except Exception:
            pass
        self.bot.state_manager.clear_active(self.user_id)

    @button(label="Harvest Remnants", style=discord.ButtonStyle.success, emoji="⛏️")
    async def harvest_btn(self, interaction: discord.Interaction, btn: Button):
        if self._harvested:
            await interaction.response.send_message("You've already harvested from this boss.", ephemeral=True)
            return

        await interaction.response.defer()

        # Roll 2-5 remnants (unaffected by bonuses, as per design)
        amount = random.randint(2, 5)

        # Award remnants
        await self.bot.database.skills.modify_remnants(
            self.user_id, self.server_id, {self.remnant_col: amount}
        )

        # Award +10 tripled ticks (base) + Grove's Reckoning bonus from Nature's Attunement
        skill_map = {"golem": "mining", "leviathan": "fishing", "colossus": "woodcutting"}
        skill = skill_map.get(self.prestige_boss_type, "mining")

        base_ticks = 10
        # Fetch fresh mastery row for the bonus (cheap)
        mrow = await self.bot.database.skills.get_mastery(self.user_id, self.server_id)
        extra = get_attunement_harvest_tripled_bonus(mrow)
        total_ticks = base_ticks + extra

        await self.bot.database.skills.add_tripled_ticks(
            self.user_id, self.server_id, skill, total_ticks
        )

        self._harvested = True
        btn.disabled = True
        btn.label = "Harvested!"

        # Update embed with results
        extra_ticks = total_ticks - 10
        bonus_line = f" (+{extra_ticks} from Grove's Reckoning)" if extra_ticks > 0 else ""
        embed = discord.Embed(
            title=f"✨ {self.monster.name} Defeated!",
            description=(
                f"You have successfully overcome the ancient guardian.\n\n"
                f"**Harvest Complete!**\n"
                f"You obtained **{amount} {self.remnant_name}**.\n"
                f"Your next **{total_ticks}** passive {skill.title()} ticks will yield **3×** resources{bonus_line}."
            ),
            color=0x2E8B57,
        )
        embed.set_thumbnail(url=self.monster.image)
        embed.set_footer(text="Normal combat rewards have already been granted.")

        await interaction.edit_original_response(embed=embed, view=self)

        # Persist player state
        await self.bot.database.users.update_from_player_object(self.player)

        # Transition to normal post-combat view so "Fight Again" (if stamina remains) can appear
        try:
            from core.combat.views.views import PostCombatView

            stamina_data = await self.bot.database.users.get_stamina(self.user_id)
            stamina = stamina_data.get("combat_stamina", 0)

            post_view = PostCombatView(
                self.bot,
                self.user_id,
                self.server_id,
                self.player,
                stamina,
                self.rematch_callback,
            )
            # Replace the current message with the normal post-combat view
            await interaction.edit_original_response(embed=embed, view=post_view)
            post_view.message = self.message
        except Exception as e:
            # If anything goes wrong during transition, at least leave the harvest result visible
            print(f"[PrestigeBossHarvestView] Failed to transition to PostCombatView: {e}")

    async def on_done(self, message):
        """Called after harvest (or timeout) to transition to normal post-combat flow if needed."""
        self.bot.state_manager.clear_active(self.user_id)
        # In a full implementation we would show PostCombatView here,
        # but for the prestige boss flow we let the caller decide.
        pass
