import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.character.passive_formatters import get_scaled_passive_description
from core.emojis import GOLD_COIN, VOID_ENGRAM
from core.images import (
    SYLAS_AUTHOR,
    UPGRADE_ENCHANT,
    UPGRADE_VOID_ENGRAM,
)
from core.inventory.upgrades.base import BaseUpgradeView
from core.items.equipment_mechanics import EquipmentMechanics
from core.models import Accessory, Boot, Glove, Helmet
from core.npc_voices import get_quip


class PotentialView(BaseUpgradeView):
    def __init__(self, bot, user_id, item, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self._processing = False

    async def render(self, interaction: Interaction):
        self._render_gen += 1
        _my_gen = self._render_gen
        self._processing = False
        # 1. Determine Item Type & Bonus
        is_accessory = isinstance(self.item, Accessory)
        if is_accessory:
            cost = EquipmentMechanics.calculate_potential_cost(self.item.passive_lvl)
            max_lvl = 10
            rune_bonus = 25
        else:
            cost = EquipmentMechanics.calculate_ap_cost(self.item.passive_lvl)
            max_lvl = 5 if isinstance(self.item, (Glove, Helmet)) else 6
            rune_bonus = 15

        # 2. Fetch User Data
        gold = await self.bot.database.users.get_gold(self.user_id)
        runes = await self.bot.database.users.get_currency(
            self.user_id, "potential_runes"
        )

        # 3. Logic
        is_capped = self.item.passive_lvl >= max_lvl
        has_attempts = self.item.potential_remaining > 0
        base_rate = max(75 - (self.item.passive_lvl * 5), 30)

        desc = (
            f"{get_quip('enchant')}\n\n"
            f"**Current Level:** {self.item.passive_lvl}/{max_lvl}\n"
            f"**Attempts Left:** {self.item.potential_remaining}\n"
            f"**Success Rate:** {base_rate}%\n"
            f"**Cost:** {cost:,} Gold ({gold:,})\n\n"
            f"💎 **Runes Owned:** {runes}"
        )

        self.cost = cost
        self.rune_bonus = rune_bonus

        embed = discord.Embed(
            title=f"Enchant {self.item.name}",
            description=desc,
            color=discord.Color.purple(),
        )
        embed.set_author(name="Artificer Sylas", icon_url=SYLAS_AUTHOR)
        embed.set_thumbnail(url=UPGRADE_ENCHANT)

        # --- BUTTONS ---
        self.clear_items()

        # Standard Enchant
        btn_std = Button(
            label=f"Enchant ({base_rate}%)", style=ButtonStyle.primary, row=0
        )
        btn_std.disabled = gold < cost or not has_attempts or is_capped
        btn_std.callback = lambda i: self.confirm_enchant(i, use_rune=False)
        self.add_item(btn_std)

        # Rune Enchant
        boosted_rate = min(100, base_rate + rune_bonus)
        btn_rune = Button(
            label=f"Use Rune ({boosted_rate}%)",
            style=ButtonStyle.success,
            emoji="💎",
            row=0,
        )
        btn_rune.disabled = gold < cost or not has_attempts or is_capped or runes < 1
        btn_rune.callback = lambda i: self.confirm_enchant(i, use_rune=True)
        self.add_item(btn_rune)

        self.add_back_button()

        await self._send_render(interaction, embed, render_gen=_my_gen)

    async def confirm_enchant(self, interaction: Interaction, use_rune: bool):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        # Re-check funds/runes
        quest_msgs = []
        if use_rune:
            runes = await self.bot.database.users.get_currency(
                self.user_id, "potential_runes"
            )
            if runes < 1:
                return await interaction.response.send_message(
                    "No Runes left!", ephemeral=True
                )
            await self.bot.database.users.modify_currency(
                self.user_id, "potential_runes", -1
            )
            try:
                from core.quests.mechanics import tick_quest_progress

                quest_msgs = await tick_quest_progress(
                    self.bot, self.user_id, str(interaction.guild_id), "rune_potential"
                )
            except Exception:
                pass
            bonus = self.rune_bonus
        else:
            bonus = 0

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        # Deduct Gold
        await self.bot.database.users.modify_gold(self.user_id, -self.cost)

        # Roll
        success = EquipmentMechanics.roll_potential_outcome(
            self.item.passive_lvl, bonus_chance=bonus
        )

        # DB Updates
        itype = (
            "accessory"
            if isinstance(self.item, Accessory)
            else (
                "glove"
                if isinstance(self.item, Glove)
                else ("boot" if isinstance(self.item, Boot) else "helmet")
            )
        )

        self.item.potential_remaining -= 1
        await self.bot.database.equipment.update_counter(
            self.item.item_id,
            itype,
            "potential_remaining",
            self.item.potential_remaining,
        )

        result_embed = discord.Embed(title="Enchantment Result")
        result_embed.set_author(name="Artificer Sylas", icon_url=SYLAS_AUTHOR)
        result_embed.set_thumbnail(url=UPGRADE_ENCHANT)

        if success:
            if self.item.passive == "none":
                new_p = EquipmentMechanics.get_new_passive(itype)
                self.item.passive = new_p
                self.item.passive_lvl = 1
                await self.bot.database.equipment.update_passive(
                    self.item.item_id, itype, new_p
                )
                await self.bot.database.equipment.update_counter(
                    self.item.item_id, itype, "passive_lvl", 1
                )
                passive_desc = get_scaled_passive_description(itype, new_p, 1)
                msg = f"Unlocked **{new_p}**!" + (
                    f"\n*{passive_desc}*" if passive_desc else ""
                )
            else:
                self.item.passive_lvl += 1
                await self.bot.database.equipment.update_counter(
                    self.item.item_id, itype, "passive_lvl", self.item.passive_lvl
                )
                msg = f"Upgraded to Level **{self.item.passive_lvl}**!"

            result_embed.color = discord.Color.gold()
            result_embed.description = (
                f"{get_quip('enchant')}\n\n✨ **Success!**\n{msg}"
            )
        else:
            result_embed.color = discord.Color.dark_grey()
            result_embed.description = "💔 **Failed.**\nThe magic failed to take hold."

        if quest_msgs:
            result_embed.add_field(
                name="📋 Quest Progress", value="\n".join(quest_msgs), inline=False
            )

        # UI Refresh
        self.clear_items()
        max_lvl = (
            10
            if isinstance(self.item, Accessory)
            else (5 if isinstance(self.item, (Glove, Helmet)) else 6)
        )
        if self.item.potential_remaining > 0 and self.item.passive_lvl < max_lvl:
            again_btn = Button(label="Enchant Again", style=ButtonStyle.primary)
            again_btn.callback = self.render
            self.add_item(again_btn)

        self.add_back_button()
        await interaction.edit_original_response(embed=result_embed, view=self)


class VoidEngramView(BaseUpgradeView):
    """Allows consuming a Void Engram to unlock or reroll a void accessory passive."""

    def __init__(self, bot, user_id, item: Accessory, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self._processing = False

    async def render(self, interaction: Interaction):
        self._render_gen += 1
        _my_gen = self._render_gen
        self._processing = False
        server_id = str(interaction.guild.id)

        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        self.engrams = uber_prog["void_engrams"]

        current_passive = getattr(self.item, "void_passive", "none")
        display_passive = (
            current_passive.replace("_", " ").title()
            if current_passive != "none"
            else "None"
        )

        desc = (
            f"**Current Void Passive:** {display_passive}\n"
            f"{VOID_ENGRAM} **Void Engrams Owned:** {self.engrams}\n"
            f"**Gold Cost:** {GOLD_COIN} 25,000,000\n\n"
            "Consuming an Engram will corrupt your accessory with a Void passive, or reroll your existing one."
        )

        self.embed = discord.Embed(
            title=f"{VOID_ENGRAM} Void Corruption: {self.item.name}",
            description=desc,
            color=discord.Color.dark_theme(),
        )
        self.embed.set_author(name="Artificer Sylas", icon_url=SYLAS_AUTHOR)
        self.embed.set_thumbnail(url=UPGRADE_VOID_ENGRAM)
        self.clear_items()
        btn_consume = Button(
            label="Consume Engram",
            style=ButtonStyle.secondary,
            emoji=VOID_ENGRAM,
            disabled=(self.engrams < 1),
        )
        btn_consume.callback = self.confirm_engram
        self.add_item(btn_consume)
        self.add_back_button()

        await self._send_render(interaction, self.embed, render_gen=_my_gen)

    async def confirm_engram(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        server_id = str(interaction.guild.id)
        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        if uber_prog["void_engrams"] < 1:
            self._processing = False
            return await interaction.response.send_message(
                "You do not have any Void Engrams!", ephemeral=True
            )

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < 25_000_000:
            self._processing = False
            return await interaction.response.send_message(
                f"You need **{GOLD_COIN} 25,000,000 gold** to use a Void Engram.",
                ephemeral=True,
            )

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        await self.bot.database.users.modify_gold(self.user_id, -25_000_000)
        await self.bot.database.uber.increment_void_engrams(self.user_id, server_id, -1)

        current_p = getattr(self.item, "void_passive", "none")
        new_passive = EquipmentMechanics.roll_void_passive(current_p)

        await self.bot.database.equipment.update_passive(
            self.item.item_id, "accessory", new_passive, "void_passive"
        )
        self.item.void_passive = new_passive

        display_new = new_passive.replace("_", " ").title()
        res_embed = discord.Embed(
            title=f"{VOID_ENGRAM} Engram Absorbed!",
            description=f"The Engram dissolves into the void, reshaping your accessory.\n\n**New Passive:** {display_new}",
            color=discord.Color.dark_theme(),
        )
        res_embed.set_author(name="Artificer Sylas", icon_url=SYLAS_AUTHOR)
        res_embed.set_thumbnail(url=UPGRADE_VOID_ENGRAM)
        self.clear_items()
        if uber_prog["void_engrams"] - 1 > 0:
            btn_again = Button(label="Roll Again", style=ButtonStyle.primary)
            btn_again.callback = self.render
            self.add_item(btn_again)

        self.add_back_button()
        await interaction.edit_original_response(embed=res_embed, view=self)
        self.message = await interaction.original_response()
