import random

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.base_view import BaseView
from core.images import SLAYER_EMBLEM, SLAYER_MASTER
from core.slayer.mechanics import (
    BOSS_TASK_CATALOG,
    BOSS_TASK_PREFIX,
    SlayerMechanics,
)


class SlayerDashboardView(BaseView):
    def __init__(self, bot, user_id, server_id, profile, player_level):
        super().__init__(bot, user_id, server_id)  # timeout=600 by default
        self.profile = profile
        self.player_level = player_level
        self._processing = False
        self.setup_buttons()

    def build_embed(self) -> discord.Embed:
        lvl = self.profile["level"]
        pts = self.profile["points"]

        # Parse cumulative XP into normalized visual progress
        current_xp_prog, next_xp_req = SlayerMechanics.get_xp_progress(
            self.profile["xp"]
        )

        embed = discord.Embed(title="💀 Slayer Master", color=discord.Color.dark_red())
        embed.set_author(name="Slayer Master Kael", icon_url=SLAYER_MASTER)

        embed.add_field(
            name="Profile",
            value=f"**Level:** {lvl}\n**XP:** {current_xp_prog:,}/{next_xp_req:,}\n**Points:** {pts}",
            inline=True,
        )
        embed.add_field(
            name="Materials",
            value=f"🩸 **Violent Essence:** {self.profile['violent_essence']}\n❤️ **Imbued Hearts:** {self.profile['imbued_heart']}",
            inline=True,
        )

        if self.profile["active_task_species"]:
            prog = self.profile["active_task_progress"]
            req = self.profile["active_task_amount"]
            species = self.profile["active_task_species"]
            if species.startswith(BOSS_TASK_PREFIX):
                boss_name = species[len(BOSS_TASK_PREFIX):].capitalize()
                task_line = f"Hunt **{req}× {boss_name}** *(Boss Task)*"
            else:
                task_line = f"Slay **{req} {species}**"
            embed.add_field(
                name="Current Task",
                value=f"{task_line}\n*Progress: {prog}/{req}*",
                inline=False,
            )
        else:
            embed.add_field(
                name="Current Task",
                value="No active task. Request one from the master.",
                inline=False,
            )

        return embed

    def setup_buttons(self):
        self.clear_items()

        has_task = bool(self.profile["active_task_species"])

        btn_task = ui.Button(
            label="Get Task", style=ButtonStyle.success, disabled=has_task, row=0
        )
        btn_task.callback = self.get_task
        self.add_item(btn_task)

        btn_skip = ui.Button(
            label="Skip Task (15 pts)",
            style=ButtonStyle.danger,
            disabled=(not has_task or self.profile["points"] < 15),
            row=0,
        )
        btn_skip.callback = self.skip_task
        self.add_item(btn_skip)

        btn_emblem = ui.Button(
            label="Manage Emblem", style=ButtonStyle.primary, emoji="🛡️", row=1
        )
        btn_emblem.callback = self.open_emblem
        self.add_item(btn_emblem)

        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary, row=1)
        btn_close.callback = self.close_view
        self.add_item(btn_close)

    async def get_task(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        # 10% chance to offer a boss task if the player has access to any
        available_bosses = SlayerMechanics.available_boss_tasks(self.player_level)
        if available_bosses and random.random() < 0.10:
            boss = random.choice(available_bosses)
            task_key = f"{BOSS_TASK_PREFIX}{boss['key']}"
            modal = BossTaskAmountModal(task_key, boss["name"], self)
            # open_modal responds to the interaction — don't defer beforehand
            self._processing = False
            await interaction.response.send_modal(modal)
            return

        await interaction.response.defer()
        species, amount = SlayerMechanics.generate_task(self.player_level)

        await self.bot.database.slayer.assign_task(
            self.user_id, self.server_id, species, amount
        )
        self.profile = await self.bot.database.slayer.get_profile(
            self.user_id, self.server_id
        )

        self._processing = False
        self.setup_buttons()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def skip_task(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        if self.profile["points"] < 15:
            self._processing = False
            return await interaction.response.send_message(
                "Not enough Slayer Points!", ephemeral=True
            )

        await interaction.response.defer()
        await self.bot.database.slayer.add_rewards(
            self.user_id, self.server_id, 0, -15
        )  # Deduct 15 pts
        await self.bot.database.slayer.clear_task(self.user_id, self.server_id)

        self.profile = await self.bot.database.slayer.get_profile(
            self.user_id, self.server_id
        )
        self._processing = False
        self.setup_buttons()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def open_emblem(self, interaction: Interaction):
        emblem = await self.bot.database.slayer.get_emblem(self.user_id, self.server_id)
        view = EmblemView(
            self.bot, self.user_id, self.server_id, self.profile, emblem, self
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()


class BossTaskAmountModal(ui.Modal, title="Boss Hunt"):
    """Modal that lets the player choose how many boss kills to hunt (1–10)."""

    count_input = ui.TextInput(
        label="How many to hunt? (1–10)",
        placeholder="Enter a number from 1 to 10",
        min_length=1,
        max_length=2,
        required=True,
    )

    def __init__(self, task_key: str, boss_display_name: str, parent_view):
        super().__init__()
        self.task_key = task_key
        self.boss_display_name = boss_display_name
        self.parent = parent_view

    async def on_submit(self, interaction: Interaction):
        try:
            count = int(self.count_input.value.strip())
            if not 1 <= count <= 10:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "Please enter a number between 1 and 10.", ephemeral=True
            )

        await interaction.response.defer()
        await self.parent.bot.database.slayer.assign_task(
            self.parent.user_id, self.parent.server_id, self.task_key, count
        )
        self.parent.profile = await self.parent.bot.database.slayer.get_profile(
            self.parent.user_id, self.parent.server_id
        )
        self.parent.setup_buttons()
        await interaction.edit_original_response(
            embed=self.parent.build_embed(), view=self.parent
        )


class EmblemView(BaseView):
    def __init__(self, bot, user_id, server_id, profile, emblem, parent_view):
        super().__init__(bot, user_id, server_id)
        self.profile = profile
        self.emblem = emblem
        self.parent = parent_view
        self.unlocked_slots = SlayerMechanics.get_unlocked_slots(self.profile["level"])
        self.setup_ui()

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="💀 Slayer Emblem",
            description="Enhance your combat prowess.",
            color=discord.Color.dark_purple(),
        )
        embed.set_thumbnail(url=SLAYER_EMBLEM)
        # Display Slots
        unlock_reqs = {1: 1, 2: 20, 3: 40, 4: 60, 5: 80}

        for slot in range(1, 6):
            if slot <= self.unlocked_slots:
                data = self.emblem.get(slot, {"type": "none", "tier": 1})
                if data["type"] == "none":
                    embed.add_field(
                        name=f"Slot {slot}",
                        value="*Empty - Needs Awakening*",
                        inline=False,
                    )
                else:
                    # FETCH DYNAMIC DESCRIPTION
                    desc = SlayerMechanics.get_passive_description(
                        data["type"], data["tier"]
                    )
                    embed.add_field(
                        name=f"Slot {slot} (Tier {data['tier']})",
                        value=f"**{desc}**",
                        inline=False,
                    )
            else:
                embed.add_field(
                    name=f"Slot {slot} 🔒",
                    value=f"Unlocks at Slayer Level {unlock_reqs[slot]}",
                    inline=False,
                )

        return embed

    def setup_ui(self):
        self.clear_items()

        # Select Menu for unlocked slots
        options = []
        for slot in range(1, self.unlocked_slots + 1):
            data = self.emblem.get(slot, {"type": "none", "tier": 1})

            if data["type"] == "none":
                lbl = f"Slot {slot} - Empty"
            else:
                # Provide a clean label for the dropdown
                desc = SlayerMechanics.get_passive_description(
                    data["type"], data["tier"]
                )
                lbl = f"Slot {slot} - {desc}"

            options.append(
                SelectOption(label=lbl[:100], value=str(slot))
            )  # Cap at 100 chars for Discord limits

        if options:
            select = ui.Select(
                placeholder="Select a slot to modify...", options=options
            )
            select.callback = self.select_slot
            self.add_item(select)

        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def select_slot(self, interaction: Interaction):
        slot = int(interaction.data["values"][0])
        slot_data = self.emblem.get(slot, {"type": "none", "tier": 1})

        view = SlotManageView(
            self.bot, self.user_id, self.server_id, self.profile, slot, slot_data, self
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def go_back(self, interaction: Interaction):
        # Refresh profile before going back
        self.parent.profile = await self.bot.database.slayer.get_profile(
            self.user_id, self.server_id
        )
        self.parent.setup_buttons()
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()


class SlotManageView(BaseView):
    def __init__(
        self, bot, user_id, server_id, profile, slot_num, slot_data, parent_view
    ):
        super().__init__(bot, user_id, server_id)
        self.profile = profile
        self.slot_num = slot_num
        self.slot_data = slot_data
        self.parent = parent_view
        self.result_msg: str = ""
        self.setup_ui()

    def build_embed(self) -> discord.Embed:
        p_type = self.slot_data["type"]
        p_tier = self.slot_data["tier"]

        embed = discord.Embed(
            title=f"Modify Slot {self.slot_num}", color=discord.Color.dark_magenta()
        )
        embed.description = f"🩸 **Violent Essence:** {self.profile['violent_essence']}\n❤️ **Imbued Hearts:** {self.profile['imbued_heart']}\n\n"
        if self.result_msg:
            embed.description += f"{self.result_msg}\n\n"

        if p_type == "none":
            embed.description += "**Status:** Empty\nUse 1 Violent Essence to Awaken a random Tier 1 passive."
        else:
            # USE DYNAMIC DESCRIPTION
            desc = SlayerMechanics.get_passive_description(p_type, p_tier)
            success_rate = max(0, int((1.0 - (p_tier * 0.20)) * 100))
            downgrade_rate = 0 if p_tier == 1 else int(((p_tier - 1) * 0.20) * 100)

            embed.add_field(name="Current Passive", value=f"**{desc}**", inline=False)
            if p_tier < 5:
                # Add a preview of what the NEXT tier looks like
                next_desc = SlayerMechanics.get_passive_description(p_type, p_tier + 1)
                embed.add_field(
                    name="Next Tier Preview", value=f"*{next_desc}*", inline=False
                )

                embed.add_field(
                    name="Upgrade Odds",
                    value=f"🟢 Success: {success_rate}%\n🔴 Downgrade: {downgrade_rate}%",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Upgrade Status", value="🌟 Max Tier Reached!", inline=False
                )

        return embed

    def setup_ui(self):
        self.clear_items()

        essences = self.profile["violent_essence"]
        hearts = self.profile["imbued_heart"]
        p_type = self.slot_data["type"]
        p_tier = self.slot_data["tier"]

        if p_type == "none":
            btn_awaken = ui.Button(
                label="Awaken (1 Essence)",
                style=ButtonStyle.primary,
                emoji="🩸",
                disabled=(essences < 1),
            )
            btn_awaken.callback = self.awaken_slot
            self.add_item(btn_awaken)
        else:
            btn_upgrade = ui.Button(
                label="Upgrade (1 Essence)",
                style=ButtonStyle.success,
                emoji="🩸",
                disabled=(essences < 1 or p_tier >= 5),
            )
            btn_upgrade.callback = self.upgrade_slot
            self.add_item(btn_upgrade)

            btn_reroll = ui.Button(
                label="Reroll Type (1 Heart)",
                style=ButtonStyle.primary,
                emoji="❤️",
                disabled=(hearts < 1),
            )
            btn_reroll.callback = self.reroll_slot
            self.add_item(btn_reroll)

        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def awaken_slot(self, interaction: Interaction):
        await interaction.response.defer()

        # ATOMIC DEDUCTION CHECK
        if not await self.bot.database.slayer.consume_material(
            self.user_id, self.server_id, "violent_essence", 1
        ):
            return await interaction.followup.send(
                "Not enough Violent Essence!", ephemeral=True
            )

        self.profile["violent_essence"] -= 1

        # Assign random
        new_type = random.choice(SlayerMechanics.PASSIVE_POOL)
        self.slot_data["type"] = new_type
        self.slot_data["tier"] = 1

        await self.bot.database.slayer.update_emblem_slot(
            self.user_id, self.server_id, self.slot_num, new_type, 1
        )

        new_desc = SlayerMechanics.get_passive_description(new_type, 1)
        self.result_msg = f"✅ Slot Awakened! Gained: **{new_desc}**"
        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def upgrade_slot(self, interaction: Interaction):
        await interaction.response.defer()

        # ATOMIC DEDUCTION CHECK
        if not await self.bot.database.slayer.consume_material(
            self.user_id, self.server_id, "violent_essence", 1
        ):
            return await interaction.followup.send(
                "Not enough Violent Essence!", ephemeral=True
            )

        self.profile["violent_essence"] -= 1

        old_tier = self.slot_data["tier"]
        success, new_tier = SlayerMechanics.roll_upgrade(old_tier)

        self.slot_data["tier"] = new_tier
        await self.bot.database.slayer.update_emblem_slot(
            self.user_id,
            self.server_id,
            self.slot_num,
            self.slot_data["type"],
            new_tier,
        )

        if success:
            msg = f"✨ **Success!** Upgraded to Tier {new_tier}!"
        elif new_tier < old_tier:
            msg = (
                f"💥 **Failure.** The essence corrupted. Downgraded to Tier {new_tier}."
            )
        else:
            msg = f"💨 **Failure.** The essence faded. Slot remains Tier {new_tier}."

        self.result_msg = msg
        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def reroll_slot(self, interaction: Interaction):
        await interaction.response.defer()

        # ATOMIC DEDUCTION CHECK
        if not await self.bot.database.slayer.consume_material(
            self.user_id, self.server_id, "imbued_heart", 1
        ):
            return await interaction.followup.send(
                "Not enough Imbued Hearts!", ephemeral=True
            )

        self.profile["imbued_heart"] -= 1

        # Pick new random (exclude current)
        pool = [p for p in SlayerMechanics.PASSIVE_POOL if p != self.slot_data["type"]]
        new_type = random.choice(pool)

        self.slot_data["type"] = new_type
        await self.bot.database.slayer.update_emblem_slot(
            self.user_id,
            self.server_id,
            self.slot_num,
            new_type,
            self.slot_data["tier"],
        )

        new_desc = SlayerMechanics.get_passive_description(
            new_type, self.slot_data["tier"]
        )
        self.result_msg = f"❤️ **Rerolled!** New Passive: **{new_desc}**"
        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def go_back(self, interaction: Interaction):
        # Sync changes back to parent
        self.parent.emblem[self.slot_num] = self.slot_data
        self.parent.setup_ui()
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()
