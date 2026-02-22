import discord
from discord import ui, ButtonStyle, Interaction
from core.combat import engine

class LowHealthWarningView(ui.View):
    def __init__(self, bot, user_id, server_id, existing_user, player, clean_stats, continue_callback):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.existing_user = existing_user
        self.player = player
        self.clean_stats = clean_stats
        self.continue_callback = continue_callback # The function to call to actually start combat
        
        self.update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try: await self.message.delete()
        except: pass

    def update_buttons(self):
        self.clear_items()
        
        # Potion Button
        btn_heal = ui.Button(label=f"Drink Potion ({self.player.potions})", style=ButtonStyle.success, emoji="🧪", disabled=(self.player.potions <= 0))
        btn_heal.callback = self.heal
        self.add_item(btn_heal)
        
        # Fight Button (Changes color if safe)
        is_safe = self.player.current_hp >= (self.player.max_hp * 0.25)
        btn_fight = ui.Button(label="Fight" if is_safe else "Fight Anyway", style=ButtonStyle.primary if is_safe else ButtonStyle.danger, emoji="⚔️")
        btn_fight.callback = self.fight
        self.add_item(btn_fight)
        
        # Flee Button
        btn_flee = ui.Button(label="Flee", style=ButtonStyle.secondary)
        btn_flee.callback = self.flee
        self.add_item(btn_flee)

    def build_embed(self) -> discord.Embed:
        is_safe = self.player.current_hp >= (self.player.max_hp * 0.25)
        color = discord.Color.orange() if is_safe else discord.Color.red()
        
        embed = discord.Embed(title="⚠️ Warning: Low Health", color=color)
        embed.description = f"You are about to enter combat with **{self.player.current_hp}/{self.player.max_hp} HP**.\nDeath results in a 10% XP penalty."
        return embed

    async def heal(self, interaction: Interaction):
        msg = engine.process_heal(self.player)
        await self.bot.database.users.update_from_player_object(self.player)
        
        self.update_buttons()
        await interaction.response.edit_message(content=f"*{msg}*", embed=self.build_embed(), view=self)

    async def fight(self, interaction: Interaction):
        # We MUST defer here because generating the monster/boss can take a second
        await interaction.response.defer()
        
        # We pass control back to the Cog to run the rest of the combat logic
        await self.continue_callback(interaction, self.user_id, self.server_id, self.existing_user, self.player, self.clean_stats)
        self.stop()

    async def flee(self, interaction: Interaction):
        await interaction.response.edit_message(content="You back away from the danger. Live to fight another day.", embed=None, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()