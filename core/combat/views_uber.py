import discord
from discord import ui, ButtonStyle, Interaction
from core.models import Player, Monster
from core.combat.gen_mob import generate_uber_aphrodite
from core.combat import engine, ui as combat_ui
from core.combat.views import CombatView # Reuse the battle engine

class UberLobbyView(ui.View):
    def __init__(self, bot, user_id: str, server_id: str, player: Player, uber_data: dict, readiness_text: str):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.player = player
        self.uber_data = uber_data
        self.readiness_text = readiness_text
        self.sigils = uber_data['celestial_sigils']
        
        self.setup_ui()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        try: await self.message.edit(view=None)
        except: pass

    def setup_ui(self):
        self.clear_items()
        
        btn_start = ui.Button(
            label="Challenge Aphrodite", 
            style=ButtonStyle.danger if self.sigils >= 3 else ButtonStyle.secondary, 
            disabled=(self.sigils < 3),
            emoji="⚔️"
        )
        btn_start.callback = self.start_uber
        self.add_item(btn_start)
        
        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary)
        btn_close.callback = self.close_view
        self.add_item(btn_close)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🌌 The Celestial Apex", 
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url="https://i.imgur.com/LjE5VZF.png")
        
        desc = (
            "A chibi Aphrodite appears and says: ME HUNGRY, FEED ME SIGILS PWETTY PWEASE?.\n\n"
            f"**Entry Cost:** 3 Celestial Sigils\n"
            f"**Owned:** {self.sigils}\n\n"
            f"**Assessment:** {self.readiness_text}"
        )
        embed.description = desc
        
        # Show unlocks if applicable
        bp_status = "✅ Unlocked" if self.uber_data['celestial_blueprint_unlocked'] else "🔒 Locked"
        embed.add_field(name="Celestial Engrams", value=str(self.uber_data['celestial_engrams']), inline=True)
        embed.add_field(name="Settlement Blueprint", value=bp_status, inline=True)
        
        return embed

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()

    async def start_uber(self, interaction: Interaction):
        # 1. State Check
        if not await self.bot.check_is_active(interaction, self.user_id): return
        
        # 2. Final verify and deduct
        current_data = await self.bot.database.uber.get_uber_progress(self.user_id, self.server_id)
        if current_data['celestial_sigils'] < 3:
            return await interaction.response.send_message("You do not have enough Celestial Sigils.", ephemeral=True)
            
        await interaction.response.defer()
        
        await self.bot.database.uber.increment_sigils(self.user_id, self.server_id, -3)
        self.bot.state_manager.set_active(self.user_id, "uber_boss")

        # 3. Generate the Boss
        monster = Monster(name="", level=0, hp=0, max_hp=0, xp=0, attack=0, defence=0, modifiers=[], image="", flavor="")
        monster = await generate_uber_aphrodite(self.player, monster)

        # 4. Snapshot clean stats
        clean_stats = {
            'attack': self.player.base_attack,
            'defence': self.player.base_defence,
            'crit_target': self.player.base_crit_chance_target
        }

        # 5. Combat Initialization
        self.player.combat_ward = self.player.get_combat_ward_value()
        engine.apply_stat_effects(self.player, monster)
        start_logs = engine.apply_combat_start_passives(self.player, monster)

        # 6. Launch Combat View
        # We pass a flag 'is_uber=True' (we will handle the custom reward logic in CombatView shortly)
        monster.is_uber = True 
        
        embed = combat_ui.create_combat_embed(self.player, monster, start_logs, title_override=f"🌌 UBER ENCOUNTER")
        view = CombatView(self.bot, self.user_id, self.player, monster, start_logs, combat_phases=None, clean_stats=clean_stats)
        
        await interaction.edit_original_response(embed=embed, view=view)
        self.stop()