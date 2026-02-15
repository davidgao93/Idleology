import discord
from discord import ui, ButtonStyle, Interaction
from core.curios.logic import CurioManager

class CurioView(ui.View):
    def __init__(self, bot, user_id: str, server_id: str, curio_count: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.curio_count = curio_count
        
        self.update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try:
            # Disable buttons
            for child in self.children:
                child.disabled = True
            await self.message.edit(view=self)
        except: pass

    def update_buttons(self):
        # Buttons: Open 1, Open 5, Open 10, Close
        # Indices: 0, 1, 2, 3
        self.children[0].disabled = self.curio_count < 1
        self.children[1].disabled = self.curio_count < 5
        self.children[2].disabled = self.curio_count < 10
        
        self.children[0].label = "🎁 Open 1"
        self.children[1].label = "🎁 Open 5"
        self.children[2].label = "🎁 Open 10"

    async def process_open(self, interaction: Interaction, amount: int):
        w_count = await self.bot.database.equipment.get_count(self.user_id, 'weapon')
        a_count = await self.bot.database.equipment.get_count(self.user_id, 'accessory') # Note: 'accessory' not 'accessories' based on type map
        ar_count = await self.bot.database.equipment.get_count(self.user_id, 'armor')
        g_count = await self.bot.database.equipment.get_count(self.user_id, 'glove')
        b_count = await self.bot.database.equipment.get_count(self.user_id, 'boot')
        h_count = await self.bot.database.equipment.get_count(self.user_id, 'helmet')

        if (w_count > 60 or a_count > 60 or 
            ar_count > 60 or g_count > 60 or
            b_count > 60 or h_count > 60): # Simplified check
            return await interaction.response.send_message("Inventory full! Clear some space.", ephemeral=True)

        await interaction.response.defer()

        # 2. Logic
        result = await CurioManager.process_open(self.bot, self.user_id, self.server_id, amount)
        self.curio_count -= amount
        
        # 3. Build Embed
        embed = discord.Embed(title=f"Curios Opened: {amount}", color=discord.Color.green())
        
        summary_text = "\n".join([f"**{k}** x{v}" for k,v in result['summary'].items()])
        embed.description = summary_text
        
        if result['loot_logs']:
            # Show up to 5 items to prevent spam
            items_preview = "\n".join(result['loot_logs'][:5])
            if len(result['loot_logs']) > 5:
                items_preview += f"\n...and {len(result['loot_logs'])-5} more."
            embed.add_field(name="Gear Details", value=items_preview, inline=False)

        # Image Logic
        # If single item type dominates or single open, try to get image
        if amount == 1:
            item_name = list(result['summary'].keys())[0]
            url = CurioManager.get_image_url(item_name)
            if url: embed.set_image(url=url)
        else:
            embed.set_image(url="https://i.imgur.com/wKyTFzh.jpg") # Generic pile of loot

        embed.set_footer(text=f"Remaining Curios: {self.curio_count}")

        # 4. Update UI
        self.update_buttons()
        if self.curio_count == 0:
            embed.add_field(name="Empty!", value="You have no curios left.", inline=False)
            await interaction.edit_original_response(embed=embed, view=None)
            self.bot.state_manager.clear_active(self.user_id)
            self.stop()
        else:
            await interaction.edit_original_response(embed=embed, view=self)

    @ui.button(style=ButtonStyle.primary)
    async def open_one(self, interaction: Interaction, button: ui.Button):
        await self.process_open(interaction, 1)

    @ui.button(style=ButtonStyle.primary)
    async def open_five(self, interaction: Interaction, button: ui.Button):
        await self.process_open(interaction, 5)

    @ui.button(style=ButtonStyle.primary)
    async def open_ten(self, interaction: Interaction, button: ui.Button):
        await self.process_open(interaction, 10)

    @ui.button(label="Close", style=ButtonStyle.danger)
    async def close(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()