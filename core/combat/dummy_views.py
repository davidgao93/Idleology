import discord
from discord import ui, ButtonStyle, Interaction, SelectOption
from core.combat.dummy_engine import DummyEngine
from core.models import Monster
from core.combat.gen_mob import get_monster_mods, get_boss_mods, get_modifier_description

class DummyConfigView(ui.View):
    def __init__(self, bot, user_id, player):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.player = player
        
        # State
        self.level_offset = 0 # 0, 10, 20, 50
        self.active_mods = []
        
        self.update_components()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try: await self.message.edit(view=None)
        except: pass

    def get_dummy_level(self):
        return self.player.level + self.level_offset

    def build_embed(self, results=None):
        lvl = self.get_dummy_level()
        embed = discord.Embed(title="🥋 Combat Dojo", color=discord.Color.light_grey())
        
        settings_text = f"**Dummy Level:** {lvl} (Player {self.level_offset:+})\n"
        if self.active_mods:
            settings_text += f"**Active Mods:** {', '.join(self.active_mods)}"
        else:
            settings_text += "**Active Mods:** None"
            
        embed.description = settings_text
        embed.set_thumbnail(url="https://i.imgur.com/v1BrB1M.png") 

        if results:
            embed.color = discord.Color.green()
            res_text = (
                f"📊 Analysis (100 Turns)\n"
                f"**Total Damage:** {results.total_damage:,}\n"
                f"**DPS (Avg/Turn):** {results.average_damage:.1f}\n\n"
                f"**Accuracy:** {results.hits}% (Crit: {results.crits}%)\n"
                f"**Range:** {results.min_hit:,} - {results.max_hit:,}"
            )
            embed.add_field(name="Results", value=res_text, inline=False)
        else:
            embed.add_field(name="Instructions", value="Configure the dummy using the menus below, then press **Start Simulation**.", inline=False)

        return embed

    def update_components(self):
        self.clear_items()
        
        # 1. Level Presets
        options_lvl = [
            SelectOption(label="Same Level", value="0", description=f"Level {self.player.level}"),
            SelectOption(label="Level +10", value="10", description=f"Level {self.player.level + 10}"),
            SelectOption(label="Level +20", value="20", description=f"Level {self.player.level + 20}"),
            SelectOption(label="Level +50", value="50", description=f"Level {self.player.level + 50}"),
        ]
        sel_lvl = ui.Select(placeholder="Set Dummy Level...", options=options_lvl, row=0)
        sel_lvl.callback = self.level_callback
        self.add_item(sel_lvl)

        # 2. Modifiers (Filtered)
        all_mods = get_monster_mods()
        # Exclude mods that don't affect DPS calculations directly or are just flavor/level scaling
        exclude = ["Built-different", "Glutton", "Vampiric", "Summoner", "Executioner", "Time Lord", "Hellborn", "Enfeeble", "Venomous"] 
        valid_mods = [m for m in all_mods if m not in exclude][:25] 
        
        options_mod = [SelectOption(label=m, value=m, description=get_modifier_description(m)[:100]) for m in valid_mods]
        sel_mod = ui.Select(placeholder="Add Modifier...", options=options_mod, row=1)
        sel_mod.callback = self.mod_callback
        self.add_item(sel_mod)

        # 3. Boss Mods
        all_boss = get_boss_mods()
        exclude_boss = ["Unlimited Blade Works", "Hell's Fury", "Infernal Legion"] # Damage dealing mods
        valid_boss = [m for m in all_boss if m not in exclude_boss][:25]
        
        options_boss = [SelectOption(label=m, value=m) for m in valid_boss]
        sel_boss = ui.Select(placeholder="Add Boss Modifier...", options=options_boss, row=2)
        sel_boss.callback = self.mod_callback 
        self.add_item(sel_boss)

        # 4. Actions
        btn_start = ui.Button(label="Start Simulation", style=ButtonStyle.success, emoji="⚔️", row=3)
        btn_start.callback = self.run_sim
        self.add_item(btn_start)

        btn_clear = ui.Button(label="Clear Mods", style=ButtonStyle.secondary, row=3)
        btn_clear.callback = self.clear_mods
        self.add_item(btn_clear)
        
        btn_exit = ui.Button(label="Exit", style=ButtonStyle.danger, row=3)
        btn_exit.callback = self.close_view
        self.add_item(btn_exit)

    async def level_callback(self, interaction: Interaction):
        self.level_offset = int(interaction.data['values'][0])
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def mod_callback(self, interaction: Interaction):
        mod = interaction.data['values'][0]
        if mod not in self.active_mods:
            self.active_mods.append(mod)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def clear_mods(self, interaction: Interaction):
        self.active_mods = []
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def run_sim(self, interaction: Interaction):
        # Create Dummy
        lvl = self.get_dummy_level()
        atk = int(lvl * 1.3)
        defn = int(lvl * 1.3)
        
        # Apply Mod effects to base stats manually 
        if "Steel-born" in self.active_mods: defn = int(defn * 1.1)
        if "Mighty" in self.active_mods: atk = int(atk * 1.1)
        if "Ascended" in self.active_mods: 
            atk += 10
            defn += 10
        if "Absolute" in self.active_mods:
            atk += 25
            defn += 25

        monster = Monster(
            name="Combat Dummy",
            level=lvl,
            hp=9999999, max_hp=9999999, xp=0,
            attack=atk, defence=defn,
            modifiers=self.active_mods,
            image="", flavor=""
        )

        results = DummyEngine.run_simulation(self.player, monster, turns=100)
        await interaction.response.edit_message(embed=self.build_embed(results=results), view=self)

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()