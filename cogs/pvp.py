import random
import discord
from discord.ext import commands
from discord.ext.tasks import asyncio
from discord import app_commands, Interaction, Message

# Here we name the cog and create a new class for the cog.
class Pvp(commands.Cog, name="pvp"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="duel", description="Challenge another user to a PvP duel.")
    async def pvp(self, interaction: Interaction, member: discord.Member, gold_amount: int) -> None:
        user_id = str(interaction.user.id)
        challenged_user_id = str(member.id)
        existing_user = await self.bot.database.fetch_user(user_id, interaction.guild.id)
        challenged_user = await self.bot.database.fetch_user(challenged_user_id, interaction.guild.id)
        if not await self.bot.check_is_active(interaction, user_id):
            return
        
        if existing_user and challenged_user:
            challenged_gold = challenged_user[6]
            challenger_gold = existing_user[6]

            if challenger_gold < gold_amount:
                await interaction.response.send_message(
                    "You do not have enough gold to initiate this challenge!",
                    ephemeral=True)
                return

            if challenged_gold < gold_amount:
                await interaction.response.send_message(
                    f"{member.name} does not have enough gold to accept the challenge!",
                    ephemeral=True)
                return
            
            if gold_amount <= 0:
                await interaction.response.send_message(
                    "You cannot challenge with zero or negative gold.",
                    ephemeral=True)
                return

            embed = discord.Embed(
                title="PvP Challenge!",
                description=f"{interaction.user.mention} has challenged {member.mention} for **{gold_amount:,} gold**!\n"
                            f"React with ✅ to accept the challenge!",
                color=0x00FF00,
            )
            embed.set_image(url="https://i.imgur.com/z20wfJO.jpeg")
            await interaction.response.send_message(embed=embed)
            message: Message = await interaction.original_response()
            await message.add_reaction("✅")
            await message.add_reaction("❌")
            self.bot.state_manager.set_active(user_id, "duel")

            def check(reaction, user):
                return user == member and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == message.id

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                if str(reaction.emoji) == "✅":
                    if self.bot.state_manager.is_active(challenged_user_id):
                        await interaction.followup.send("You cannot accept this duel. Please finish all other interactions.")
                        await message.delete()
                        self.bot.state_manager.clear_active(user_id)
                        return
                else:
                    self.bot.state_manager.clear_active(user_id)
                    await message.delete()
                    return
            except asyncio.TimeoutError:
                self.bot.state_manager.clear_active(user_id)
                await message.delete()
                return

            player = existing_user[3]
            opponent = challenged_user[3]
            await self.start_duel(interaction, user_id, challenged_user_id, gold_amount, member, player, opponent, message)
        else:
            await interaction.response.send_message("There was an error fetching user data.")

    async def start_duel(self, interaction: Interaction, 
                         challenger_id: str, challenged_id: str, 
                         gold_amount: int, member: discord.Member,
                         player: str, opponent: str, message) -> None:
        self.bot.state_manager.set_active(challenged_id, "duel")
        await message.clear_reactions()
        challenger_hp = 100
        challenged_hp = 100
        self.bot.logger.info(f"Challenger: {challenger_id}, Challenged: {challenged_id}")
        self.bot.logger.info(f"Challenger name: {player}, Challenged name: {opponent}")
        turn_order = random.choice([challenger_id, challenged_id])
        name = ''
        if turn_order == challenger_id:
            starter = challenger_id
            name = player
        else:
            starter = challenged_id
            name = opponent

        embed = discord.Embed(
            title="PvP Duel Begins!",
            color=0x00FF00
        )
        embed.set_thumbnail(url="https://i.imgur.com/z20wfJO.jpeg")
        embed.add_field(name=f"{name} has won the coin toss!", value="Beginning in 3...", inline=False)
        embed.add_field(name=f"{player}'s HP ❤️", value=challenger_hp, inline=True)
        embed.add_field(name=f"{opponent}'s HP ❤️", value=challenged_hp, inline=True)
        embed.add_field(name=f"Waiting for input", value="Pick an action!", inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(1)
        embed.set_field_at(0, name=f"{name} has won the coin toss!", value="Beginning in 2...", inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(1)
        embed.set_field_at(0, name=f"{name} has won the coin toss!", value="Beginning in 1...", inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(1)
        embed.set_field_at(0, name=f"{name} has won the coin toss!", value="FIGHT!", inline=False)
        await message.edit(embed=embed)
        current_player = starter
        if turn_order == challenger_id:
            name = player
        else:
            name = opponent

        await message.add_reaction("⚔️")
        await message.add_reaction("💖")

        while challenger_hp > 0 and challenged_hp > 0:
            embed.set_field_at(0, name=f"It's **{name}**'s turn!", value="Do you choose to HIT ⚔️ or HEAL 💖? ", inline=False)
            await message.edit(embed=embed)

            def action_check(reaction, user):
                return (
                    user.id == int(current_player) and 
                    reaction.message.id == message.id and 
                    str(reaction.emoji) in ["⚔️", "💖"]
                )

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=action_check)

                if str(reaction.emoji) == "⚔️":
                    if random.randint(1, 100) <= 30:
                        response_message = f"{name}'s attack 💨 misses! "
                    else:
                        damage = self.calculate_damage(challenger_hp if current_player == challenger_id else challenged_hp)
                        if current_player == challenger_id:
                            challenged_hp -= damage
                            response_message = f"{name} attacked for 💥 **{damage}**!"
                            embed.set_field_at(2, name=f"{opponent}'s HP ❤️", value=challenged_hp, inline=True)
                        else:
                            challenger_hp -= damage
                            response_message = f"{name} attacked for 💥 **{damage}**!"
                            embed.set_field_at(1, name=f"{player}'s HP ❤️", value=challenger_hp, inline=True)
                else:
                    heal_amount = 20
                    if current_player == challenger_id:
                        challenger_hp = min(challenger_hp + heal_amount, 100)
                        response_message = f"{name} healed for **{heal_amount}**."
                        embed.set_field_at(1, name=f"{player}'s HP ❤️", value=challenger_hp, inline=True)
                    else:
                        challenged_hp = min(challenged_hp + heal_amount, 100)
                        response_message = f"{name} healed for **{heal_amount}**."
                        embed.set_field_at(2, name=f"{opponent}'s HP ❤️", value=challenged_hp, inline=True)
                await message.remove_reaction(reaction.emoji, user)
                embed.set_field_at(3, name=f"Result", value=response_message, inline=False)
                await asyncio.sleep(1)

                current_player = challenged_id if current_player == challenger_id else challenger_id
                if current_player == challenger_id:
                    name = player
                else:
                    name = opponent

            except asyncio.TimeoutError:
                timeout = f"{name} took too long to decide. The duel has ended and they forfeit their gold."
                embed.add_field(name=f"Timed out!", value=timeout, inline=False)
                if current_player == challenger_id:
                    await self.bot.database.add_gold(challenged_id, gold_amount)
                    await self.bot.database.add_gold(challenger_id, -gold_amount)
                    self.bot.logger.info(f'Awarded {challenged_id} with gold')
                else: 
                    await self.bot.database.add_gold(challenger_id, gold_amount)
                    await self.bot.database.add_gold(challenged_id, -gold_amount)
                    self.bot.logger.info(f'Awarded {challenger_id} with gold')
                self.bot.state_manager.clear_active(challenger_id)
                self.bot.state_manager.clear_active(challenged_id)
                await message.edit(embed=embed)
                return

        winner, loser = (challenger_id, challenged_id) if challenged_hp <= 0 else (challenged_id, challenger_id)
        self.bot.logger.info(f'winner: {winner}, loser: {loser}')
        await self.bot.database.add_gold(winner, gold_amount)
        await self.bot.database.add_gold(loser, -gold_amount)
        if winner == challenger_id:
            name = player
            loser_name = opponent
        else:
            name = opponent
            loser_name = player
        self.bot.state_manager.clear_active(challenger_id)
        self.bot.state_manager.clear_active(challenged_id)
        victory = f"{name} slays {loser_name} with a 💥 {damage}!\nThey receive **{gold_amount * 2} gold**!"
        embed.add_field(name=f"{name} is victorious!", value=victory, inline=False)
        await message.edit(embed=embed)

    def calculate_damage(self, current_hp: int) -> int:
        """Calculate damage based on HP, using a modified version of the Dharok's effect."""
        if current_hp <= 0:
            return 0

        if current_hp == 100:
            max_hit = 25
        else:
            max_hit = 120 * (100 - current_hp) / 100

        max_hit = max(25, int(max_hit))
        damage = random.randint(1, max_hit)
        return damage


# And then we finally add the cog to the bot so that it can load, unload, reload and use it's content.
async def setup(bot) -> None:
    await bot.add_cog(Pvp(bot))
