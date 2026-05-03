import discord
from discord import ui, ButtonStyle, Interaction

from core.images import TAVERN_CASINO
from core.tavern.mechanics import TavernMechanics
# Import minigames directly to handle transitions without Cog
from core.minigames.views import BlackjackView, RouletteView, CrashView, HorseRaceView

class ShopView(ui.View):
    def __init__(self, bot, user_id: str, user_data: tuple):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.gold = user_data[6]
        self.potions = user_data[16]
        self.level = user_data[4]
        self.potion_cost = TavernMechanics.calculate_potion_cost(self.level)
        self.message = None
        self.update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        for child in self.children:
            child.disabled = True
        try:
            embed = self.message.embeds[0]
            for i, field in enumerate(embed.fields):
                if "tavernkeeper" in field.name.lower():
                    embed.set_field_at(i, name="The tavernkeeper", value="*Zzz...* (The shop has closed)", inline=False)
                    break
            await self.message.edit(embed=embed, view=self)
        except Exception:
            pass

    def _topup_qty(self) -> int:
        return max(0, 20 - self.potions)

    def update_buttons(self):
        topup_qty = self._topup_qty()
        topup_cost = self.potion_cost * topup_qty
        self.children[0].disabled = self.gold < self.potion_cost or self.potions >= 20
        self.children[1].disabled = self.gold < self.potion_cost * 5 or self.potions > 15
        self.children[2].disabled = topup_qty == 0 or self.gold < topup_cost
        self.children[2].label = f"🧪 Top Up ({topup_qty})"

    async def refresh_ui(self, interaction: Interaction, msg: str):
        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="Your Gold 💰", value=f"{self.gold:,}", inline=False)
        topup_qty = self._topup_qty()
        embed.set_field_at(
            1,
            name="Potion 🧪",
            value=(
                f"x1: **{self.potion_cost:,}** gold\n"
                f"x5: **{self.potion_cost * 5:,}** gold\n"
                f"Top Up ({topup_qty}): **{self.potion_cost * topup_qty:,}** gold"
            ),
            inline=False,
        )
        embed.set_field_at(2, name="The tavernkeeper", value=msg, inline=False)
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def process_potion_buy(self, interaction: Interaction, qty: int):
        cost = self.potion_cost * qty
        await self.bot.database.users.modify_gold(self.user_id, -cost)
        await self.bot.database.users.modify_stat(self.user_id, 'potions', qty)
        self.gold -= cost
        self.potions += qty
        msg = f"Here are your **{qty}** potions. Stay safe out there."
        await self.refresh_ui(interaction, msg)

    @ui.button(label="🧪 x1", style=ButtonStyle.primary)
    async def buy_one(self, interaction: Interaction, button: ui.Button):
        await self.process_potion_buy(interaction, 1)

    @ui.button(label="🧪 x5", style=ButtonStyle.primary)
    async def buy_five(self, interaction: Interaction, button: ui.Button):
        await self.process_potion_buy(interaction, 5)

    @ui.button(label="🧪 Top Up", style=ButtonStyle.primary)
    async def top_up(self, interaction: Interaction, button: ui.Button):
        qty = self._topup_qty()
        if qty == 0:
            return await interaction.response.send_message("Your potions are already full.", ephemeral=True)
        await self.process_potion_buy(interaction, qty)

    @ui.button(label="Leave", style=ButtonStyle.danger)
    async def leave(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()


class RestView(ui.View):
    def __init__(self, bot, user_id, cost, max_hp):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.cost = cost
        self.max_hp = max_hp

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id
    
    
    @ui.button(label="Pay for a room?", style=ButtonStyle.success, emoji="🛏️")
    async def confirm_rest(self, interaction: Interaction, button: ui.Button):
        # 1. Deduct Gold
        await self.bot.database.users.modify_gold(self.user_id, -self.cost)
        # 2. Heal
        await self.bot.database.users.update_hp(self.user_id, self.max_hp)
        
        embed = interaction.message.embeds[0]
        embed.description = f"You paid **{self.cost}** gold.\nYou have rested and regained your health! Current HP: **{self.max_hp}**."
        embed.clear_fields() # Remove the payment prompt field
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    @ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(content="Rest cancelled.", embed=None, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()


class CasinoMenuView(ui.View):
    def __init__(self, bot, user_id, bet_amount):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.bet_amount = bet_amount

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try: await self.message.delete()
        except: pass

    async def _check_funds(self, interaction: Interaction):
        # Re-check funds before starting game
        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < self.bet_amount:
            await interaction.response.send_message("Insufficient funds!", ephemeral=True)
            return False
        return True

    @ui.button(label="Blackjack", emoji="🃏", style=ButtonStyle.primary, row=0)
    async def blackjack(self, interaction: Interaction, button: ui.Button):
        if not await self._check_funds(interaction): return
        
        view = BlackjackView(self.bot, self.user_id, self.bet_amount, interaction)
        await interaction.response.edit_message(content=f"Starting **Blackjack**...", embed=None, view=None)
        await view.start_game()

    @ui.button(label="Roulette", emoji="🎡", style=ButtonStyle.danger, row=0)
    async def roulette(self, interaction: Interaction, button: ui.Button):
        if not await self._check_funds(interaction): return
        
        embed = discord.Embed(title="🎡 Roulette Table", description=f"Betting **{self.bet_amount:,} gold**.\nChoose your wager:", color=discord.Color.red())
        embed.set_thumbnail(url=TAVERN_CASINO)
        
        view = RouletteView(self.bot, self.user_id, self.bet_amount, interaction)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Crash", emoji="🚀", style=ButtonStyle.success, row=1)
    async def crash(self, interaction: Interaction, button: ui.Button):
        if not await self._check_funds(interaction): return
        
        view = CrashView(self.bot, self.user_id, self.bet_amount, interaction)
        embed = discord.Embed(
            title="🚀 Preparing Launch...", 
            description=f"Fueling up for a bet of **{self.bet_amount:,} gold**.",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)
        await view.start_game()

    @ui.button(label="Horse Racing", emoji="🐎", style=ButtonStyle.secondary, row=1)
    async def horse(self, interaction: Interaction, button: ui.Button):
        if not await self._check_funds(interaction): return
        
        view = HorseRaceView(self.bot, self.user_id, self.bet_amount, interaction)
        
        embed = discord.Embed(
            title="🐎 Horse Racing", 
            description=f"Betting **{self.bet_amount:,} gold**.\nPick your champion! (4x Payout)", 
            color=discord.Color.green()
        )
        embed.add_field(name="1. Thunder Hoof 🐎", value="Balanced speed.", inline=True)
        embed.add_field(name="2. Lightning Bolt 🦄", value="High risk, high speed.", inline=True)
        embed.add_field(name="3. Old Reliable 🦓", value="Consistent pace.", inline=True)
        embed.add_field(name="4. Dark Horse 🐫", value="Unpredictable.", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Cancel", emoji="❌", style=ButtonStyle.gray, row=2)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(content="Gambling cancelled.", embed=None, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()