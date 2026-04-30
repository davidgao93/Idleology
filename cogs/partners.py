import discord
from discord import app_commands, Interaction
from discord.ext import commands

from core.partners.views import PartnerMainView


class Partners(commands.Cog, name="partners"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="partner", description="Manage your partners.")
    async def partner(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        user_data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user_data):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        await self.bot.database.partners.ensure_items_row(user_id)
        items = await self.bot.database.partners.get_items(user_id)

        embed = discord.Embed(
            title="The Guild",
            description="Welcome to the Guild! Recruit, manage, and dispatch your partners.",
            color=0xFFD700,
        )
        embed.set_thumbnail(url="https://i.imgur.com/agWsjri.jpeg")
        embed.add_field(
            name="Guild Tickets 🎫",
            value=f"**{items.get('guild_tickets', 0):,}**",
            inline=True,
        )
        embed.add_field(
            name="Combat Shards ⚔️",
            value=f"**{items.get('combat_skill_shards', 0):,}**",
            inline=True,
        )
        embed.add_field(
            name="Dispatch Shards 🗺️",
            value=f"**{items.get('dispatch_skill_shards', 0):,}**",
            inline=True,
        )

        view = PartnerMainView(self.bot, user_id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(Partners(bot))
