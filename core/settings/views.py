import discord
from discord import ButtonStyle, Interaction, ui


class SettingsView(ui.View):
    def __init__(self, bot, user_id: str, doors_status: bool, exp_protection: bool):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.doors_status = doors_status
        self.exp_protection = exp_protection
        self.rebuild_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    def rebuild_buttons(self):
        self.clear_items()

        doors_lbl = "Disable Boss Doors" if self.doors_status else "Enable Boss Doors"
        doors_style = ButtonStyle.danger if self.doors_status else ButtonStyle.success
        doors_btn = ui.Button(label=doors_lbl, style=doors_style, emoji="🚪", row=0)
        doors_btn.callback = self.toggle_doors
        self.add_item(doors_btn)

        exp_lbl = (
            "Disable EXP Protection" if self.exp_protection else "Enable EXP Protection"
        )
        exp_style = ButtonStyle.danger if self.exp_protection else ButtonStyle.success
        exp_btn = ui.Button(label=exp_lbl, style=exp_style, emoji="🛡️", row=1)
        exp_btn.callback = self.toggle_exp_protection
        self.add_item(exp_btn)

    def build_embed(self) -> discord.Embed:
        doors_str = "🟢 ENABLED" if self.doors_status else "🔴 DISABLED"
        exp_str = "🟢 ENABLED" if self.exp_protection else "🔴 DISABLED"

        desc = (
            "**🚪 Boss Doors** — {doors}\n"
            "When enabled, your keys and fragments will resonate, giving you a chance to "
            "encounter Boss Doors during regular `/combat`. Disable to bypass all boss "
            "encounters and fight only standard monsters (useful for Slayer tasks or general grinding).\n\n"
            "**🛡️ EXP Protection** — {exp}\n"
            "When enabled, you will still see experience rewards but will not actually gain it. "
            "Useful for staying at your current level."
        ).format(doors=doors_str, exp=exp_str)

        embed = discord.Embed(
            title="Settings", description=desc, color=discord.Color.blue()
        )
        return embed

    async def toggle_doors(self, interaction: Interaction):
        self.doors_status = not self.doors_status
        await self.bot.database.users.toggle_doors(self.user_id, self.doors_status)
        self.rebuild_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def toggle_exp_protection(self, interaction: Interaction):
        self.exp_protection = not self.exp_protection
        await self.bot.database.users.toggle_exp_protection(
            self.user_id, self.exp_protection
        )
        self.rebuild_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
