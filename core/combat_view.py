import discord
from discord.ui import Button, View

class CombatView(View):
    def __init__(self, user_id: str, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.action = None

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.danger, emoji="⚔️", custom_id="combat_attack")
    async def attack_button(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This action is not for you!", ephemeral=True)
            return
        self.action = "attack"
        self.stop()

    @discord.ui.button(label="Heal", style=discord.ButtonStyle.green, emoji="🩹", custom_id="combat_heal")
    async def heal_button(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This action is not for you!", ephemeral=True)
            return
        self.action = "heal"
        self.stop()

    @discord.ui.button(label="Auto", style=discord.ButtonStyle.blurple, emoji="⏩", custom_id="combat_auto")
    async def auto_button(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This action is not for you!", ephemeral=True)
            return
        self.action = "auto"
        self.stop()

    @discord.ui.button(label="Run", style=discord.ButtonStyle.grey, emoji="🏃", custom_id="combat_run")
    async def run_button(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This action is not for you!", ephemeral=True)
            return
        self.action = "run"
        self.stop()

class AscensionView(View):
    def __init__(self, user_id: str, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.action = None

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="✅", custom_id="ascension_accept")
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This action is not for you!", ephemeral=True)
            return
        self.action = "accept"
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="❌", custom_id="ascension_decline")
    async def decline_button(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This action is not for you!", ephemeral=True)
            return
        self.action = "decline"
        self.stop()

class DuelView(View):
    def __init__(self, challenger_id: str, challenged_id: str, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.challenger_id = challenger_id
        self.challenged_id = challenged_id
        self.action = None

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="✅", custom_id="duel_accept")
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.challenged_id:
            await interaction.response.send_message("This action is not for you!", ephemeral=True)
            return
        self.action = "accept"
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="❌", custom_id="duel_decline")
    async def decline_button(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.challenged_id:
            await interaction.response.send_message("This action is not for you!", ephemeral=True)
            return
        self.action = "decline"
        self.stop()

class DuelActionView(View):
    def __init__(self, user_id: str, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.action = None

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.danger, emoji="⚔️", custom_id="duel_hit")
    async def hit_button(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This action is not for you!", ephemeral=True)
            return
        self.action = "hit"
        self.stop()

    @discord.ui.button(label="Heal", style=discord.ButtonStyle.green, emoji="💖", custom_id="duel_heal")
    async def heal_button(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This action is not for you!", ephemeral=True)
            return
        self.action = "heal"
        self.stop()