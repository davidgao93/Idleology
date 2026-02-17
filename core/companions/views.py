# core/companions/views.py

import discord
from discord import ui, ButtonStyle, Interaction, SelectOption
from core.models import Companion
from core.companions.mechanics import CompanionMechanics
from core.companions.logic import CompanionLogic

class CompanionListView(ui.View):
    def __init__(self, bot, user_id: str, companions: list[Companion]):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.companions = companions
        
        # Pagination
        self.current_page = 0
        self.items_per_page = 5
        self.total_pages = (len(companions) + self.items_per_page - 1) // self.items_per_page
        
        self.update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try: await self.message.edit(view=None)
        except: pass

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    def update_buttons(self):
        self.clear_items()
        
        # 1. Companion Select Buttons
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        batch = self.companions[start:end]
        
        for i, comp in enumerate(batch):
            status = "🟢" if comp.is_active else "⚪"
            lbl = f"{status} {comp.name} (Lv.{comp.level})"
            btn = ui.Button(label=lbl, style=ButtonStyle.secondary, row=0)
            btn.callback = lambda i, c=comp: self.select_companion(i, c)
            self.add_item(btn)

        # 2. Navigation
        if self.total_pages > 1:
            prev_btn = ui.Button(label="Prev", disabled=(self.current_page == 0), row=1)
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)
            
            next_btn = ui.Button(label="Next", disabled=(self.current_page == self.total_pages - 1), row=1)
            next_btn.callback = self.next_page
            self.add_item(next_btn)

        # 3. Actions
        collect_btn = ui.Button(label="Collect Loot", style=ButtonStyle.success, emoji="💰", row=1)
        collect_btn.callback = self.collect_loot
        self.add_item(collect_btn)
        
        close_btn = ui.Button(label="Close", style=ButtonStyle.danger, row=1)
        close_btn.callback = self.close_view
        self.add_item(close_btn)

    def get_embed(self):
        embed = discord.Embed(title="🐾 Companions", color=discord.Color.blue())
        embed.set_footer(text=f"Page {self.current_page + 1}/{max(1, self.total_pages)} | Cap: {len(self.companions)}/20")
        
        if not self.companions:
            embed.description = "You have no companions. Fight monsters to capture one!"
            return embed

        active_count = sum(1 for c in self.companions if c.is_active)
        desc = f"**Active:** {active_count}/3\n\n"
        
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        
        for comp in self.companions[start:end]:
            status = "**[Active]**" if comp.is_active else ""
            desc += f"{status} **{comp.name}** ({comp.species})\n"
            desc += f"Lv.{comp.level} | {comp.description}\n\n"
            
        embed.description = desc
        return embed

    # --- Callbacks ---
    async def prev_page(self, interaction: Interaction):
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def next_page(self, interaction: Interaction):
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def select_companion(self, interaction: Interaction, comp: Companion):
        view = CompanionDetailView(self.bot, self.user_id, comp, self)
        await interaction.response.edit_message(embed=view.get_embed(), view=view)

    async def collect_loot(self, interaction: Interaction):
        # Delegate to Logic
        result_msg = await CompanionLogic.collect_passive_rewards(
            self.bot, 
            self.user_id, 
            str(interaction.guild.id)
        )
        
        await interaction.response.send_message(result_msg, ephemeral=True)

class CompanionDetailView(ui.View):
    def __init__(self, bot, user_id, companion, parent_view):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.comp = companion
        self.parent = parent_view
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        
        # Toggle Active
        lbl = "Set Inactive" if self.comp.is_active else "Set Active"
        style = ButtonStyle.secondary if self.comp.is_active else ButtonStyle.success
        btn_active = ui.Button(label=lbl, style=style, row=0)
        btn_active.callback = self.toggle_active
        self.add_item(btn_active)

        # Rename
        btn_rename = ui.Button(label="Rename", style=ButtonStyle.primary, row=0)
        btn_rename.callback = self.rename_modal
        self.add_item(btn_rename)

        # Reroll
        btn_reroll = ui.Button(label="Reroll Passive", style=ButtonStyle.primary, emoji="🎲", row=1)
        btn_reroll.callback = self.reroll_passive
        self.add_item(btn_reroll)

        # Release
        btn_release = ui.Button(label="Release", style=ButtonStyle.danger, row=1)
        btn_release.callback = self.release_confirm
        self.add_item(btn_release)

        # Back
        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=2)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    def get_embed(self):
        embed = discord.Embed(title=f"{self.comp.name}", color=discord.Color.gold())
        embed.set_thumbnail(url=self.comp.image_url)
        
        status = "Active 🟢" if self.comp.is_active else "Inactive ⚪"
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Level", value=f"{self.comp.level}", inline=True)
        
        next_xp = CompanionMechanics.calculate_next_level_xp(self.comp.level)
        embed.add_field(name="EXP", value=f"{self.comp.exp}/{next_xp}", inline=True)
        
        embed.add_field(name="Passive", value=f"T{self.comp.passive_tier} **{self.comp.description}**", inline=False)
        embed.set_footer(text=f"Species: {self.comp.species}")
        return embed

    async def toggle_active(self, interaction: Interaction):
        new_state = not self.comp.is_active
        success = await self.bot.database.companions.set_active(self.user_id, self.comp.id, new_state)
        
        if not success:
            return await interaction.response.send_message("You already have 3 active companions!", ephemeral=True)
        
        if new_state:
            await self.bot.database.users.initialize_companion_timer(self.user_id)
        
        self.comp.is_active = new_state
        self.update_buttons()
        
        # Update parent list state locally
        for c in self.parent.companions:
            if c.id == self.comp.id: c.is_active = new_state
            
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def rename_modal(self, interaction: Interaction):
        modal = RenameModal(self)
        await interaction.response.send_modal(modal)

    async def reroll_passive(self, interaction: Interaction):
        # 1. Check Rune Balance
        runes = await self.bot.database.users.get_currency(self.user_id, 'partnership_runes')
        if runes < 1:
            return await interaction.response.send_message(
                "You need a **Rune of Partnership** to reroll passives.", 
                ephemeral=True
            )

        # 2. Defer interaction (DB writes involved)
        await interaction.response.defer()

        # 3. Consume Rune
        await self.bot.database.users.modify_currency(self.user_id, 'partnership_runes', -1)

        # 4. Calculate New Passive via Mechanics
        # Logic: Rerolls Type, 10% chance to Upgrade Tier, 90% chance to keep Tier
        old_tier = self.comp.passive_tier
        new_type, new_tier, upgraded = CompanionMechanics.reroll_passive(old_tier)

        # 5. Update Database
        await self.bot.database.companions.update_passive(self.comp.id, new_type, new_tier)

        # 6. Update Local Object (to reflect changes in UI immediately)
        self.comp.passive_type = new_type
        self.comp.passive_tier = new_tier

        # 7. Update UI & Send Feedback
        msg = f"🎲 Passive rerolled to **{self.comp.description}**!"
        if upgraded:
            msg += f"\n🌟 **TIER UPGRADE!** (T{old_tier} ➡️ T{new_tier})"
        
        await interaction.edit_original_response(embed=self.get_embed(), view=self)
        await interaction.followup.send(msg, ephemeral=True)

    async def release_confirm(self, interaction: Interaction):
        await self.bot.database.companions.delete_companion(self.comp.id, self.user_id)
        
        # Remove from parent list
        self.parent.companions = [c for c in self.parent.companions if c.id != self.comp.id]
        self.parent.update_buttons()
        
        await interaction.response.edit_message(embed=self.parent.get_embed(), view=self.parent)

    async def go_back(self, interaction: Interaction):
        await interaction.response.edit_message(embed=self.parent.get_embed(), view=self.parent)

class RenameModal(ui.Modal, title="Rename Companion"):
    name = ui.TextInput(label="New Name", max_length=20)

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        new_name = self.name.value
        await self.parent_view.bot.database.companions.rename(self.parent_view.comp.id, new_name)
        self.parent_view.comp.name = new_name
        
        await interaction.response.edit_message(embed=self.parent_view.get_embed(), view=self.parent_view)