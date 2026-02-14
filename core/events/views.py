import discord
import random
from discord import Interaction, ButtonStyle
from discord.ui import View, Button

class RandomEventView(View):
    def __init__(self, bot, event_type: str):
        super().__init__(timeout=600) # 10 minutes
        self.bot = bot
        self.event_type = event_type
        self.claimed_users = set()
        
        # Configure button based on type
        self.setup_button()

    def setup_button(self):
        labels = {
            "leprechaun": ("Grab a Curio", "☘️", ButtonStyle.success),
            "meteorite": ("Mine Meteor", "⛏️", ButtonStyle.primary),
            "dryad": ("Chop Dryad", "🪓", ButtonStyle.primary),
            "high_tide": ("Fish", "🎣", ButtonStyle.primary)
        }
        
        if self.event_type in labels:
            lbl, emoji, style = labels[self.event_type]
            btn = Button(label=lbl, emoji=emoji, style=style, custom_id="claim_event")
            btn.callback = self.claim_callback
            self.add_item(btn)

    async def claim_callback(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        if user_id in self.claimed_users:
            await interaction.response.send_message("You have already claimed this event!", ephemeral=True)
            return

        # Check registration
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        # Logic Mapping
        reward_msg = ""
        
        if self.event_type == "leprechaun":
            await self.bot.database.users.modify_currency(user_id, 'curios', 1)
            reward_msg = f"grabbed a **curio**!"

        elif self.event_type == "meteorite":
            data = await self.bot.database.skills.get_data(user_id, server_id, 'mining')
            if not data:
                return await interaction.response.send_message("You need a Pickaxe (Mining) to participate!", ephemeral=True)
            
            # Use Skills Cog logic to calculate yield based on tier
            skills_cog = self.bot.get_cog("skills")
            resources = await skills_cog.gather_mining_resources(data[2]) # data[2] is tier
            await self.bot.database.skills.update_batch(user_id, server_id, 'mining', resources)
            reward_msg = "mined the meteor!"

        elif self.event_type == "dryad":
            data = await self.bot.database.skills.get_data(user_id, server_id, 'woodcutting')
            if not data:
                return await interaction.response.send_message("You need an Axe (Woodcutting) to participate!", ephemeral=True)
            
            skills_cog = self.bot.get_cog("skills")
            resources = await skills_cog.gather_woodcutting_resources(data[2])
            await self.bot.database.skills.update_batch(user_id, server_id, 'woodcutting', resources)
            reward_msg = "claimed the Dryad's blessing!"

        elif self.event_type == "high_tide":
            data = await self.bot.database.skills.get_data(user_id, server_id, 'fishing')
            if not data:
                return await interaction.response.send_message("You need a Rod (Fishing) to participate!", ephemeral=True)
            
            skills_cog = self.bot.get_cog("skills")
            resources = await skills_cog.gather_fishing_resources(data[2])
            await self.bot.database.skills.update_batch(user_id, server_id, 'fishing', resources)
            reward_msg = "caught fish from the High Tide!"

        # Success Handling
        self.claimed_users.add(user_id)
        await interaction.response.send_message(f"Event claimed! You {reward_msg}", ephemeral=True)
        
        # Update original message embed with "Claimed by: Name"
        try:
            embed = interaction.message.embeds[0]
            
            # Find or Create "Recent Claims" field
            field_found = False
            new_val = f"**{existing_user[3]}** {reward_msg}"
            
            # Simple list management for the embed field
            for i, field in enumerate(embed.fields):
                if field.name == "Recent Claims":
                    # Keep only last 5 lines to prevent embed overflow
                    current_lines = field.value.split('\n')
                    if len(current_lines) >= 5: current_lines.pop(0)
                    current_lines.append(new_val)
                    
                    embed.set_field_at(i, name="Recent Claims", value="\n".join(current_lines), inline=False)
                    field_found = True
                    break
            
            if not field_found:
                embed.add_field(name="Recent Claims", value=new_val, inline=False)
            
            await interaction.message.edit(embed=embed)
        except Exception as e:
            self.bot.logger.error(f"Failed to update event embed: {e}")

    async def on_timeout(self):
        # Disable button when time runs out
        for item in self.children:
            item.disabled = True
        
        # Attempt to edit message to show expired
        if hasattr(self, 'message') and self.message:
            try:
                await self.message.edit(view=self)
            except: pass