import discord
from discord import ui, ButtonStyle, Interaction

class DoorToggleView(ui.View):
    def __init__(self, bot, user_id: str, current_status: bool):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.status = current_status
        self.update_button()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    def update_button(self):
        self.clear_items()
        
        lbl = "Disable Boss Doors" if self.status else "Enable Boss Doors"
        style = ButtonStyle.danger if self.status else ButtonStyle.success
        
        btn = ui.Button(label=lbl, style=style, emoji="🚪")
        btn.callback = self.toggle_doors
        self.add_item(btn)

    def build_embed(self) -> discord.Embed:
        state_str = "🟢 ENABLED" if self.status else "🔴 DISABLED"
        desc = (
            "When **Enabled**, your keys and fragments will resonate, giving you a chance to encounter Boss Doors during regular `/combat`.\n\n"
            "When **Disabled**, you will bypass all boss encounters and only fight standard monsters (Useful for Slayer tasks or standard grinding)."
        )
        
        embed = discord.Embed(
            title="Boss Door Settings", 
            description=f"Current Status: **{state_str}**\n\n{desc}", 
            color=discord.Color.blue()
        )
        return embed

    async def toggle_doors(self, interaction: Interaction):
        # Flip state
        self.status = not self.status
        
        # Save to DB
        await self.bot.database.users.toggle_doors(self.user_id, self.status)
        
        # Update UI
        self.update_button()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)