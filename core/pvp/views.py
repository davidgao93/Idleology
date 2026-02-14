import discord
import random
import asyncio
from discord import Interaction, ButtonStyle
from discord.ui import View, Button
from core.pvp.engine import PvPEngine

class ChallengeView(View):
    """View for accepting/declining a duel request."""
    def __init__(self, bot, challenger_id, target_id, amount):
        super().__init__(timeout=60)
        self.bot = bot
        self.challenger_id = str(challenger_id)
        self.target_id = str(target_id)
        self.amount = amount
        self.accepted = False

    async def interaction_check(self, interaction: Interaction) -> bool:
        if str(interaction.user.id) == self.target_id:
            return True
        if str(interaction.user.id) == self.challenger_id:
            await interaction.response.send_message("You cannot accept your own challenge. Cancel it if you changed your mind.", ephemeral=True)
            return False
        return False

    async def on_timeout(self):
        if not self.accepted:
            self.bot.state_manager.clear_active(self.challenger_id)
            # Target wasn't active yet, so no need to clear
            try: await self.message.edit(content="Challenge timed out.", view=None)
            except: pass

    @discord.ui.button(label="Accept", style=ButtonStyle.success)
    async def accept(self, interaction: Interaction, button: Button):
        # Check target state
        if not await self.bot.check_is_active(interaction, self.target_id):
            return # check_is_active sends the error message

        self.accepted = True
        self.bot.state_manager.set_active(self.target_id, "duel")
        
        # Start Duel View
        duel_view = DuelView(self.bot, self.challenger_id, self.target_id, self.amount)
        await duel_view.start_match(interaction)
        self.stop()

    @discord.ui.button(label="Decline", style=ButtonStyle.danger)
    async def decline(self, interaction: Interaction, button: Button):
        self.bot.state_manager.clear_active(self.challenger_id)
        await interaction.response.edit_message(content="Challenge declined.", embed=None, view=None)
        self.stop()


class DuelView(View):
    """View handling the actual turn-based combat."""
    def __init__(self, bot, p1_id, p2_id, amount):
        super().__init__(timeout=180)
        self.bot = bot
        self.p1_id = p1_id # Challenger
        self.p2_id = p2_id # Target
        self.amount = amount
        
        # Game State
        self.hp = {p1_id: 100, p2_id: 100}
        self.names = {p1_id: "Player 1", p2_id: "Player 2"} # Placeholder until fetch
        self.current_turn = None # ID of current player
        self.logs = "Duel started!"

    async def start_match(self, interaction: Interaction):
        # Fetch Names
        try:
            u1 = await self.bot.fetch_user(int(self.p1_id))
            u2 = await self.bot.fetch_user(int(self.p2_id))
            self.names[self.p1_id] = u1.display_name
            self.names[self.p2_id] = u2.display_name
        except: pass

        # Coin Toss
        self.current_turn = random.choice([self.p1_id, self.p2_id])
        
        embed = self._build_embed()
        await interaction.response.edit_message(content=None, embed=embed, view=self)

    def _build_embed(self):
        p1_name = self.names[self.p1_id]
        p2_name = self.names[self.p2_id]
        
        # Highlight current turn
        p1_fmt = f"**{p1_name}**" if self.current_turn == self.p1_id else p1_name
        p2_fmt = f"**{p2_name}**" if self.current_turn == self.p2_id else p2_name

        embed = discord.Embed(title=f"⚔️ Duel for {self.amount:,} Gold", color=discord.Color.gold())
        embed.add_field(name=f"{p1_fmt}", value=f"❤️ {self.hp[self.p1_id]} HP", inline=True)
        embed.add_field(name=f"{p2_fmt}", value=f"❤️ {self.hp[self.p2_id]} HP", inline=True)
        embed.add_field(name="Log", value=self.logs, inline=False)
        embed.set_footer(text=f"Turn: {self.names[self.current_turn]}")
        return embed

    async def interaction_check(self, interaction: Interaction) -> bool:
        if str(interaction.user.id) != self.current_turn:
            await interaction.response.send_message("It is not your turn!", ephemeral=True)
            return False
        return True

    async def process_turn(self, interaction: Interaction, action: str):
        attacker = self.current_turn
        defender = self.p1_id if attacker == self.p2_id else self.p2_id
        
        if action == "attack":
            # 30% Miss Chance
            if random.randint(1, 100) <= 30:
                self.logs = f"💨 **{self.names[attacker]}** missed their attack!"
            else:
                dmg = PvPEngine.calculate_damage(self.hp[attacker])
                self.hp[defender] -= dmg
                self.logs = f"💥 **{self.names[attacker]}** hit for **{dmg}** damage!"
        
        elif action == "heal":
            amt = PvPEngine.calculate_heal()
            old_hp = self.hp[attacker]
            self.hp[attacker] = min(100, self.hp[attacker] + amt)
            healed = self.hp[attacker] - old_hp
            self.logs = f"💖 **{self.names[attacker]}** healed for **{healed}** HP."

        # Check Win Condition
        if self.hp[defender] <= 0:
            await self.end_match(interaction, winner=attacker, loser=defender)
        else:
            # Swap Turn
            self.current_turn = defender
            await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def end_match(self, interaction: Interaction, winner: str, loser: str):
        # Database Transaction
        await self.bot.database.users.modify_gold(winner, self.amount)
        await self.bot.database.users.modify_gold(loser, -self.amount)
        
        embed = discord.Embed(title="🏆 Duel Over!", color=discord.Color.green())
        embed.description = f"**{self.names[winner]}** has defeated **{self.names[loser]}**!\n\nWinner receives: **{self.amount * 2:,} gold** (Pot)."
        
        # Clear states
        self.bot.state_manager.clear_active(self.p1_id)
        self.bot.state_manager.clear_active(self.p2_id)
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def on_timeout(self):
        # Timeout Penalty: Current turn player loses
        loser = self.current_turn
        winner = self.p1_id if loser == self.p2_id else self.p2_id
        
        # Execute loss via DB
        await self.bot.database.users.modify_gold(winner, self.amount)
        await self.bot.database.users.modify_gold(loser, -self.amount)
        
        self.bot.state_manager.clear_active(self.p1_id)
        self.bot.state_manager.clear_active(self.p2_id)
        
        try:
            embed = discord.Embed(title="⏰ Timed Out", description=f"**{self.names[loser]}** took too long and forfeited.\n{self.names[winner]} wins the pot.", color=discord.Color.red())
            await self.message.edit(embed=embed, view=None)
        except: pass

    @discord.ui.button(label="Attack", style=ButtonStyle.danger, emoji="⚔️")
    async def btn_attack(self, interaction: Interaction, button: Button):
        await self.process_turn(interaction, "attack")

    @discord.ui.button(label="Heal", style=ButtonStyle.success, emoji="💖")
    async def btn_heal(self, interaction: Interaction, button: Button):
        await self.process_turn(interaction, "heal")