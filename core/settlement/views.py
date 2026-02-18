import discord
from discord import ui, ButtonStyle, Interaction, SelectOption
from datetime import datetime
from core.models import Settlement, Building
from core.settlement.mechanics import SettlementMechanics

class SettlementDashboardView(ui.View):
    def __init__(self, bot, user_id, server_id, settlement: Settlement, follower_count: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.settlement = settlement
        self.follower_count = follower_count
        
        self.update_grid()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try: await self.message.edit(view=None)
        except: pass

    def build_embed(self) -> discord.Embed:
        workers_used = sum(b.workers_assigned for b in self.settlement.buildings)
        
        embed = discord.Embed(title="Town Hall", color=discord.Color.dark_green())
        embed.description = (
            f"**Tier {self.settlement.town_hall_tier}** Settlement\n"
            f"👥 **Workforce:** {workers_used}/{self.follower_count}\n"
            f"🪵 **Timber:** {self.settlement.timber:,}\n"
            f"🪨 **Stone:** {self.settlement.stone:,}"
        )
        embed.set_thumbnail(url="https://i.imgur.com/xNY7tPj.png")
        
        # Calculate Pending Resources (Visual Only)
        now = datetime.now()
        last = datetime.fromisoformat(self.settlement.last_collection_time)
        hours = (now - last).total_seconds() / 3600
        
        if hours > 0.1:
            pending_txt = ""
            for b in self.settlement.buildings:
                # Mock calculation for display (simplified, real calc handles limits)
                if b.workers_assigned > 0:
                    b_data = SettlementMechanics.BUILDINGS.get(b.building_type)
                    rate = int(b_data['base_rate'] * b.tier * b.workers_assigned)
                    pending_txt += f"• {b.name}: ~{int(rate * hours)} output\n"
            
            if pending_txt:
                embed.add_field(name="Pending Production", value=pending_txt, inline=False)

        return embed

    def update_grid(self):
        self.clear_items()
        
        # 1. Building Slots
        # We display up to the max slots allowed by Town Hall
        # Map existing buildings to their slot index
        built_map = {b.slot_index: b for b in self.settlement.buildings}
        
        for i in range(self.settlement.building_slots):
            row = i // 3
            if i in built_map:
                b = built_map[i]
                status = "🟢" if b.workers_assigned > 0 else "🔴"
                btn = ui.Button(label=f"{b.name} (T{b.tier}) {status}", style=ButtonStyle.secondary, row=row)
                btn.callback = lambda inter, b=b: self.open_building(inter, b)
            else:
                btn = ui.Button(label="[ Empty Lot ]", style=ButtonStyle.gray, row=row)
                btn.callback = lambda inter, slot=i: self.open_build_menu(inter, slot)
            self.add_item(btn)

        # 2. Controls
        collect_btn = ui.Button(label="Collect Resources", style=ButtonStyle.success, row=3, emoji="🚜")
        collect_btn.callback = self.collect_resources
        self.add_item(collect_btn)
        
        close_btn = ui.Button(label="Close", style=ButtonStyle.danger, row=3)
        close_btn.callback = self.close_view
        self.add_item(close_btn)

    async def open_build_menu(self, interaction: Interaction, slot_index: int):
        view = BuildConstructionView(self.bot, self.user_id, slot_index, self)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def open_building(self, interaction: Interaction, building: Building):
        view = BuildingDetailView(self.bot, self.user_id, building, self)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def collect_resources(self, interaction: Interaction):
        await interaction.response.defer()
        
        # 1. Fetch Inventory for limiting logic
        uid, sid = self.user_id, self.server_id
        # We need raw materials to calc conversion limits
        # Simplified fetch for brevity; ideally repo method
        mining = await self.bot.database.skills.get_data(uid, sid, 'mining')
        wood = await self.bot.database.skills.get_data(uid, sid, 'woodcutting')
        fish = await self.bot.database.skills.get_data(uid, sid, 'fishing')
        
        raw_inv = {
            'iron': mining[3], 'coal': mining[4], 'gold': mining[5], 'platinum': mining[6], 'idea': mining[7],
            'oak_logs': wood[3], 'willow_logs': wood[4], 'mahogany_logs': wood[5], 'magic_logs': wood[6], 'idea_logs': wood[7],
            'desiccated_bones': fish[3], 'regular_bones': fish[4], 'sturdy_bones': fish[5], 'reinforced_bones': fish[6], 'titanium_bones': fish[7]
        }

        # 2. Calculate Time
        now = datetime.now()
        last = datetime.fromisoformat(self.settlement.last_collection_time)
        hours = (now - last).total_seconds() / 3600
        
        if hours < 0.1: # Minimum 6 minutes
            return await interaction.followup.send("Production cycle not yet complete.", ephemeral=True)

        # 3. Calculate Changes
        total_changes = {}
        for b in self.settlement.buildings:
            changes = SettlementMechanics.calculate_production(
                b.building_type, b.tier, b.workers_assigned, hours, raw_inv
            )
            # Merge changes
            for k, v in changes.items():
                total_changes[k] = total_changes.get(k, 0) + v
                # Temporarily update raw_inv so next building in loop sees reduced stock
                if k in raw_inv: raw_inv[k] += v # v is negative for consumption

        # 4. Commit
        await self.bot.database.settlement.commit_production(uid, sid, total_changes)
        await self.bot.database.settlement.update_collection_timer(uid, sid)
        
        # 5. Update Local State & Refresh
        self.settlement.timber += total_changes.get('timber', 0)
        self.settlement.stone += total_changes.get('stone', 0)
        self.settlement.last_collection_time = now.isoformat()
        
        summary = ", ".join([f"{k}: {v:+}" for k, v in total_changes.items() if v != 0])
        if not summary: summary = "No resources produced (Lack of workers or raw materials)."
        
        await interaction.edit_original_response(content=f"✅ **Collection Complete**\n{summary}", embed=self.build_embed(), view=self)

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

class BuildConstructionView(ui.View):
    def __init__(self, bot, user_id, slot_index, parent_view):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.slot_index = slot_index
        self.parent = parent_view
        
        self.COSTS = {
            "logging_camp": {"gold": 1000, "stone": 50},
            "quarry":       {"gold": 1000, "timber": 50},
            "foundry":      {"gold": 5000, "timber": 200, "stone": 200},
            "sawmill":      {"gold": 5000, "timber": 200, "stone": 200},
            "reliquary":    {"gold": 5000, "timber": 200, "stone": 200},
            "market":       {"gold": 10000, "timber": 500, "stone": 500},
            "barracks":     {"gold": 15000, "timber": 1000, "stone": 1000},
            "temple":       {"gold": 20000, "timber": 1500, "stone": 1500}
        }
        
        self.setup_select()

    def build_embed(self):
        embed = discord.Embed(title="Construction Site", description="Select a building plan.", color=discord.Color.blue())
        embed.set_thumbnail(url="https://i.imgur.com/cZcEKhS.png")
        return embed

    def setup_select(self):
        BUILDING_INFO = {
            "logging_camp": "Generates Timber. Required for upgrades.",
            "quarry":       "Generates Stone. Required for upgrades.",
            "foundry":      "Converts Ore -> Ingots (Weapon/Armor crafting).",
            "sawmill":      "Converts Logs -> Planks (Structure upgrades).",
            "reliquary":    "Converts Bones -> Essence (Enchantments).",
            "market":       "Generates Passive Gold based on workforce.",
            "barracks":     "Passive: +1% Atk/Def per tier.",
            "temple":       "Passive: +5% Propagate growth per tier."
        }
                
        options = []
        for key, cost in self.COSTS.items():
            lbl = key.replace("_", " ").title()
            desc = f"Cost: {cost.get('gold',0)}g, 🪵{cost.get('timber',0)}, 🪨{cost.get('stone',0)}"
            options.append(SelectOption(label=lbl, value=key, description=desc))
            
        select = ui.Select(placeholder="Choose Blueprint...", options=options)
        select.callback = self.on_select
        self.add_item(select)
        
        cancel = ui.Button(label="Cancel", style=ButtonStyle.danger)
        cancel.callback = self.cancel
        self.add_item(cancel)

    async def on_select(self, interaction: Interaction):
        b_type = interaction.data['values'][0]
        cost = self.COSTS[b_type]

        used_slots = len(self.parent.settlement.buildings)
        max_slots = self.parent.settlement.building_slots

        if used_slots >= max_slots:
            return await interaction.response.send_message(
                f"No building slots remaining! Upgrade your Town Hall to build more.", 
                ephemeral=True
            )
        
        # Check Funds
        u_gold = await self.bot.database.users.get_gold(self.user_id)
        u_timber = self.parent.settlement.timber
        u_stone = self.parent.settlement.stone
        
        if u_gold < cost.get('gold', 0) or u_timber < cost.get('timber', 0) or u_stone < cost.get('stone', 0):
            return await interaction.response.send_message("Insufficient resources!", ephemeral=True)
            
        await interaction.response.defer()
        
        # Deduct
        changes = {'gold': -cost.get('gold', 0), 'timber': -cost.get('timber', 0), 'stone': -cost.get('stone', 0)}
        await self.bot.database.settlement.commit_production(self.user_id, self.parent.server_id, changes)
        
        # Build
        await self.bot.database.settlement.build_structure(
            self.user_id, self.parent.server_id, b_type, self.slot_index
        )
        
        # Update Parent
        self.parent.settlement = await self.bot.database.settlement.get_settlement(self.user_id, self.parent.server_id)
        self.parent.update_grid()
        
        await interaction.edit_original_response(embed=self.parent.build_embed(), view=self.parent)
        self.stop()

    async def cancel(self, interaction: Interaction):
        await interaction.response.edit_message(embed=self.parent.build_embed(), view=self.parent)
        self.stop()

class BuildingDetailView(ui.View):
    def __init__(self, bot, user_id, building: Building, parent_view):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.building = building
        self.parent = parent_view
        
        self.setup_ui()

    SPECIAL_MAP = {
        "foundry": "magma_core",
        "quarry": "magma_core",
        "sawmill": "life_root",
        "logging_camp": "life_root",
        "reliquary": "spirit_shard",
        "temple": "spirit_shard",
        "market": "spirit_shard",
        "barracks": "spirit_shard",
        "town_hall": "spirit_shard"
    }

    THUMBNAILS = {
        "town_hall": "https://i.imgur.com/xNY7tPj.png",
        "logging_camp": "https://i.imgur.com/CWhzIHy.png",
        "quarry": "https://i.imgur.com/ChAHxnq.png",
        "foundry": "https://i.imgur.com/WFr1Z31.png",   # Forge
        "sawmill": "https://i.imgur.com/Cj8D00u.png",
        "reliquary": "https://i.imgur.com/W9iiQtD.png",
        "market": "https://i.imgur.com/FavvGUA.png",
        "barracks": "https://i.imgur.com/RvhhUCJ.png",
        "temple": "https://i.imgur.com/4bmHF4u.png",
    }

    # Helper for display names
    ITEM_NAMES = {
        "magma_core": "Magma Core",
        "life_root": "Life Root",
        "spirit_shard": "Spirit Shard"
    }

    def build_embed(self):
        b_data = SettlementMechanics.BUILDINGS.get(self.building.building_type)
        max_w = SettlementMechanics.get_max_workers(self.building.tier)
        
        # Calculate Rate
        rate = b_data['base_rate'] * self.building.tier * self.building.workers_assigned
        
        desc = (
            f"**Level:** {self.building.tier}/5\n"
            f"**Workers:** {self.building.workers_assigned}/{max_w}\n"
            f"**Output:** ~{rate}/hr ({b_data.get('output', 'Refined Goods')})"
        )
        
        embed = discord.Embed(title=f"{self.building.name}", description=desc, color=discord.Color.gold())
            
        thumb = self.THUMBNAILS.get(self.building.building_type)
        if thumb:
            embed.set_thumbnail(url=thumb)

        # Upgrade Cost Preview (Simplified for display)
        next_cost = self._get_upgrade_cost(self.building.tier + 1)
        if self.building.tier < 5:
            cost_str = f"🪵 {next_cost.get('timber')} | 🪨 {next_cost.get('stone')} | 💰 {next_cost.get('gold')}"
            if 'special' in next_cost:
                cost_str += f" | ✨ {next_cost['special']} x{next_cost['special_qty']}"
            embed.add_field(name="Next Upgrade Cost", value=cost_str, inline=False)
        else:
            embed.add_field(name="Status", value="🌟 Max Level Reached", inline=False)
            
        return embed

    def _get_upgrade_cost(self, target_tier):
        # Formula: Base * Tier^1.5
        base_wood = 200
        base_stone = 200
        base_gold = 5000
        
        cost = {
            "timber": int(base_wood * (target_tier ** 1.5)),
            "stone": int(base_stone * (target_tier ** 1.5)),
            "gold": int(base_gold * (target_tier ** 1.5))
        }
        
        # Special Materials
        if target_tier == 3:
            cost['special'] = "Magma Core" if self.building.building_type == "foundry" else "Special Material"
            cost['special_qty'] = 1
        elif target_tier == 4:
            cost['special'] = "Magma Core"
            cost['special_qty'] = 2
        elif target_tier == 5:
            cost['special'] = "Magma Core"
            cost['special_qty'] = 3
            
        return cost

    def setup_ui(self):
        self.clear_items()
        
        # Workers
        btn_workers = ui.Button(label="Assign Workers", style=ButtonStyle.primary, emoji="👥")
        btn_workers.callback = self.manage_workers
        self.add_item(btn_workers)

        btn_max = ui.Button(label="Max Workers", style=ButtonStyle.primary, row=0)
        btn_max.callback = self.max_workers
        self.add_item(btn_max)
        
        # Upgrade
        btn_upgrade = ui.Button(label="Upgrade", style=ButtonStyle.success, emoji="⬆️", disabled=(self.building.tier >= 5))
        btn_upgrade.callback = self.upgrade_building
        self.add_item(btn_upgrade)

        if self.building.building_type != "town_hall":
            btn_demo = ui.Button(label="Demolish", style=ButtonStyle.danger, row=1)
            btn_demo.callback = self.demolish_building
            self.add_item(btn_demo)
        
        # Back
        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def demolish_building(self, interaction: Interaction):
        # Refunds? No. In idle games, demolition usually destroys materials.
        # But we must return the workers to the pool.
        
        await interaction.response.defer()
        
        # 1. Remove from DB
        await self.bot.database.connection.execute(
            "DELETE FROM buildings WHERE id = ?", (self.building.id,)
        )
        await self.bot.database.connection.commit()
        
        # 2. Update Local State
        # Remove building from parent list so it vanishes from grid
        self.parent.settlement.buildings = [
            b for b in self.parent.settlement.buildings if b.id != self.building.id
        ]
        
        # 3. Refresh Parent Grid
        self.parent.update_grid()
        
        await interaction.edit_original_response(
            content=f"💥 **{self.building.name}** has been demolished. Workers returned to pool.", 
            embed=self.parent.build_embed(), 
            view=self.parent
        )
        self.stop()

    async def manage_workers(self, interaction: Interaction):
        modal = WorkerModal(self)
        await interaction.response.send_modal(modal)


    async def max_workers(self, interaction: Interaction):
        # Calculate Max Possible
        cap_per_building = SettlementMechanics.get_max_workers(self.building.tier)
        
        total_assigned_global = sum(b.workers_assigned for b in self.parent.settlement.buildings)
        currently_in_this = self.building.workers_assigned
        
        # Total free people in town
        free_followers = self.parent.follower_count - (total_assigned_global - currently_in_this)
        
        # We can fill up to the cap, or as many as we have free
        target_amount = min(cap_per_building, free_followers)
        
        if target_amount == self.building.workers_assigned:
            return await interaction.response.send_message("Building already at optimal capacity.", ephemeral=True)

        await interaction.response.defer()
        
        await self.bot.database.settlement.assign_workers(self.building.id, target_amount)
        self.building.workers_assigned = target_amount
        
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def upgrade_building(self, interaction: Interaction):
        target_tier = self.building.tier + 1
        costs = self._get_upgrade_cost(target_tier)
        
        # Check Settlement Resources
        if (self.parent.settlement.timber < costs['timber'] or 
            self.parent.settlement.stone < costs['stone']):
            return await interaction.response.send_message("Insufficient Timber or Stone!", ephemeral=True)
            
        # Check Gold
        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < costs['gold']:
            return await interaction.response.send_message("Insufficient Gold!", ephemeral=True)
            
        # 3. Check Special Items (T3+)
        if 'special_key' in costs:
            col = costs['special_key']
            req = costs['special_qty']
            
            # Explicitly check user's special inventory
            async with self.bot.database.connection.execute(
                f"SELECT {col} FROM users WHERE user_id = ?", (self.user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                owned = row[0] if row else 0
            
            if owned < req:
                return await interaction.response.send_message(
                    f"Missing Material: You need **{req}x {costs['special_name']}** (Owned: {owned})", 
                    ephemeral=True
                )
            
            # Prepare deduction
            await self.bot.database.users.modify_currency(self.user_id, col, -req)

        await interaction.response.defer()
        
        # Deduct
        changes = {'gold': -costs['gold'], 'timber': -costs['timber'], 'stone': -costs['stone']}
        await self.bot.database.settlement.commit_production(self.user_id, self.parent.server_id, changes)
        
        # Upgrade DB
        await self.bot.database.connection.execute(
            "UPDATE buildings SET tier = tier + 1 WHERE id = ?", (self.building.id,)
        )

        # --- NEW: TOWN HALL SPECIAL EFFECT ---
        if self.building.building_type == "town_hall":
            # Town Hall upgrades increase max slots by 1 per tier
            await self.bot.database.connection.execute(
                "UPDATE settlements SET building_slots = building_slots + 1 WHERE user_id = ? AND server_id = ?",
                (self.user_id, self.parent.server_id)
            )
            # Update local state so UI reflects it immediately
            self.parent.settlement.building_slots += 1

        await self.bot.database.connection.commit()
        
        # Update Local
        self.building.tier += 1
        self.parent.settlement.timber -= costs['timber']
        self.parent.settlement.stone -= costs['stone']
        
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def go_back(self, interaction: Interaction):
        await interaction.response.edit_message(embed=self.parent.build_embed(), view=self.parent)
        self.stop()

class WorkerModal(ui.Modal, title="Manage Workforce"):
    count = ui.TextInput(label="Number of Workers", min_length=1, max_length=4)

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        try:
            val = int(self.count.value)
            if val < 0: raise ValueError
            
            # Validation: Cap check
            max_w = SettlementMechanics.get_max_workers(self.parent_view.building.tier)
            if val > max_w:
                return await interaction.response.send_message(f"This building can only hold {max_w} workers.", ephemeral=True)
            
            # Validation: Total Available
            # We need to know how many are FREE. 
            # Free = Total_Followers - (Currently_Assigned_Total - Workers_In_This_Building)
            total_assigned_global = sum(b.workers_assigned for b in self.parent_view.parent.settlement.buildings)
            currently_in_this = self.parent_view.building.workers_assigned
            free_followers = self.parent_view.parent.follower_count - (total_assigned_global - currently_in_this)
            
            if val > free_followers:
                return await interaction.response.send_message(f"You only have {free_followers} available followers.", ephemeral=True)

            # Update DB
            await self.parent_view.bot.database.settlement.assign_workers(self.parent_view.building.id, val)
            
            # Update Local
            self.parent_view.building.workers_assigned = val
            
            await interaction.response.edit_message(embed=self.parent_view.build_embed(), view=self.parent_view)
            
        except ValueError:
            await interaction.response.send_message("Invalid number.", ephemeral=True)