# core/companions/views.py

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.base_view import BaseView
from core.companions.engram_view import BalancedEngramView
from core.images import COMPANIONS_HUB, COMPANIONS_FUSION
from core.companions.logic import CompanionLogic
from core.companions.mechanics import CompanionMechanics
from core.models import Companion


class RerollConfirmView(BaseView):
    def __init__(self, bot, user_id, companion, runes_owned, origin_view):
        super().__init__(bot, user_id)
        self.bot = bot
        self.user_id = user_id
        self.comp = companion
        self.runes_owned = runes_owned
        self.origin_view = origin_view  # The Detail View
        self._processing = False

    @ui.button(label="Confirm Reroll", style=ButtonStyle.success, emoji="🎲")
    async def confirm(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        # Double check funds just in case
        runes = await self.bot.database.users.get_currency(
            self.user_id, "partnership_runes"
        )
        if runes < 1:
            self._processing = False
            return await interaction.response.send_message(
                "You ran out of runes!", ephemeral=True
            )

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        # 1. Deduct
        await self.bot.database.users.modify_currency(
            self.user_id, "partnership_runes", -1
        )

        # 2. Logic
        old_tier = self.comp.passive_tier
        old_type = self.comp.passive_type

        # Pass current type to ensure change
        new_type, new_tier, upgraded = CompanionMechanics.reroll_passive(
            old_tier, old_type
        )

        # 3. Update DB
        await self.bot.database.companions.update_passive(
            self.comp.id, new_type, new_tier
        )

        # 4. Update Local Object
        self.comp.passive_type = new_type
        self.comp.passive_tier = new_tier

        # 5. Return to Detail View
        embed = self.origin_view.get_embed()
        embed.color = discord.Color.green()
        result = f"🎲 **Reroll Complete!**\nPrevious: T{old_tier} {old_type.upper()}\n**New:** T{new_tier} **{new_type.upper()}**"
        if upgraded:
            result += "\n🌟 **TIER UPGRADE!**"
        embed.description = (embed.description or "") + f"\n\n{result}"

        await interaction.edit_original_response(
            content=None, embed=embed, view=self.origin_view
        )
        self.stop()

    @ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(
            content=None, embed=self.origin_view.get_embed(), view=self.origin_view
        )
        self.stop()


class CompanionListView(BaseView):
    def __init__(self, bot, user_id: str, companions: list[Companion]):
        super().__init__(bot, user_id)
        self.bot = bot
        self.user_id = user_id
        self.companions = companions
        self.update_buttons()

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    def update_buttons(self):
        self.clear_items()

        # Dropdown to select any companion (row 0)
        if self.companions:
            options = []
            for comp in self.companions:
                status = "🟢" if comp.is_active else "⚪"
                label = f"{status} {comp.name} (Lv.{comp.level})"
                balanced_str = (
                    f" | {comp.balanced_description}"
                    if comp.balanced_passive != "none"
                    else ""
                )
                desc = f"T{comp.passive_tier} {comp.description}{balanced_str}"
                options.append(
                    SelectOption(
                        label=label[:100],
                        description=desc[:100],
                        value=str(comp.id),
                    )
                )
            select = ui.Select(
                placeholder="Select a companion to view details...",
                options=options,
                row=0,
            )
            select.callback = self._on_select
            self.add_item(select)

        # Action buttons (row 1)
        collect_btn = ui.Button(
            label="Collect", style=ButtonStyle.success, emoji="💰", row=1
        )
        collect_btn.callback = self.collect_loot
        self.add_item(collect_btn)

        fusion_btn = ui.Button(
            label="Fusion", style=ButtonStyle.primary, emoji="🧬", row=1
        )
        fusion_btn.callback = self.open_fusion
        self.add_item(fusion_btn)

        close_btn = ui.Button(label="Close", style=ButtonStyle.danger, row=1)
        close_btn.callback = self.close_view
        self.add_item(close_btn)

    def get_embed(self):
        embed = discord.Embed(title="🐾 Companions", color=discord.Color.blue())
        embed.set_thumbnail(url=COMPANIONS_HUB)
        embed.set_footer(text=f"Roster: {len(self.companions)}/20")

        if not self.companions:
            embed.description = "You have no companions. Fight monsters to capture one!"
            return embed

        active = [c for c in self.companions if c.is_active]
        inactive = [c for c in self.companions if not c.is_active]

        active_count = len(active)
        desc = f"**Active Companions** ({active_count}/3)\n"

        if active:
            desc += "\n"
            for comp in active:
                balanced_str = (
                    f"\n> ♊ T{comp.balanced_passive_tier} {comp.balanced_description}"
                    if comp.balanced_passive != "none"
                    else ""
                )
                desc += (
                    f"🟢 **{comp.name}** — {comp.species} | Lv.{comp.level}\n"
                    f"> T{comp.passive_tier} {comp.description}{balanced_str}\n\n"
                )
        else:
            desc += "\n*No active companions.*\n\n"

        if inactive:
            desc += f"**Inactive** ({len(inactive)})\n"
            desc += ", ".join(f"{c.name} (Lv.{c.level})" for c in inactive)

        embed.description = desc
        return embed

    # --- Callbacks ---
    async def _on_select(self, interaction: Interaction):
        comp_id = int(interaction.data["values"][0])
        comp = next((c for c in self.companions if c.id == comp_id), None)
        if comp is None:
            return await interaction.response.send_message(
                "Companion not found.", ephemeral=True
            )
        view = CompanionDetailView(self.bot, self.user_id, comp, self)
        await interaction.response.edit_message(embed=view.get_embed(), view=view)

    async def collect_loot(self, interaction: Interaction):
        result_msg = await CompanionLogic.collect_passive_rewards(
            self.bot, self.user_id, str(interaction.guild.id)
        )
        await interaction.response.send_message(result_msg, ephemeral=True)

    async def open_fusion(self, interaction: Interaction):
        from core.companions.fusion_views import FusionWizardView

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < 50000:
            return await interaction.response.send_message(
                "Fusion costs **50,000 Gold**. You cannot afford it.", ephemeral=True
            )
        if len(self.companions) < 2:
            return await interaction.response.send_message(
                "You need at least **2** companions to perform fusion.", ephemeral=True
            )

        view = FusionWizardView(
            self.bot, self.user_id, self.companions, parent_list_view=self
        )
        embed = discord.Embed(
            title="🧬 Companion Fusion",
            description="Combine two companions to merge their XP and randomize their traits.\n\n**Cost:** 50,000 Gold\nSelect your **Primary** companion below.",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=COMPANIONS_FUSION)
        await interaction.response.edit_message(embed=embed, view=view)


class CompanionDetailView(BaseView):
    def __init__(self, bot, user_id, companion, parent_view):
        super().__init__(bot, user_id)
        self.bot = bot
        self.user_id = user_id
        self.comp = companion
        self.parent = parent_view
        self._processing = False
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
        btn_reroll = ui.Button(
            label="Reroll Passive", style=ButtonStyle.primary, emoji="🎲", row=1
        )
        btn_reroll.callback = self.reroll_passive
        self.add_item(btn_reroll)

        # Balanced Engram
        btn_engram = ui.Button(
            label="Balanced Engram", style=ButtonStyle.blurple, emoji="♊", row=1
        )
        btn_engram.callback = self.open_balanced_engram
        self.add_item(btn_engram)

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

        # Cleanly display Max Level
        if self.comp.level >= CompanionMechanics.MAX_LEVEL:
            embed.add_field(name="EXP", value="Max Level", inline=True)
        else:
            next_xp = CompanionMechanics.calculate_next_level_xp(self.comp.level)
            embed.add_field(name="EXP", value=f"{self.comp.exp}/{next_xp}", inline=True)

        embed.add_field(
            name="Passive",
            value=f"T{self.comp.passive_tier} **{self.comp.description}**",
            inline=False,
        )
        if self.comp.balanced_passive != "none" and self.comp.balanced_passive_tier > 0:
            embed.add_field(
                name="Balanced Passive",
                value=f"T{self.comp.balanced_passive_tier} **{self.comp.balanced_description}**",
                inline=False,
            )
        embed.set_footer(text=f"Species: {self.comp.species}")
        return embed

    @staticmethod
    def _companion_slot_cap(level: int, ascension: int) -> int:
        """Returns the active-companion slot cap based on player progression.

        Level 40  → 1 slot
        Level 80  → 2 slots
        Ascension 20+ → 3 slots
        """
        if ascension >= 20:
            return 3
        if level >= 80:
            return 2
        if level >= 40:
            return 1
        return 0  # Companions not yet unlocked

    async def toggle_active(self, interaction: Interaction):
        # Fetch current player level/ascension to determine the slot cap
        user_row = await self.bot.database.users.get(
            self.user_id, str(interaction.guild.id)
        )
        player_level = user_row[4] if user_row else 1
        player_ascension = user_row[15] if user_row else 0
        max_slots = self._companion_slot_cap(player_level, player_ascension)

        new_state = not self.comp.is_active
        if new_state and max_slots == 0:
            return await interaction.response.send_message(
                "Companions unlock at Level 40!", ephemeral=True
            )

        success = await self.bot.database.companions.set_active(
            self.user_id, self.comp.id, new_state, max_active=max_slots
        )

        if not success:
            cap_str = (
                "1 slot (Level 40), 2 slots (Level 80), 3 slots (Ascension 20+)"
            )
            return await interaction.response.send_message(
                f"You've reached your companion slot cap!\n{cap_str}", ephemeral=True
            )

        if new_state:
            await self.bot.database.users.initialize_companion_timer(self.user_id)

        # Update this companion object
        self.comp.is_active = new_state

        # Update parent list state locally
        for c in self.parent.companions:
            if c.id == self.comp.id:
                c.is_active = new_state
                break

        # Rebuild the parent list buttons so icons (🟢 / ⚪) match
        self.parent.update_buttons()

        # Update this detail view’s buttons (label + styles)
        self.update_buttons()

        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def rename_modal(self, interaction: Interaction):
        modal = RenameModal(self)
        await interaction.response.send_modal(modal)

    async def reroll_passive(self, interaction: Interaction):
        # 1. Check Rune Balance
        runes = await self.bot.database.users.get_currency(
            self.user_id, "partnership_runes"
        )
        if runes < 1:
            return await interaction.response.send_message(
                "You need a **Rune of Partnership** to reroll passives.", ephemeral=True
            )

        # 2. Create Confirmation Embed
        embed = discord.Embed(
            title="🎲 Reroll Companion Passive?",
            description=f"**Companion:** {self.comp.name}\n**Current:** T{self.comp.passive_tier} {self.comp.passive_type.upper()}",
            color=discord.Color.purple(),
        )
        embed.set_thumbnail(url=self.comp.image_url)
        embed.add_field(
            name="Cost", value=f"1 Rune of Partnership\n(Owned: {runes})", inline=True
        )
        embed.add_field(
            name="Mechanics",
            value="• Guaranteed **New Passive Type**\n• **10% Chance** to Upgrade Tier",
            inline=True,
        )

        confirm_view = RerollConfirmView(self.bot, self.user_id, self.comp, runes, self)

        # 3. Swap View
        await interaction.response.edit_message(
            content=None, embed=embed, view=confirm_view
        )

    async def open_balanced_engram(self, interaction: Interaction):
        await interaction.response.defer()

        view = BalancedEngramView(self.bot, self.user_id, self.comp, self)
        await view.render(interaction)

    async def release_confirm(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        await self.bot.database.companions.delete_companion(self.comp.id, self.user_id)

        # Remove from parent list
        self.parent.companions = [
            c for c in self.parent.companions if c.id != self.comp.id
        ]
        self.parent.update_buttons()

        await interaction.edit_original_response(
            embed=self.parent.get_embed(), view=self.parent
        )

    async def go_back(self, interaction: Interaction):
        # Rebuild parent buttons in case active states changed
        self.parent.update_buttons()
        await interaction.response.edit_message(
            embed=self.parent.get_embed(), view=self.parent
        )


class RenameModal(ui.Modal, title="Rename Companion"):
    name = ui.TextInput(label="New Name", max_length=20)

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        new_name = self.name.value
        await self.parent_view.bot.database.companions.rename(
            self.parent_view.comp.id, new_name
        )
        self.parent_view.comp.name = new_name

        await interaction.response.edit_message(
            embed=self.parent_view.get_embed(), view=self.parent_view
        )
