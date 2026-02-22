import discord
from discord import ui, ButtonStyle, Interaction
from datetime import datetime, timedelta
from core.combat import engine
from core.companions.logic import CompanionLogic
from core.settlement.mechanics import SettlementMechanics
from core.items.factory import load_player

class ProfileBuilder:
    """Static builder class that generates the embeds for the Profile Hub."""
    
    @staticmethod
    async def build_card(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)
        followers = await bot.database.social.get_follower_count(user[8])
        
        embed = discord.Embed(title=f"Adventurer License", color=discord.Color.gold())
        embed.set_thumbnail(url=user[7])
        
        embed.add_field(name="Name", value=f"**{user[3]}**", inline=True)
        embed.add_field(name="Level", value=f"{user[4]} (Ascension {user[15]})", inline=True)
        embed.add_field(name="Experience", value=f"{user[5]:,}", inline=True)
        
        embed.add_field(name="Ideology", value=f"{user[8]}", inline=True)
        embed.add_field(name="Followers", value=f"{followers:,}", inline=True)
        embed.add_field(name="Gold", value=f"{user[6]:,} 💰", inline=True)
        
        return embed

    @staticmethod
    async def build_stats(bot, user_id: str, server_id: str) -> discord.Embed:
        data = await bot.database.users.get(user_id, server_id)
        p = await load_player(user_id, data, bot.database)
        
        embed = discord.Embed(title=f"Combat Statistics", color=0x00FF00)
        embed.set_thumbnail(url=data[7])

        atk_bonus = p.get_total_attack() - p.base_attack
        def_bonus = p.get_total_defence() - p.base_defence
        
        embed.add_field(name="⚔️ Attack", value=f"{p.base_attack} (+{atk_bonus})" if atk_bonus > 0 else str(p.base_attack), inline=True)
        embed.add_field(name="🛡️ Defence", value=f"{p.base_defence} (+{def_bonus})" if def_bonus > 0 else str(p.base_defence), inline=True)
        embed.add_field(name="❤️ HP", value=f"{p.current_hp}/{p.max_hp}", inline=True)
        
        ward = p.get_total_ward_percentage()
        if ward > 0: embed.add_field(name="🔮 Ward", value=f"{ward}%", inline=True)
        
        crit_chance = 100 - p.get_current_crit_target()
        if crit_chance > 5: embed.add_field(name="🎯 Crit Chance", value=f"{crit_chance}%", inline=True)
        
        pdr = p.get_total_pdr()
        if pdr > 0: embed.add_field(name="🛡️ PDR", value=f"{pdr}%", inline=True)

        fdr = p.get_total_fdr()
        if fdr > 0: embed.add_field(name="🛡️ FDR", value=f"{fdr}", inline=True)

        rarity = p.get_total_rarity()
        if rarity > 0: embed.add_field(name="✨ Rarity", value=f"{rarity}%", inline=True)

        passives = []
        if p.equipped_weapon:
            p_list = [passive.title() for passive in [p.equipped_weapon.passive, p.equipped_weapon.p_passive, p.equipped_weapon.u_passive] if passive != 'none']
            if p_list: passives.append(f"**Weapon:** {', '.join(p_list)}")
        if p.equipped_armor and p.equipped_armor.passive != 'none':
            passives.append(f"**Armor:** {p.equipped_armor.passive.title()}")
        if p.equipped_accessory and p.equipped_accessory.passive != 'none':
            passives.append(f"**Accessory:** {p.equipped_accessory.passive.title()} ({p.equipped_accessory.passive_lvl})")
        if p.equipped_glove and p.equipped_glove.passive != 'none':
            passives.append(f"**Glove:** {p.equipped_glove.passive.title()} ({p.equipped_glove.passive_lvl})")
        if p.equipped_boot and p.equipped_boot.passive != 'none':
            passives.append(f"**Boot:** {p.equipped_boot.passive.title()} ({p.equipped_boot.passive_lvl})")
        if p.equipped_helmet and p.equipped_helmet.passive != 'none':
            passives.append(f"**Helmet:** {p.equipped_helmet.passive.title()} ({p.equipped_helmet.passive_lvl})")
        
        if passives:
            embed.add_field(name="__Active Passives__", value="\n".join(passives), inline=False)
        return embed

    @staticmethod
    async def build_inventory(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)
        
        w_count = await bot.database.equipment.get_count(user_id, 'weapon')
        a_count = await bot.database.equipment.get_count(user_id, 'accessory')
        ar_count = await bot.database.equipment.get_count(user_id, 'armor')
        g_count = await bot.database.equipment.get_count(user_id, 'glove')
        b_count = await bot.database.equipment.get_count(user_id, 'boot')
        h_count = await bot.database.equipment.get_count(user_id, 'helmet')
        pet_count = await bot.database.companions.get_count(user_id)

        k_balance = await bot.database.users.get_currency(user_id, 'balance_fragment')
        r_partner = await bot.database.users.get_currency(user_id, 'partnership_runes')

        embed = discord.Embed(title=f"Inventory Summary", description=f"💰 **Gold:** {user[6]:,}\n🧪 **Potions:** {user[16]:,}", color=0x00FF00)
        embed.set_thumbnail(url=user[7])

        embed.add_field(name="📦 **Equipment**", 
            value=(f"⚔️ Weapons: {w_count}/60\n🛡️ Armor: {ar_count}/60\n📿 Accessories: {a_count}/60\n"
                   f"🧤 Gloves: {g_count}/60\n👢 Boots: {b_count}/60\n🪖 Helmets: {h_count}/60\n🐾 Companions: {pet_count}/20"), inline=True)

        embed.add_field(name="💎 **Runes**", 
            value=(f"🔨 Refinement: {user[19]}\n✨ Potential: {user[21]}\n🔮 Imbuing: {user[27]}\n"
                   f"💥 Shatter: {user[31]}\n🤝 Partnership: {r_partner}"), inline=True)

        embed.add_field(name="🔑 **Key Items**", 
            value=(f"🐉 Draconic Keys: {user[25]}\n🪽 Angelic Keys: {user[26]}\n🗝️ Void Keys: {user[30]}\n"
                   f"⚖️ Balance Frags: {k_balance}\n❤️‍🔥 Soul Cores: {user[28]}\n🟣 Void Frags: {user[29]}\n🎁 Curios: {user[22]}"), inline=True)
        return embed

    @staticmethod
    async def build_cooldowns(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)
        p = await load_player(user_id, user, bot.database)
        
        # 1. Combat Cooldown (Calculate Speedster Passive)
        combat_cd_mins = 10
        if p.equipped_boot and p.equipped_boot.passive == "speedster":
            combat_cd_mins -= p.equipped_boot.passive_lvl
        
        def get_remaining(time_str, cooldown_td: timedelta):
            if not time_str: return "Ready!"
            try:
                last = datetime.fromisoformat(time_str)
                diff = datetime.now() - last
                if diff < cooldown_td:
                    rem = cooldown_td - diff
                    return f"**{rem.seconds // 3600}h {(rem.seconds // 60) % 60}m {rem.seconds % 60}s**"
                return "Ready!"
            except: return "Ready!"

        embed = discord.Embed(title="Active Timers & Cooldowns", color=0xBEBEFE)
        embed.set_thumbnail(url=user[7])
        
        # Standard Cooldowns
        embed.add_field(name="/combat ⚔️", value=get_remaining(user[24], timedelta(minutes=combat_cd_mins)), inline=True)
        embed.add_field(name="/rest 🛏️", value=get_remaining(user[13], timedelta(hours=2)), inline=True)
        embed.add_field(name="/checkin 🛖", value=get_remaining(user[17], timedelta(hours=18)), inline=True)
        embed.add_field(name="/propagate 💡", value=get_remaining(user[14], timedelta(hours=18)), inline=True)

        # 2. Settlement Production
        settlement = await bot.database.settlement.get_settlement(user_id, server_id)
        if settlement and settlement.last_collection_time:
            try:
                s_last = datetime.fromisoformat(settlement.last_collection_time)
                s_diff = datetime.now() - s_last
                s_hours = s_diff.total_seconds() / 3600
                embed.add_field(
                    name="🏭 Settlement", 
                    value=f"**{s_hours:.2f}** hours of production pending.", 
                    inline=False
                )
            except Exception: pass

        # 3. Companion Adventures
        active_comps = await bot.database.companions.get_active(user_id)
        if not active_comps:
            embed.add_field(name="🐾 Companions", value="No active companions deployed.", inline=False)
        else:
            # Fetch the collection timer specifically
            cursor = await bot.database.connection.execute(
                "SELECT last_companion_collect_time FROM users WHERE user_id = ?", (user_id,)
            )
            res = await cursor.fetchone()
            c_time_str = res[0] if res else None
            
            if c_time_str:
                try:
                    c_last = datetime.fromisoformat(c_time_str)
                    c_diff = (datetime.now() - c_last).total_seconds()
                    
                    cycles = int(c_diff // 1800) # 30 mins per cycle
                    
                    if cycles >= 48:
                        embed.add_field(name="🐾 Companions", value="**48/48** adventures completed! (MAXED)\nWaiting to be collected.", inline=False)
                    else:
                        next_cycle_rem = 1800 - (c_diff % 1800)
                        next_cycle_str = f"({int(next_cycle_rem // 60)}m {int(next_cycle_rem % 60)}s until next)"
                        embed.add_field(name="🐾 Companions", value=f"**{cycles}/48** adventures completed.\n{next_cycle_str}", inline=False)
                except Exception:
                    embed.add_field(name="🐾 Companions", value="Ready to deploy.", inline=False)
            else:
                embed.add_field(name="🐾 Companions", value="Ready to deploy.", inline=False)

        return embed

    @staticmethod
    async def build_resources(bot, user_id: str, server_id: str) -> discord.Embed:
        settlement = await bot.database.settlement.get_settlement(user_id, server_id)
        
        async with bot.database.connection.execute("SELECT iron_bar, steel_bar, gold_bar, platinum_bar, idea_bar FROM mining WHERE user_id=? AND server_id=?", (user_id, server_id)) as c:
            ingots = await c.fetchone() or (0,0,0,0,0)
        async with bot.database.connection.execute("SELECT oak_plank, willow_plank, mahogany_plank, magic_plank, idea_plank FROM woodcutting WHERE user_id=? AND server_id=?", (user_id, server_id)) as c:
            planks = await c.fetchone() or (0,0,0,0,0)
        async with bot.database.connection.execute("SELECT desiccated_essence, regular_essence, sturdy_essence, reinforced_essence, titanium_essence FROM fishing WHERE user_id=? AND server_id=?", (user_id, server_id)) as c:
            essence = await c.fetchone() or (0,0,0,0,0)
        async with bot.database.connection.execute("SELECT magma_core, life_root, spirit_shard FROM users WHERE user_id=?", (user_id,)) as c:
            rares = await c.fetchone() or (0,0,0)

        embed = discord.Embed(title="Storage Warehouse", color=discord.Color.dark_orange())
        embed.add_field(name="🏭 Settlement", value=f"🪵 Timber: {settlement.timber:,}\n🪨 Stone: {settlement.stone:,}", inline=False)
        embed.add_field(name="🧱 Ingots", value=f"Iron: {ingots[0]}\nSteel: {ingots[1]}\nGold: {ingots[2]}\nPlat: {ingots[3]}\nIdea: {ingots[4]}", inline=True)
        embed.add_field(name="🪵 Planks", value=f"Oak: {planks[0]}\nWillow: {planks[1]}\nMahog: {planks[2]}\nMagic: {planks[3]}\nIdea: {planks[4]}", inline=True)
        embed.add_field(name="⚗️ Essence", value=f"Desic: {essence[0]}\nReg: {essence[1]}\nSturdy: {essence[2]}\nReinf: {essence[3]}\nTitan: {essence[4]}", inline=True)
        embed.add_field(name="✨ Rare Materials", value=f"🔥 Magma Core: {rares[0]}\n🌿 Life Root: {rares[1]}\n👻 Spirit Shard: {rares[2]}", inline=False)
        return embed


class ProfileHubView(ui.View):
    def __init__(self, bot, user_id: str, server_id: str, active_tab: str):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.active_tab = active_tab
        self.update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        try:
            for child in self.children:
                child.disabled = True
            await self.message.edit(view=self)
        except: pass

    def update_buttons(self):
        self.clear_items()
        
        tabs = [
            ("card", "Card", "👤"),
            ("stats", "Stats", "📊"),
            ("inventory", "Inventory", "🎒"),
            ("cooldowns", "Cooldowns", "⏰"),
            ("resources", "Resources", "📦")
        ]
        
        for tab_id, label, emoji in tabs:
            style = ButtonStyle.primary if self.active_tab == tab_id else ButtonStyle.secondary
            btn = ui.Button(label=label, emoji=emoji, style=style, custom_id=tab_id)
            btn.callback = self.handle_tab_switch
            self.add_item(btn)

    async def handle_tab_switch(self, interaction: Interaction):
        tab_id = interaction.data["custom_id"]
        if tab_id == self.active_tab:
            return await interaction.response.defer()
            
        self.active_tab = tab_id
        self.update_buttons()
        await interaction.response.defer()
        
        # Build new embed based on selected tab
        embed = None
        if tab_id == "card": embed = await ProfileBuilder.build_card(self.bot, self.user_id, self.server_id)
        elif tab_id == "stats": embed = await ProfileBuilder.build_stats(self.bot, self.user_id, self.server_id)
        elif tab_id == "inventory": embed = await ProfileBuilder.build_inventory(self.bot, self.user_id, self.server_id)
        elif tab_id == "cooldowns": embed = await ProfileBuilder.build_cooldowns(self.bot, self.user_id, self.server_id)
        elif tab_id == "resources": embed = await ProfileBuilder.build_resources(self.bot, self.user_id, self.server_id)

        await interaction.edit_original_response(embed=embed, view=self)