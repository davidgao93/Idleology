import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.hematurgy.mechanics import (
    MUTATIVE_COST,
    SLOT_UNLOCK_COSTS,
    TRANSMUTE_RATIO,
    UPGRADE_COSTS,
    HematurgyMechanics,
)

_SLOT_ORDER = [
    "head", "torso", "right_arm", "left_arm",
    "right_leg", "left_leg", "cheeks", "organs",
]

_SLOT_LABELS = {
    "head": "Head", "torso": "Torso",
    "right_arm": "Right Arm", "left_arm": "Left Arm",
    "right_leg": "Right Leg", "left_leg": "Left Leg",
    "cheeks": "Cheeks", "organs": "Organs",
}

_SLOT_EMOJI = {
    "head": "💀", "torso": "🫁", "right_arm": "💪", "left_arm": "🤜",
    "right_leg": "🦵", "left_leg": "🦿", "cheeks": "🍑", "organs": "🫀",
}

_BLOOD_EMOJI = {"primordial": "🩸", "evolutionary": "🧬", "mutative": "☣️"}
_BLOOD_NAMES = {"primordial": "Primordial", "evolutionary": "Evolutionary", "mutative": "Mutative"}


def _build_hematurgy_embed(passives: dict, blood: dict) -> discord.Embed:
    embed = discord.Embed(
        title="🩸 Hematurgy",
        description=(
            "Imbue your body slots with permanent passives through the power of monster blood.\n\n"
            f"🩸 **Primordial:** {blood.get('primordial', 0):,}  "
            f"🧬 **Evolutionary:** {blood.get('evolutionary', 0):,}  "
            f"☣️ **Mutative:** {blood.get('mutative', 0):,}"
        ),
        color=0x8B0000,
    )
    for slot in _SLOT_ORDER:
        label = _SLOT_LABELS[slot]
        emoji = _SLOT_EMOJI[slot]
        if slot in passives:
            p = passives[slot]
            name = HematurgyMechanics.passive_display_name(p["passive_id"])
            embed.add_field(
                name=f"{emoji} {label}",
                value=f"✦ **{name}** (Tier {p['tier']}/5)",
                inline=True,
            )
        else:
            cost = SLOT_UNLOCK_COSTS[slot]
            embed.add_field(
                name=f"{emoji} {label}",
                value=f"*No passive* — Unlock: {cost:,} 🩸",
                inline=True,
            )
    return embed


# ---------------------------------------------------------------------------
# Transmute Modal
# ---------------------------------------------------------------------------

class TransmuteModal(ui.Modal, title="Transmute Blood (3:1)"):
    amount_input = ui.TextInput(
        label="Amount to convert (multiples of 3)",
        placeholder="e.g. 300",
        min_length=1,
        max_length=7,
    )

    def __init__(self, parent: "HematurgyView", source: str, target: str):
        super().__init__()
        self.parent = parent
        self.source = source
        self.target = target
        self.title = f"Transmute {_BLOOD_NAMES[source]} → {_BLOOD_NAMES[target]} (3:1)"

    async def on_submit(self, interaction: Interaction):
        try:
            amount = int(self.amount_input.value)
            if amount <= 0 or amount % TRANSMUTE_RATIO != 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                f"Enter a positive multiple of {TRANSMUTE_RATIO}.", ephemeral=True
            )

        blood = await self.parent.bot.database.hematurgy.get_blood(self.parent.user_id)
        if blood[self.source] < amount:
            return await interaction.response.send_message(
                f"Insufficient {_BLOOD_NAMES[self.source]} blood (have {blood[self.source]:,}).",
                ephemeral=True,
            )

        gained = amount // TRANSMUTE_RATIO
        await self.parent.bot.database.hematurgy.modify_blood(self.parent.user_id, self.source, -amount)
        await self.parent.bot.database.hematurgy.modify_blood(self.parent.user_id, self.target, gained)

        self.parent.blood = await self.parent.bot.database.hematurgy.get_blood(self.parent.user_id)
        await interaction.response.edit_message(
            embed=_build_hematurgy_embed(self.parent.passives, self.parent.blood),
            view=self.parent,
        )


# ---------------------------------------------------------------------------
# Transmute source/target selects
# ---------------------------------------------------------------------------

class TransmuteSourceSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=f"{_BLOOD_NAMES[t]} Blood", value=t, emoji=_BLOOD_EMOJI[t])
            for t in ("primordial", "evolutionary", "mutative")
        ]
        super().__init__(placeholder="Source blood type...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: Interaction):
        source = self.values[0]
        view = TransmuteTargetView(self.view.parent, source)
        await interaction.response.edit_message(
            content=f"Select the **target** type to receive {_BLOOD_NAMES[source]} → ?",
            embed=None,
            view=view,
        )


class TransmuteTargetSelect(ui.Select):
    def __init__(self, source: str):
        self.source = source
        options = [
            discord.SelectOption(label=f"{_BLOOD_NAMES[t]} Blood", value=t, emoji=_BLOOD_EMOJI[t])
            for t in ("primordial", "evolutionary", "mutative")
            if t != source
        ]
        super().__init__(placeholder="Target blood type...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: Interaction):
        target = self.values[0]
        modal = TransmuteModal(self.view.parent, self.source, target)
        await interaction.response.send_modal(modal)


class TransmuteTargetView(BaseView):
    def __init__(self, parent: "HematurgyView", source: str):
        super().__init__(parent.bot, parent=parent)
        self.parent = parent
        self.add_item(TransmuteTargetSelect(source))

    @ui.button(label="Cancel", style=ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(
            content=None,
            embed=_build_hematurgy_embed(self.parent.passives, self.parent.blood),
            view=self.parent,
        )
        self.stop()


# ---------------------------------------------------------------------------
# Slot Detail View
# ---------------------------------------------------------------------------

class SlotDetailView(BaseView):
    def __init__(self, parent: "HematurgyView", slot_type: str):
        super().__init__(parent.bot, parent=parent)
        self.parent = parent
        self.slot_type = slot_type
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()
        passive = self.parent.passives.get(self.slot_type)
        blood = self.parent.blood

        if passive is None:
            # Unlock button
            cost = SLOT_UNLOCK_COSTS[self.slot_type]
            can_unlock = blood.get("primordial", 0) >= cost
            btn_unlock = ui.Button(
                label=f"Unlock ({cost:,} 🩸)",
                style=ButtonStyle.success,
                disabled=not can_unlock,
            )
            btn_unlock.callback = self._unlock
            self.add_item(btn_unlock)
        else:
            tier = passive["tier"]
            # Upgrade button
            if tier < 5:
                cost = UPGRADE_COSTS[tier + 1]
                can_upgrade = blood.get("evolutionary", 0) >= cost
                btn_upgrade = ui.Button(
                    label=f"Upgrade T{tier}→T{tier+1} ({cost:,} 🧬)",
                    style=ButtonStyle.primary,
                    disabled=not can_upgrade,
                )
                btn_upgrade.callback = self._upgrade
                self.add_item(btn_upgrade)
            else:
                btn_max = ui.Button(label="Max Tier Reached", style=ButtonStyle.primary, disabled=True)
                self.add_item(btn_max)

            # Mutate button
            can_mutate = blood.get("mutative", 0) >= MUTATIVE_COST
            btn_mutate = ui.Button(
                label=f"Mutate ({MUTATIVE_COST:,} ☣️)",
                style=ButtonStyle.danger,
                disabled=not can_mutate,
            )
            btn_mutate.callback = self._mutate
            self.add_item(btn_mutate)

        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        btn_back.callback = self._back
        self.add_item(btn_back)

    def build_embed(self) -> discord.Embed:
        slot_label = _SLOT_LABELS[self.slot_type]
        emoji = _SLOT_EMOJI[self.slot_type]
        passive = self.parent.passives.get(self.slot_type)
        blood = self.parent.blood

        embed = discord.Embed(
            title=f"{emoji} {slot_label} — Hematurgy",
            color=0x8B0000,
        )

        embed.add_field(
            name="Blood",
            value=(
                f"🩸 Primordial: {blood.get('primordial', 0):,}\n"
                f"🧬 Evolutionary: {blood.get('evolutionary', 0):,}\n"
                f"☣️ Mutative: {blood.get('mutative', 0):,}"
            ),
            inline=False,
        )

        if passive is None:
            cost = SLOT_UNLOCK_COSTS[self.slot_type]
            embed.add_field(
                name="Status",
                value=f"*No passive unlocked*\nCost to unlock: **{cost:,}** 🩸 Primordial blood",
                inline=False,
            )
        else:
            name = HematurgyMechanics.passive_display_name(passive["passive_id"])
            tier = passive["tier"]
            desc = HematurgyMechanics.passive_description(passive["passive_id"], tier)
            embed.add_field(
                name=f"Active Passive — Tier {tier}/5",
                value=f"**{name}**\n{desc}",
                inline=False,
            )
            if tier < 5:
                upgrade_cost = UPGRADE_COSTS[tier + 1]
                embed.add_field(
                    name="Upgrade Cost",
                    value=f"{upgrade_cost:,} 🧬 Evolutionary blood",
                    inline=True,
                )
            embed.add_field(
                name="Mutate Cost",
                value=f"{MUTATIVE_COST:,} ☣️ Mutative blood",
                inline=True,
            )

        return embed

    async def _unlock(self, interaction: Interaction):
        await interaction.response.defer()
        cost = SLOT_UNLOCK_COSTS[self.slot_type]
        blood = await self.parent.bot.database.hematurgy.get_blood(self.parent.user_id)
        if blood["primordial"] < cost:
            return await interaction.followup.send("Insufficient Primordial blood.", ephemeral=True)

        owned = await self.parent.bot.database.hematurgy.get_unlocked_passive_ids(self.parent.user_id)
        passive_id = HematurgyMechanics.get_random_main_passive(owned)
        if passive_id is None:
            return await interaction.followup.send(
                "All main passives are already unlocked across your slots!", ephemeral=True
            )

        await self.parent.bot.database.hematurgy.modify_blood(self.parent.user_id, "primordial", -cost)
        await self.parent.bot.database.hematurgy.set_passive(self.parent.user_id, self.slot_type, passive_id)

        self.parent.passives = await self.parent.bot.database.hematurgy.get_all_passives(self.parent.user_id)
        self.parent.blood = await self.parent.bot.database.hematurgy.get_blood(self.parent.user_id)
        self._build_buttons()

        name = HematurgyMechanics.passive_display_name(passive_id)
        embed = self.build_embed()
        embed.set_footer(text=f"Unlocked: {name} (Tier 1)")
        await interaction.edit_original_response(embed=embed, view=self)

    async def _upgrade(self, interaction: Interaction):
        await interaction.response.defer()
        passive = self.parent.passives.get(self.slot_type)
        if passive is None or passive["tier"] >= 5:
            return

        cost = UPGRADE_COSTS[passive["tier"] + 1]
        blood = await self.parent.bot.database.hematurgy.get_blood(self.parent.user_id)
        if blood["evolutionary"] < cost:
            return await interaction.followup.send("Insufficient Evolutionary blood.", ephemeral=True)

        await self.parent.bot.database.hematurgy.modify_blood(self.parent.user_id, "evolutionary", -cost)
        new_tier = await self.parent.bot.database.hematurgy.upgrade_passive(self.parent.user_id, self.slot_type)

        self.parent.passives = await self.parent.bot.database.hematurgy.get_all_passives(self.parent.user_id)
        self.parent.blood = await self.parent.bot.database.hematurgy.get_blood(self.parent.user_id)
        self._build_buttons()

        embed = self.build_embed()
        embed.set_footer(text=f"Upgraded to Tier {new_tier}!")
        await interaction.edit_original_response(embed=embed, view=self)

    async def _mutate(self, interaction: Interaction):
        await interaction.response.defer()
        passive = self.parent.passives.get(self.slot_type)
        if passive is None:
            return

        blood = await self.parent.bot.database.hematurgy.get_blood(self.parent.user_id)
        if blood["mutative"] < MUTATIVE_COST:
            return await interaction.followup.send("Insufficient Mutative blood.", ephemeral=True)

        await self.parent.bot.database.hematurgy.modify_blood(self.parent.user_id, "mutative", -MUTATIVE_COST)

        outcome = HematurgyMechanics.roll_mutative_outcome()
        footer = ""

        if outcome == "delete":
            await self.parent.bot.database.hematurgy.delete_passive(self.parent.user_id, self.slot_type)
            footer = "☣️ Mutation: the passive was consumed by the blood... it's gone."

        elif outcome == "downgrade":
            current_tier = passive["tier"]
            if current_tier <= 1:
                await self.parent.bot.database.hematurgy.delete_passive(self.parent.user_id, self.slot_type)
                footer = "☣️ Mutation: the passive degraded past its limit and was destroyed."
            else:
                new_tier = current_tier - 1
                await self.parent.bot.database.hematurgy.set_passive(
                    self.parent.user_id, self.slot_type, passive["passive_id"], new_tier
                )
                footer = f"☣️ Mutation: the passive was weakened to Tier {new_tier}."

        elif outcome == "double":
            new_tier = min(5, passive["tier"] * 2)
            await self.parent.bot.database.hematurgy.set_passive(
                self.parent.user_id, self.slot_type, passive["passive_id"], new_tier
            )
            footer = f"☣️ Mutation: the passive surged to Tier {new_tier}!"

        else:  # new_passive
            owned = await self.parent.bot.database.hematurgy.get_unlocked_passive_ids(self.parent.user_id)
            new_id = HematurgyMechanics.get_random_mutative_passive(owned)
            if new_id is None:
                # All mutative passives already owned; fall back to delete
                await self.parent.bot.database.hematurgy.delete_passive(self.parent.user_id, self.slot_type)
                footer = "☣️ Mutation: no new forms available — the passive was dissolved."
            else:
                await self.parent.bot.database.hematurgy.set_passive(
                    self.parent.user_id, self.slot_type, new_id, 1
                )
                name = HematurgyMechanics.passive_display_name(new_id)
                footer = f"☣️ Mutation: the passive transformed into **{name}**!"

        self.parent.passives = await self.parent.bot.database.hematurgy.get_all_passives(self.parent.user_id)
        self.parent.blood = await self.parent.bot.database.hematurgy.get_blood(self.parent.user_id)
        self._build_buttons()

        embed = self.build_embed()
        embed.set_footer(text=footer)
        await interaction.edit_original_response(embed=embed, view=self)

    async def _back(self, interaction: Interaction):
        embed = _build_hematurgy_embed(self.parent.passives, self.parent.blood)
        await interaction.response.edit_message(embed=embed, view=self.parent)
        self.stop()


# ---------------------------------------------------------------------------
# Slot Select
# ---------------------------------------------------------------------------

class SlotSelect(ui.Select):
    def __init__(self, passives: dict):
        options = []
        for slot in _SLOT_ORDER:
            label = _SLOT_LABELS[slot]
            emoji = _SLOT_EMOJI[slot]
            if slot in passives:
                p = passives[slot]
                name = HematurgyMechanics.passive_display_name(p["passive_id"])
                desc = f"Tier {p['tier']}/5 — {name}"
            else:
                cost = SLOT_UNLOCK_COSTS[slot]
                desc = f"No passive — Unlock: {cost:,} Primordial"
            options.append(discord.SelectOption(label=label, description=desc[:100], value=slot, emoji=emoji))
        super().__init__(placeholder="Inspect a slot...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: Interaction):
        slot_type = self.values[0]
        detail_view = SlotDetailView(self.view, slot_type)
        await interaction.response.edit_message(embed=detail_view.build_embed(), view=detail_view)


# ---------------------------------------------------------------------------
# Main Hematurgy View
# ---------------------------------------------------------------------------

class HematurgyView(BaseView):
    def __init__(self, bot, parent: "BaseView", passives: dict, blood: dict):
        super().__init__(bot, parent=parent)
        self.consume_view = parent  # direct reference for the back button
        self.passives = passives
        self.blood = blood
        self._rebuild_select()

    def _rebuild_select(self):
        for item in self.children[:]:
            if isinstance(item, SlotSelect):
                self.remove_item(item)
        self.add_item(SlotSelect(self.passives))

    @ui.button(label="Transmute Blood", style=ButtonStyle.secondary, emoji="⚗️", row=1)
    async def transmute(self, interaction: Interaction, button: ui.Button):
        transmute_view = TransmuteSourceView(self)
        await interaction.response.edit_message(
            content="Select the **source** blood type to convert from:",
            embed=None,
            view=transmute_view,
        )

    @ui.button(label="Back to Consume", style=ButtonStyle.secondary, row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(
            embed=self.consume_view.build_embed(), view=self.consume_view
        )
        self.stop()


class TransmuteSourceView(BaseView):
    def __init__(self, parent: HematurgyView):
        super().__init__(parent.bot, parent=parent)
        self.parent = parent
        self.add_item(TransmuteSourceSelect())

    @ui.button(label="Cancel", style=ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(
            content=None,
            embed=_build_hematurgy_embed(self.parent.passives, self.parent.blood),
            view=self.parent,
        )
        self.stop()
