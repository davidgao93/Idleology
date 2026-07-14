import csv
import re

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui
from discord.ui import Button, Modal, Select, TextInput

from core.base_view import BaseView
from core.character.tutorial import TutorialView
from core.emojis import GOLD_COIN, RUNE_REGRET
from core.images import DEFAULT_SILHOUETTE

_CLASS_DESCRIPTIONS = {
    "Artificer": "Inventor of arcane machinery",
    "Barb": "Primal warrior of raw fury",
    "Bard": "Weaver of music and magic",
    "Cleric": "Devout wielder of divine power",
    "Druid": "Guardian of nature's balance",
    "Fighter": "Seasoned veteran of countless battles",
    "Monk": "Master of mind and body",
    "Mystic": "Seeker of hidden knowledge",
    "Paladin": "Holy champion of justice",
    "Ranger": "Scout of the untamed wilds",
    "Rogue": "Shadow walker and opportunist",
    "Rune": "Inscriber of ancient rune magic",
    "Sorc": "Channeler of raw magical power",
    "Warlock": "Bound to a dark patron",
    "Wizard": "Scholar of the arcane arts",
    "Dragonborn": "Bearer of draconic heritage",
    "Drow": "Child of the sunless depths",
    "Elf": "Ancient and graceful forest dweller",
    "ElfMage": "Elven master of the arcane",
    "Gnome": "Small but endlessly inventive",
    "Orc": "Powerful warrior of ancestral pride",
}


class RegistrationView(BaseView):
    """
    Step 1: Gender Selection (Buttons)
    Step 2: Appearance Selection (Select Menu + Preview) -> Confirm Button
    Step 3: Ideology (Modal)
    """

    def __init__(self, bot, user_id, name):
        super().__init__(bot, user_id)
        self.name = name
        self.gender = None
        self.appearance_url = None

    def _load_appearances(self, gender_code: str):
        apps = []
        try:
            with open("assets/profiles.csv", mode="r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["Sex"].upper() == gender_code:
                        apps.append((row["Class"], row["URL"]))
        except Exception:
            pass
        return apps

    # --- STEP 1: GENDER SELECTION ---

    @discord.ui.button(label="Male", emoji="♂️", style=ButtonStyle.primary)
    async def male_btn(self, interaction: Interaction, button: Button):
        await self.process_gender(interaction, "M")

    @discord.ui.button(label="Female", emoji="♀️", style=ButtonStyle.danger)
    async def female_btn(self, interaction: Interaction, button: Button):
        await self.process_gender(interaction, "F")

    async def process_gender(self, interaction: Interaction, gender: str):
        self.gender = gender
        portraits = self._load_appearances(gender)

        self.clear_items()

        if not portraits:
            self.appearance_url = DEFAULT_SILHOUETTE
            confirm_btn = Button(label="Confirm Setup", style=ButtonStyle.success)
            confirm_btn.callback = self.on_confirm_appearance
            self.add_item(confirm_btn)
            await interaction.response.edit_message(view=self)
            return

        self.appearance_url = portraits[0][1]

        options = []
        for class_name, url in portraits[:25]:
            desc = _CLASS_DESCRIPTIONS.get(class_name, "A unique portrait")
            options.append(SelectOption(label=class_name, value=url, description=desc))

        select = Select(placeholder="Choose your portrait...", options=options)
        select.callback = self.on_select_appearance
        self.add_item(select)

        other_gender = "F" if gender == "M" else "M"
        other_label = "Switch to Female" if gender == "M" else "Switch to Male"
        other_emoji = "♀️" if gender == "M" else "♂️"

        async def _switch_cb(i: Interaction):
            await self.process_gender(i, other_gender)

        switch_btn = Button(
            label=other_label, emoji=other_emoji, style=ButtonStyle.secondary, row=1
        )
        switch_btn.callback = _switch_cb
        self.add_item(switch_btn)

        confirm_btn = Button(
            label="Confirm Appearance", style=ButtonStyle.success, row=1
        )
        confirm_btn.callback = self.on_confirm_appearance
        self.add_item(confirm_btn)

        gender_label = "Male" if gender == "M" else "Female"
        embed = interaction.message.embeds[0]
        embed.description = (
            f"Gender: **{gender_label}**\nSelect a portrait from the menu to preview it.\n\n"
            "*What is an ideology?* Your ideology is the creed you carry into the world. "
            "Name it, spread it, and recruit followers."
        )
        embed.set_image(url=self.appearance_url)

        await interaction.response.edit_message(embed=embed, view=self)

    # --- STEP 2: PREVIEW & CONFIRM ---

    async def on_select_appearance(self, interaction: Interaction):
        """Updates the embed image without progressing state."""
        self.appearance_url = interaction.data["values"][0]

        embed = interaction.message.embeds[0]
        embed.set_image(url=self.appearance_url)

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_confirm_appearance(self, interaction: Interaction):
        """Triggered when user is happy with the preview."""
        await interaction.response.send_modal(IdeologyModal(self))

    # --- FINALIZATION ---

    async def complete_registration(self, interaction: Interaction, ideology: str):
        await interaction.response.defer()
        sid = str(interaction.guild.id)

        # 0a. Guard against registering twice across servers (user_id is globally unique).
        existing_elsewhere = await self.bot.database.users.get_by_user_id(self.user_id)
        if existing_elsewhere:
            error_embed = discord.Embed(
                title="❌ Already Registered Elsewhere",
                description=(
                    "You already have an adventurer registered on another server. "
                    "Each account can only be active on one server at a time."
                ),
                color=discord.Color.red(),
            )
            self.clear_items()
            await interaction.edit_original_response(embed=error_embed, view=self)
            self.bot.state_manager.clear_active(self.user_id)
            self.stop()
            return

        # 0b. Enforce ideology uniqueness per server BEFORE writing anything to the DB.
        existing = await self.bot.database.social.get_all_by_server(sid)
        if ideology.strip().lower() in [i.lower() for i in existing]:
            error_embed = discord.Embed(
                title="❌ Ideology Name Taken",
                description=(
                    f'**"{ideology}"** already exists on this server.\n\n'
                    "Each ideology must be unique — it represents your creed and integrates "
                    "with your settlement. Please choose a different name."
                ),
                color=discord.Color.red(),
            )
            self.clear_items()
            retry_btn = ui.Button(
                label="Choose a Different Name", style=ButtonStyle.primary
            )
            retry_btn.callback = self.on_confirm_appearance
            self.add_item(retry_btn)
            await interaction.edit_original_response(embed=error_embed, view=self)
            return

        # 1. Register User
        await self.bot.database.users.register(
            self.user_id,
            sid,
            self.name,
            self.appearance_url,
            ideology,
        )

        # 2. Initialize Skills
        await self.bot.database.skills.initialize(self.user_id, sid, "mining", "iron")
        await self.bot.database.skills.initialize(
            self.user_id, sid, "fishing", "desiccated"
        )
        await self.bot.database.skills.initialize(
            self.user_id, sid, "woodcutting", "flimsy"
        )

        # 3. Starter Pack (potions are granted via /journey Level 1 claim)
        await self.bot.database.users.modify_gold(self.user_id, 200)

        # 4. Found the ideology — name is guaranteed unique at this point.
        await self.bot.database.social.create_ideology(self.user_id, sid, ideology)
        await self.bot.database.social.update_followers(ideology, 1)
        ideology_line = f"You have founded a new ideology: **{ideology}**!"

        embed = discord.Embed(title="Registration Complete! 🎉", color=0x00FF00)
        embed.set_thumbnail(url=self.appearance_url)
        embed.description = (
            f"Welcome, **{self.name}**! {ideology_line}\n\n"
            "**Your adventure begins now.**\n"
            "Use `/journey` to claim your starter rewards and see what awaits you as you grow stronger. "
            "Each milestone unlocks new systems and grants valuable items — start there first!"
        )

        # Hand off to the tutorial. State remains locked until the tutorial
        # finishes or times out — TutorialView clears it on _on_finish / on_timeout.
        tutorial = TutorialView(
            self.bot,
            self.user_id,
            str(interaction.guild.id),
            finish_embed=embed,
        )
        tutorial.message = self.message
        await self.message.edit(embed=tutorial.build_embed(), view=tutorial)
        self.stop()  # RegistrationView is done; do NOT clear state here


class IdeologyModal(Modal, title="Choose Your Path"):
    ideology = TextInput(
        label="Ideology Name",
        placeholder="e.g. The Order of the Flame",
        max_length=24,
        required=True,
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        val = self.ideology.value.strip()

        if not re.match(r"^[A-Za-z0-9\s]+$", val):
            return await interaction.response.send_message(
                "Invalid characters in ideology name.", ephemeral=True
            )

        await self.parent_view.complete_registration(interaction, val)


class StatInvestView(BaseView):
    """
    View for allocating passive points permanently into ATK / DEF / HP / Gold.
    Each point grants a 0.1% bonus multiplier to that stat in combat.
    A Rune of Regret can be consumed to remove 1 point from any stat.
    """

    _STAT_MAP = [
        ("atk", "⚔️ Attack", "atk"),
        ("def", "🛡️ Defence", "def"),
        ("hp", "❤️ Max HP", "hp"),
        ("gold", f"{GOLD_COIN} Gold Find", "gold"),
    ]

    def __init__(
        self, bot, user_id: str, server_id: str, data, currencies: dict | None = None
    ):
        super().__init__(bot, user_id, server_id)
        self._data = dict(data)  # sqlite3.Row → dict so .get() works
        if currencies:
            self._data.update(currencies)
        self._processing = False
        self._refund_mode = False
        self._rebuild()

    async def _refresh_data(self):
        self._data = dict(
            await self.bot.database.users.get(self.user_id, self.server_id)
        )
        all_currencies = await self.bot.database.users.get_all_currencies(self.user_id)
        self._data["passive_points"] = (
            all_currencies["passive_points"] if all_currencies else 0
        )
        self._data["rune_of_regret"] = (
            all_currencies["rune_of_regret"] if all_currencies else 0
        )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _rebuild(self):
        self.clear_items()
        points = self._data["passive_points"]
        runes = self._data.get("rune_of_regret", 0) or 0

        if self._refund_mode:
            # ── Refund-selection mode ──────────────────────────────────
            options = []
            for db_key, label, _ in self._STAT_MAP:
                invested = self._data.get(f"stat_invest_{db_key}", 0) or 0
                if invested > 0:
                    options.append(
                        discord.SelectOption(
                            label=label.split(" ", 1)[1],  # strip emoji
                            value=db_key,
                            description=f"Refund 1 of your {invested} {db_key.upper()} points",
                            emoji=label.split(" ", 1)[0],
                        )
                    )
            if options:
                sel = discord.ui.Select(
                    placeholder="Choose a stat to refund 1 point from…",
                    options=options,
                    row=0,
                )
                sel.callback = self._do_refund
                self.add_item(sel)
            cancel = discord.ui.Button(
                label="Cancel", style=discord.ButtonStyle.secondary, row=1
            )
            cancel.callback = self._cancel_refund
            self.add_item(cancel)
            return

        # ── Normal invest mode ─────────────────────────────────────────
        for db_key, label, _ in self._STAT_MAP:
            emoji_part, _, text_part = label.partition(" ")
            btn = discord.ui.Button(
                label=text_part,
                emoji=emoji_part,
                style=discord.ButtonStyle.blurple,
                disabled=points <= 0,
                row=0,
            )
            btn.callback = self._make_invest_cb(db_key)
            self.add_item(btn)

        rune_btn = discord.ui.Button(
            label=f"Rune of Regret ({runes})",
            emoji=RUNE_REGRET,
            style=discord.ButtonStyle.secondary,
            disabled=runes <= 0
            or not any(
                (self._data.get(f"stat_invest_{dk}", 0) or 0) > 0
                for dk, _, __ in self._STAT_MAP
            ),
            row=1,
        )
        rune_btn.callback = self._enter_refund_mode
        self.add_item(rune_btn)

        done_btn = discord.ui.Button(
            label="Done", style=discord.ButtonStyle.secondary, row=1
        )
        done_btn.callback = self._done
        self.add_item(done_btn)

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        pts = self._data["passive_points"]
        runes = self._data.get("rune_of_regret", 0) or 0

        desc = (
            f"**Passive Points available:** {pts}\n"
            f"**Runes of Regret:** {runes}\n\n"
            "Each point grants **+0.1%** of the chosen stat's flat value as a "
            "bonus in combat (e.g. ATK points grant % of flat ATK as bonus ATK).\n"
            "Use a **Rune of Regret** to reclaim 1 point from any stat."
        )
        if self._refund_mode:
            desc = (
                f"**Runes of Regret:** {runes}\n\nSelect a stat to remove 1 point from."
            )

        embed = discord.Embed(
            title="📊 Stat Allocation",
            description=desc,
            color=discord.Color.gold(),
        )

        total_invested = 0
        for db_key, label, _ in self._STAT_MAP:
            invested = self._data.get(f"stat_invest_{db_key}", 0) or 0
            total_invested += invested
            embed.add_field(
                name=label,
                value=f"**{invested}** pts → **+{invested * 0.1:.1f}%**",
                inline=True,
            )

        embed.set_footer(text=f"Total invested: {total_invested} pts")
        return embed

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _make_invest_cb(self, db_key: str):
        async def callback(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            self._processing = True
            await interaction.response.defer()

            ok = await self.bot.database.users.invest_stat_point(
                self.user_id, self.server_id, db_key
            )
            await self._refresh_data()
            if not ok:
                await interaction.followup.send(
                    "No passive points available!", ephemeral=True
                )
            self._rebuild()
            await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )
            self._processing = False

        return callback

    async def _enter_refund_mode(self, interaction: Interaction):
        self._refund_mode = True
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _cancel_refund(self, interaction: Interaction):
        self._refund_mode = False
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _do_refund(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        db_key = interaction.data["values"][0]
        ok = await self.bot.database.users.refund_stat_point(
            self.user_id, self.server_id, db_key
        )
        await self._refresh_data()
        self._refund_mode = False
        self._rebuild()

        msg = (
            "Refund successful!"
            if ok
            else "Refund failed — not enough invested or no Rune available."
        )
        await interaction.followup.send(msg, ephemeral=True)
        await interaction.edit_original_response(embed=self.build_embed(), view=self)
        self._processing = False

    async def _done(self, interaction: Interaction):
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
        self.stop()

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        await super().on_timeout()


class UnregisterView(BaseView):
    def __init__(self, bot, user_id: str, ideology: str):
        super().__init__(bot, user_id)
        self.ideology = ideology

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        embed = discord.Embed(
            title="Unregistration Cancelled",
            description="The request timed out. Your character remains safe.",
            color=discord.Color.light_grey(),
        )
        try:
            if self.message:
                await self.message.edit(embed=embed, view=None)
        except (discord.NotFound, discord.HTTPException):
            pass

    @ui.button(label="Confirm Retirement", style=ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: Interaction, button: ui.Button):
        # Delete all user data, including the ideology row (hard-deleted in unregister).
        # The ideology name is freed for others to use on this server.
        await self.bot.database.users.unregister(
            self.user_id, str(interaction.guild.id)
        )

        embed = discord.Embed(
            title="Retirement",
            description="You have been successfully unregistered. We hope to see you again.",
            color=0x00FF00,
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    @ui.button(label="Cancel", style=ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: Interaction, button: ui.Button):
        embed = discord.Embed(
            title="Good choice",
            description="Your story doesn't end here.",
            color=0x00FF00,
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
