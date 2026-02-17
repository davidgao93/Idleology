import discord
from discord import ui, ButtonStyle, Interaction
from core.minigames.mechanics import DelveMechanics, DelveState

class DelveView(ui.View):
    def __init__(self, bot, user_id, server_id, state: DelveState, stats: dict):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.state = state
        self.stats = stats # {fuel_lvl, struct_lvl, sensor_lvl}
        
        # Pre-generate next 10 layers if empty
        self._expand_map()
        self.update_buttons()

    def _expand_map(self):
        while len(self.state.hazards) < self.state.depth + 10:
            self.state.hazards.append(DelveMechanics.generate_layer(len(self.state.hazards)))

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        # Auto-fail if abandoned deep underground
        self.bot.state_manager.clear_active(self.user_id)
        if self.state.depth > 0:
            try: await self.message.edit(content="⚠️ **Signal Lost.** The mine collapsed while you were idle.", view=None, embed=None)
            except: pass

    def update_buttons(self):
        # Drill: Always enabled unless dead
        self.children[0].disabled = False
        
        # Survey: Requires Fuel
        survey_cost = 2
        self.children[1].disabled = self.state.current_fuel < survey_cost
        
        # Reinforce: Requires Fuel and Stability < 100
        reinf_cost = 5
        self.children[2].disabled = (self.state.current_fuel < reinf_cost) or (self.state.stability >= 100)
        
        # Extract: Requires Depth > 0
        self.children[3].disabled = self.state.depth == 0

    def build_embed(self, last_action: str = "") -> discord.Embed:
        # Visual Bars
        stab_fill = int(self.state.stability / 10)
        stab_bar = "▓" * stab_fill + "░" * (10 - stab_fill)
        stab_color = "🟢" if self.state.stability > 50 else ("🟡" if self.state.stability > 20 else "🔴")
        
        fuel_fill = int((self.state.current_fuel / self.state.max_fuel) * 10)
        fuel_bar = "⚡" * fuel_fill + "⚫" * (10 - fuel_fill)

        embed = discord.Embed(title=f"⛏️ Deep Delve (Depth: {self.state.depth})", color=discord.Color.dark_grey())
        
        status = (f"**Structure:** `{stab_bar}` {self.state.stability}%\n"
                  f"**Fuel:** {fuel_bar} ({self.state.current_fuel}/{self.state.max_fuel})")
        
        embed.add_field(name="Status", value=status, inline=False)
        
        # Scanner Visuals
        scan_text = ""
        range_val = DelveMechanics.get_survey_range(self.stats['sensor_lvl'])
        
        for i in range(1, range_val + 1):
            idx = self.state.depth + i
            if idx in self.state.revealed_indices:
                hazard = self.state.hazards[idx]
                icon = "🟢" if hazard == "Safe" else ("🪨" if hazard == "Gravel" else ("☣️" if hazard == "Gas Pocket" else "🔥"))
                scan_text += f"`Depth {idx}:` {icon} **{hazard}**\n"
            else:
                scan_text += f"`Depth {idx}:` ❓ Unknown\n"
        
        embed.add_field(name=f"Scanner (Lvl {self.stats['sensor_lvl']})", value=scan_text, inline=False)
        
        loot = f"🎁 Curios: **{self.state.curios_found}**\n💎 Shards: **{self.state.shards_found}**"
        embed.add_field(name="Cargo", value=loot, inline=True)
        
        if last_action:
            embed.set_footer(text=last_action)
            
        return embed

    # --- ACTIONS ---

    @ui.button(label="Drill (-1 Fuel)", style=ButtonStyle.primary, emoji="⛏️", row=0)
    async def drill(self, interaction: Interaction, button: ui.Button):
        # Cost
        self.state.current_fuel -= 1
        self.state.depth += 1
        
        # Hazard
        self._expand_map()
        hazard = self.state.hazards[self.state.depth]
        dmg = DelveMechanics.calculate_damage(hazard, self.state.pickaxe_tier)
        self.state.stability = max(0, self.state.stability - dmg)
        
        msg = f"Drilled to Depth {self.state.depth}."
        if dmg > 0: msg += f" Hit {hazard}! -{dmg}% Stability."
        
        # Rewards
        c, s = DelveMechanics.check_rewards(self.state.depth)
        if c > 0: msg += f" Found {c} Curio!"
        if s > 0: msg += f" Found {s} Shards!"
        self.state.curios_found += c
        self.state.shards_found += s

        # Check Fail
        if self.state.stability <= 0:
            await self.game_over(interaction, "collapse")
        elif self.state.current_fuel <= 0:
            await self.game_over(interaction, "fuel")
        else:
            self.update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(msg), view=self)

    @ui.button(label="Survey (-2 Fuel)", style=ButtonStyle.secondary, emoji="📡", row=0)
    async def survey(self, interaction: Interaction, button: ui.Button):
        self.state.current_fuel -= 2
        
        # Reveal range based on level
        r = DelveMechanics.get_survey_range(self.stats['sensor_lvl'])
        for i in range(1, r + 1):
            self.state.revealed_indices.append(self.state.depth + i)
            
        if self.state.current_fuel <= 0:
            await self.game_over(interaction, "fuel")
        else:
            self.update_buttons()
            await interaction.response.edit_message(embed=self.build_embed("Scanners activated."), view=self)

    @ui.button(label="Reinforce (-5 Fuel)", style=ButtonStyle.success, emoji="🏗️", row=1)
    async def reinforce(self, interaction: Interaction, button: ui.Button):
        self.state.current_fuel -= 5
        amt = DelveMechanics.get_reinforce_power(self.stats['struct_lvl'])
        self.state.stability = min(100, self.state.stability + amt)
        
        if self.state.current_fuel <= 0:
            await self.game_over(interaction, "fuel")
        else:
            self.update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(f"Reinforced structure (+{amt}%)."), view=self)

    @ui.button(label="Extract", style=ButtonStyle.danger, emoji="🚀", row=1)
    async def extract(self, interaction: Interaction, button: ui.Button):
        await self.game_over(interaction, "extract")

    async def game_over(self, interaction: Interaction, reason: str):
        embed = None
        if reason == "collapse":
            embed = discord.Embed(title="💥 MINE COLLAPSED", description="You died in the depths.", color=discord.Color.red())
            embed.add_field(name="Lost Cargo", value=f"🎁 {self.state.curios_found} Curios\n💎 {self.state.shards_found} Shards")
            # Logic: Lose everything (or half? Strictrogue-like usually implies loss)
            # Let's say lose everything for high stakes.
        elif reason == "fuel":
            embed = discord.Embed(title="⚡ OUT OF FUEL", description="Life support failed.", color=discord.Color.red())
            embed.add_field(name="Lost Cargo", value=f"🎁 {self.state.curios_found} Curios\n💎 {self.state.shards_found} Shards")
        else:
            # Success
            embed = discord.Embed(title="✅ EXTRACTION SUCCESSFUL", color=discord.Color.green())
            embed.description = f"Reached Depth **{self.state.depth}**."
            
            # DB Commit
            if self.state.curios_found > 0:
                await self.bot.database.users.modify_currency(self.user_id, 'curios', self.state.curios_found)
            if self.state.shards_found > 0:
                await self.bot.database.delve.modify_shards(self.user_id, self.server_id, self.state.shards_found)
            
            # XP Gain (Depth = XP)
            await self.bot.database.delve.add_xp(self.user_id, self.server_id, self.state.depth)
            
            embed.add_field(name="Loot Secured", value=f"🎁 **{self.state.curios_found}** Curios\n💎 **{self.state.shards_found}** Obsidian Shards", inline=False)
            embed.add_field(name="Progression", value=f"📈 +{self.state.depth} Delve XP")

        await interaction.response.edit_message(embed=embed, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

class DelveUpgradeView(ui.View):
    def __init__(self, bot, user_id, server_id, stats):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.stats = stats # dict from repo
        self.update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    def update_buttons(self):
        shards = self.stats['shards']
        
        # Fuel
        fuel_cost = DelveMechanics.get_upgrade_cost(self.stats['fuel_lvl'])
        self.children[0].label = f"Fuel Lvl {self.stats['fuel_lvl']} ({fuel_cost} 💎)"
        self.children[0].disabled = shards < fuel_cost or self.stats['fuel_lvl'] >= 10

        # Reinforce
        struct_cost = DelveMechanics.get_upgrade_cost(self.stats['struct_lvl'])
        self.children[1].label = f"Struct Lvl {self.stats['struct_lvl']} ({struct_cost} 💎)"
        self.children[1].disabled = shards < struct_cost or self.stats['struct_lvl'] >= 10

        # Sensor
        sensor_cost = DelveMechanics.get_upgrade_cost(self.stats['sensor_lvl'])
        self.children[2].label = f"Sensor Lvl {self.stats['sensor_lvl']} ({sensor_cost} 💎)"
        self.children[2].disabled = shards < sensor_cost or self.stats['sensor_lvl'] >= 10

    async def _upgrade(self, interaction, stat_key, db_col):
        cost = DelveMechanics.get_upgrade_cost(self.stats[stat_key])
        await self.bot.database.delve.upgrade_stat(self.user_id, self.server_id, db_col, cost)
        
        # Update local
        self.stats['shards'] -= cost
        self.stats[stat_key] += 1
        
        self.update_buttons()
        embed = interaction.message.embeds[0]
        embed.description = f"💎 **Obsidian Shards:** {self.stats['shards']}"
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(style=ButtonStyle.primary, row=0)
    async def up_fuel(self, interaction: Interaction, button: ui.Button):
        await self._upgrade(interaction, 'fuel_lvl', 'fuel_level')

    @ui.button(style=ButtonStyle.secondary, row=0)
    async def up_struct(self, interaction: Interaction, button: ui.Button):
        await self._upgrade(interaction, 'struct_lvl', 'struct_level')

    @ui.button(style=ButtonStyle.success, row=1)
    async def up_sensor(self, interaction: Interaction, button: ui.Button):
        await self._upgrade(interaction, 'sensor_lvl', 'sensor_level')

    @ui.button(label="Done", style=ButtonStyle.danger, row=1)
    async def close(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()