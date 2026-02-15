import discord
from discord import app_commands, Interaction
from discord.ext import commands
from datetime import datetime, timedelta

from core.tavern.views import ShopView, RestView, CasinoMenuView
from core.tavern.mechanics import TavernMechanics

class Tavern(commands.Cog, name="tavern"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="shop", description="Visit the tavern shop to buy items.")
    async def shop(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        user_data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user_data): return
        if not await self.bot.check_is_active(interaction, user_id): return

        self.bot.state_manager.set_active(user_id, "shop")

        # Initial Embed Setup
        gold = user_data[6]
        level = user_data[4]
        
        potion_cost = TavernMechanics.calculate_potion_cost(level)
        curio_cost, curio_stock = TavernMechanics.get_curio_stock_info(user_data[23])

        embed = discord.Embed(
            title="Tavern Shop 🏪",
            description="Welcome to the shop! Here are the items you can buy:",
            color=0xFFCC00,
        )
        embed.set_thumbnail(url="https://i.imgur.com/81jN8tA.jpeg")
        embed.add_field(name="Your Gold 💰", value=f"{gold:,}", inline=False)
        embed.add_field(name="Potion 🧪 x1 / x5 / x10", 
                        value=f"Cost: {potion_cost} / {potion_cost * 5} / {potion_cost * 10} gold", 
                        inline=False)

        if curio_stock > 0:
            embed.add_field(name="Curious Curio 🎁",
                            value=f"Cost: **{curio_cost:,}** gold\nStock: **{curio_stock}**", inline=False)
        else:
            embed.add_field(name="Curious Curio 🎁",
                            value="No stock left. Refreshed on next /checkin!", inline=False)
        
        embed.add_field(name="The tavernkeeper", value=f"Hello traveler, the pickings are slim I'm afraid...", inline=False)

        view = ShopView(self.bot, user_id, user_data)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


    @app_commands.command(name="rest", description="Rest your weary body and mind.")
    async def rest(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user): return
        if not await self.bot.check_is_active(interaction, user_id): return

        current_hp, max_hp = user[11], user[12]
        
        if current_hp >= max_hp:
            return await interaction.response.send_message(
                embed=discord.Embed(title="The Tavern 🛏️", description="You are already fully rested.", color=0xFFCC00),
                ephemeral=True
            )

        # Cooldown Check
        last_rest = user[13]
        cooldown = timedelta(hours=2)
        on_cooldown = False
        remaining_str = ""

        if last_rest:
            try:
                diff = datetime.now() - datetime.fromisoformat(last_rest)
                if diff < cooldown:
                    on_cooldown = True
                    rem = cooldown - diff
                    remaining_str = f"**{rem.seconds // 3600}h {(rem.seconds // 60) % 60}m**"
            except: pass

        if not on_cooldown:
            # Free Rest
            await self.bot.database.users.update_hp(user_id, max_hp)
            await self.bot.database.users.update_timer(user_id, 'last_rest_time')
            
            embed = discord.Embed(
                title="The Tavern 🛏️",
                description=f"You have rested and regained your health! Current HP: **{max_hp}**.",
                color=0xFFCC00
            )
            embed.set_thumbnail(url="https://i.imgur.com/ZARftKJ.jpeg")
            await interaction.response.send_message(embed=embed)
        else:
            # Paid Rest Prompt
            cost = TavernMechanics.calculate_rest_cost(user[4])
            gold = user[6]
            
            embed = discord.Embed(
                title="The Tavern 🛏️",
                description=f"You need to wait {remaining_str} before resting for free again.",
                color=0xFFCC00
            )
            embed.set_image(url="https://i.imgur.com/Nv1JbrO.jpeg")
            
            if gold >= cost:
                self.bot.state_manager.set_active(user_id, "rest")
                embed.add_field(name="The Tavernkeeper", value=f"I have an extra room available for **{cost} gold**.")
                view = RestView(self.bot, user_id, cost, max_hp)
                await interaction.response.send_message(embed=embed, view=view)
                view.message = await interaction.original_response()
            else:
                embed.add_field(name="The Tavernkeeper", value=f"I have a room for **{cost} gold**, but you can't afford it.")
                await interaction.response.send_message(embed=embed, ephemeral=True)


    @app_commands.command(name="gamble", description="Gamble your gold in the tavern!")
    @app_commands.describe(amount="The amount of gold to bet.")
    async def gamble(self, interaction: Interaction, amount: int) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        user_data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user_data): return
        if not await self.bot.check_is_active(interaction, user_id): return
        
        if amount <= 0:
            return await interaction.response.send_message("Bet must be positive.", ephemeral=True)
        if amount > user_data[6]:
            return await interaction.response.send_message(f"Insufficient funds. You have **{user_data[6]:,}**.", ephemeral=True)

        self.bot.state_manager.set_active(user_id, "gamble")

        embed = discord.Embed(
            title="The Tavern Casino 🎲",
            description=f"Table Stake: **{amount:,} gold**.\nSelect a game:",
            color=0xFFD700
        )
        embed.set_thumbnail(url="https://i.imgur.com/D8HlsQX.jpeg")
        embed.add_field(name="🃏 Blackjack", value="Beat the dealer to 21. (2x Payout)", inline=True)
        embed.add_field(name="🎡 Roulette", value="Red/Black/Numbers. (2x-35x Payout)", inline=True)
        embed.add_field(name="🚀 Crash", value="Cash out before the crash! (1.0x - ???x)", inline=True)
        embed.add_field(name="🐎 Horse Racing", value="Pick the winner! (4x Payout)", inline=True)

        view = CasinoMenuView(self.bot, user_id, amount)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


    @app_commands.command(name="checkin", description="Daily check-in reward.")
    async def checkin(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user): return

        # Check Timer
        last_checkin = user[17]
        cooldown = timedelta(hours=18)
        
        if last_checkin:
            try:
                diff = datetime.now() - datetime.fromisoformat(last_checkin)
                if diff < cooldown:
                    rem = cooldown - diff
                    return await interaction.response.send_message(
                        f"Check-in available in **{rem.seconds // 3600}h {(rem.seconds // 60) % 60}m**.",
                        ephemeral=True
                    )
            except: pass

        # Reward
        await self.bot.database.users.update_timer(user_id, 'last_checkin_time')
        await self.bot.database.users.modify_currency(user_id, 'curios', 1)
        # Reset daily shop stock counter (stored in 'curios_purchased_today')
        # We set it to 0 by negating current value
        current_purchased = user[23]
        if current_purchased > 0:
            await self.bot.database.users.modify_currency(user_id, 'curios_purchased_today', -current_purchased)

        await interaction.response.send_message(
            "✅ Check-in complete! You received a **Curious Curio**.\nTavern Shop stock has been refreshed.",
            ephemeral=True
        )

async def setup(bot) -> None:
    await bot.add_cog(Tavern(bot))