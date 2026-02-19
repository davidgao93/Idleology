import discord
from discord import ui, ButtonStyle, Interaction, SelectOption
from datetime import datetime
from core.models import Settlement, Building
from core.settlement.mechanics import SettlementMechanics
import asyncio

class TownHallView(ui.View):
    def __init__(self, bot, user_id, settlement, parent_view):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.settlement = settlement
        self.parent = parent_view
        self.setup_ui()

    async def on_timeout(self):
        try:
            expired_embed = discord.Embed(
                title="Town Hall Session Expired",
                description="This Town Hall management session has timed out.\n\n"
                            "Reopen your settlement dashboard to manage it again.",
                color=discord.Color.dark_grey()
            )
            await self.parent.message.edit(embed=expired_embed, view=None)
        except:
            pass
        finally:
            self.stop()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    def _get_upgrade_cost(self, target_tier):
        # Town Hall is expensive. Base costs higher than normal buildings.
        base_wood = 500
        base_stone = 500
        base_gold = 10000
        
        cost = {
            "timber": int(base_wood * (target_tier ** 1.5)),
            "stone": int(base_stone * (target_tier ** 1.5)),
            "gold": int(base_gold * (target_tier ** 1.5))
        }
        
        # Special Materials
        if target_tier >= 3:
            cost['special_key'] = "spirit_shard"
            cost['special_name'] = "Spirit Shard"
            cost['special_qty'] = target_tier - 2 # 1 at T3, 2 at T4, 3 at T5
            
        return cost

    def build_embed(self):
        tier = self.settlement.town_hall_tier
        slots = self.settlement.building_slots
        
        # Calculate next tier benefits
        next_slots = slots + 1
        
        desc = (
            f"**Level:** {tier}/5\n"
            f"**Building Slots:** {slots}\n"
            f"**Follower Cap Buff:** +{tier * 10}%\n" 
        )
        
        embed = discord.Embed(title="🏛️ Town Hall", description=desc, color=discord.Color.dark_blue())
        
        if tier < 5:
            costs = self._get_upgrade_cost(tier + 1)
            cost_str = f"🪵 {costs['timber']:,} | 🪨 {costs['stone']:,} | 💰 {costs['gold']:,}"
            if 'special_key' in costs:
                cost_str += f" | ✨ {costs['special_name']} x{costs['special_qty']}"
                
            embed.add_field(name="Upgrade Benefits", value=f"Slots: {slots} ➡️ **{next_slots}**", inline=False)
            embed.add_field(name="Upgrade Cost", value=cost_str, inline=False)
        else:
            embed.add_field(name="Status", value="🌟 Maximum Authority Reached", inline=False)
        embed.set_thumbnail(url="https://i.imgur.com/xNY7tPj.png")    
        return embed

    def setup_ui(self):
        self.clear_items()
        
        btn_up = ui.Button(label="Upgrade Hall", style=ButtonStyle.success, emoji="⬆️", disabled=(self.settlement.town_hall_tier >= 5))
        btn_up.callback = self.upgrade
        self.add_item(btn_up)
        
        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def upgrade(self, interaction: Interaction):
        target_tier = self.settlement.town_hall_tier + 1
        costs = self._get_upgrade_cost(target_tier)
        
        # 1. Check Resources
        if (self.settlement.timber < costs['timber'] or 
            self.settlement.stone < costs['stone']):
            return await interaction.response.send_message("Insufficient Timber or Stone!", ephemeral=True)
            
        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < costs['gold']:
            return await interaction.response.send_message("Insufficient Gold!", ephemeral=True)

        if 'special_key' in costs:
            col = costs['special_key']
            req = costs['special_qty']
            async with self.bot.database.connection.execute(f"SELECT {col} FROM users WHERE user_id = ?", (self.user_id,)) as c:
                owned = (await c.fetchone())[0]
            
            if owned < req:
                return await interaction.response.send_message(f"Need {req}x {costs['special_name']}!", ephemeral=True)
            
            await self.bot.database.users.modify_currency(self.user_id, col, -req)

        await interaction.response.defer()

        # 2. Consume Resources
        changes = {'gold': -costs['gold'], 'timber': -costs['timber'], 'stone': -costs['stone']}
        await self.bot.database.settlement.commit_production(self.user_id, self.parent.server_id, changes)

        # 3. Update DB (Settlements Table)
        # Upgrading Town Hall adds 1 building slot
        await self.bot.database.connection.execute(
            """UPDATE settlements 
               SET town_hall_tier = town_hall_tier + 1, 
                   building_slots = building_slots + 1 
               WHERE user_id = ? AND server_id = ?""",
            (self.user_id, self.parent.server_id)
        )
        await self.bot.database.connection.commit()

        # 4. Update Local State
        self.settlement.town_hall_tier += 1
        self.settlement.building_slots += 1
        self.settlement.timber -= costs['timber']
        self.settlement.stone -= costs['stone']

        # 5. Refresh
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def go_back(self, interaction: Interaction):
        # We need to refresh the parent grid because slots might have increased
        self.parent.update_grid() 
        await interaction.response.edit_message(embed=self.parent.build_embed(), view=self.parent)
        self.stop()


class SettlementDashboardView(ui.View):
    def __init__(self, bot, user_id, server_id, settlement: Settlement, follower_count: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.settlement = settlement
        self.follower_count = follower_count
        self.update_grid()

    RESOURCE_DISPLAY_NAMES = {
        "timber": "Timber",
        "stone": "Stone",
        "gold": "Gold",
        "iron": "Iron Ore",
        "coal": "Coal",
        "platinum": "Platinum Ore",
        "idea": "Idea Ore",
        "iron_bar": "Iron Bars",
        "steel_bar": "Steel Bars",
        "gold_bar": "Gold Bars",
        "platinum_bar": "Platinum Bars",
        "idea_bar": "Idea Bars",
        "oak_logs": "Oak Logs",
        "willow_logs": "Willow Logs",
        "mahogany_logs": "Mahogany Logs",
        "magic_logs": "Magic Logs",
        "idea_logs": "Idea Logs",
        "oak_plank": "Oak Planks",
        "willow_plank": "Willow Planks",
        "mahogany_plank": "Mahogany Planks",
        "magic_plank": "Magic Planks",
        "idea_plank": "Idea Planks",
        "desiccated_bones": "Desiccated Bones",
        "regular_bones": "Regular Bones",
        "sturdy_bones": "Sturdy Bones",
        "reinforced_bones": "Reinforced Bones",
        "titanium_bones": "Titanium Bones",
        "desiccated_essence": "Desiccated Essence",
        "regular_essence": "Regular Essence",
        "sturdy_essence": "Sturdy Essence",
        "reinforced_essence": "Reinforced Essence",
        "titanium_essence": "Titanium Essence",
    }

    def _format_changes(self, changes: dict) -> str:
        positive_items = []
        for key, value in changes.items():
            if value <= 0:
                continue
            name = self.RESOURCE_DISPLAY_NAMES.get(
                key, key.replace("_", " ").title()
            )
            emoji = ""
            if key == "timber":
                emoji = "🪵 "
            elif key == "stone":
                emoji = "🪨 "
            elif key == "gold":
                emoji = "💰 "
            positive_items.append(f"{emoji}{name}: +{value:,}")

        if not positive_items:
            return "No resources produced (no workers, generators, or raw materials)."

        return "\n".join(positive_items)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try:
            expired_embed = discord.Embed(
                title="Settlement Session Expired",
                description="This settlement management session has timed out.\n\n"
                            "Run the command again to reopen the dashboard.",
                color=discord.Color.dark_grey()
            )
            await self.message.edit(embed=expired_embed, view=None)
        except:
            pass

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
            # copy raw_inv logic from collect_resources, but using a snapshot
            # If you don't want to fetch skills here again, just display *per-hour* rates:
            for b in self.settlement.buildings:
                if b.workers_assigned <= 0:
                    continue

                b_data = SettlementMechanics.BUILDINGS.get(b.building_type)
                if not b_data:
                    continue

                # Match the generator formula: base_rate * tier * workers
                per_hour = int(b_data['base_rate'] * b.tier * b.workers_assigned)
                if b_data["type"] == "generator":
                    resource = b_data.get("output", "output")
                    display = self.RESOURCE_DISPLAY_NAMES.get(
                        resource, resource.replace("_", " ").title()
                    )
                    pending_txt += f"• {b.name}: ~{per_hour * hours:.0f} {display}\n"
                else:
                    # For converters and passives, either skip or add a generic line
                    pending_txt += f"• {b.name}: Converts raw materials (see details)\n"

            if pending_txt:
                embed.add_field(name="Pending Production", value=pending_txt, inline=False)

        if self.settlement.buildings:
            lines = []
            for b in self.settlement.buildings:
                info = BuildingDetailView.BUILDING_INFO.get(b.building_type)
                if info:
                    lines.append(f"• **{b.name} (T{b.tier})** – {info}")
                else:
                    lines.append(f"• **{b.name} (T{b.tier})**")
            
            embed.add_field(
                name="Buildings",
                value="\n".join(lines),
                inline=False
            )

        return embed

    def update_grid(self):
        self.clear_items()
        
        # 1. Building Slots
        built_map = {b.slot_index: b for b in self.settlement.buildings}
        
        # Iterate up to current max slots
        for i in range(self.settlement.building_slots):
            row = i // 3 # 3 buttons per row
            # Safety: Discord max row is 4 (index 0-4). 
            # If slots > 12, we need pagination. For now (max 8), this is fine.
            
            if i in built_map:
                b = built_map[i]
                status = "🟢" if b.workers_assigned > 0 else "🔴"
                btn = ui.Button(label=f"{b.name} (T{b.tier}) {status}", style=ButtonStyle.secondary, row=row)
                btn.callback = lambda inter, b=b: self.open_building(inter, b)
            else:
                btn = ui.Button(label=f"Slot {i+1} [Empty]", style=ButtonStyle.gray, row=row)
                btn.callback = lambda inter, slot=i: self.open_build_menu(inter, slot)
            self.add_item(btn)

        # 2. Controls (Row 3 or 4 depending on slots)
        # With max 8 slots, the grid uses Row 0, 1, 2. Controls go to Row 3.
        ctrl_row = (self.settlement.building_slots // 3) + 1
        if ctrl_row > 4: ctrl_row = 4 # Cap at bottom row

        # Town Hall Button
        th_btn = ui.Button(label=f"Town Hall (T{self.settlement.town_hall_tier})", style=ButtonStyle.primary, row=ctrl_row, emoji="🏛️")
        th_btn.callback = self.open_town_hall
        self.add_item(th_btn)

        collect_btn = ui.Button(label="Collect", style=ButtonStyle.success, row=ctrl_row, emoji="🚜")
        collect_btn.callback = self.collect_resources
        self.add_item(collect_btn)
        
        close_btn = ui.Button(label="Close", style=ButtonStyle.danger, row=ctrl_row)
        close_btn.callback = self.close_view
        self.add_item(close_btn)

    async def open_town_hall(self, interaction: Interaction):
        view = TownHallView(self.bot, self.user_id, self.settlement, self)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def open_build_menu(self, interaction: Interaction, slot_index: int):
        view = BuildConstructionView(self.bot, self.user_id, slot_index, self)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def open_building(self, interaction: Interaction, building: Building):
        view = BuildingDetailView(self.bot, self.user_id, building, self)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def collect_resources(self, interaction: Interaction):
        await interaction.response.defer()
        
        uid, sid = self.user_id, self.server_id

        # 1. Fetch inventory for limiting logic
        mining = await self.bot.database.skills.get_data(uid, sid, 'mining')
        wood = await self.bot.database.skills.get_data(uid, sid, 'woodcutting')
        fish = await self.bot.database.skills.get_data(uid, sid, 'fishing')
        
        raw_inv = {
            'iron': mining[3], 'coal': mining[4], 'gold': mining[5], 'platinum': mining[6], 'idea': mining[7],
            'oak_logs': wood[3], 'willow_logs': wood[4], 'mahogany_logs': wood[5], 'magic_logs': wood[6], 'idea_logs': wood[7],
            'desiccated_bones': fish[3], 'regular_bones': fish[4], 'sturdy_bones': fish[5], 'reinforced_bones': fish[6], 'titanium_bones': fish[7]
        }

        # 2. Calculate time elapsed
        now = datetime.now()
        last = datetime.fromisoformat(self.settlement.last_collection_time)
        hours = (now - last).total_seconds() / 3600
        
        if hours < 0.1:  # Minimum 6 minutes
            return await interaction.followup.send(
                "Your workers haven't generated anything yet.",
                ephemeral=True
            )

        # 3. Calculate changes
        total_changes: dict[str, int] = {}
        for b in self.settlement.buildings:
            changes = SettlementMechanics.calculate_production(
                b.building_type, b.tier, b.workers_assigned, hours, raw_inv
            )
            for k, v in changes.items():
                total_changes[k] = total_changes.get(k, 0) + v
                if k in raw_inv:
                    raw_inv[k] += v

        print("DEBUG total_changes AFTER MERGE:", total_changes)

        # Make a copy specifically for display (so you can filter it safely)
        display_changes = dict(total_changes)

        # If you have any filtering logic, apply it to display_changes, NOT total_changes
        # Example: if you had something like this before:
        # total_changes = {k: v for k, v in total_changes.items() if v > 0}
        # change it to:
        # display_changes = {k: v for k, v in display_changes.items() if v > 0}

        print("DEBUG display_changes BEFORE format:", display_changes)

        # 4. Commit to DB with the full changes
        await self.bot.database.settlement.commit_production(uid, sid, total_changes)
        await self.bot.database.settlement.update_collection_timer(uid, sid)

        # 5. Update local settlement state
        self.settlement.timber += display_changes.get('timber', 0)
        self.settlement.stone  += display_changes.get('stone', 0)
        self.settlement.last_collection_time = now.isoformat()

        # 6. Build updated embed
        embed = self.build_embed()

        # 7. Use display_changes for the Last Collection field
        formatted_changes = self._format_changes(display_changes)
        embed.add_field(
            name="Last Collection",
            value=(
                f"⏱️ Time since last collection: {hours:.2f} hours\n\n"
                f"📦 Yield:\n{formatted_changes}"
            ),
            inline=False
        )

        # 8. Content message depending on whether anything positive was produced
        has_positive = any(v > 0 for v in display_changes.values())
        if has_positive:
            content = "✅ **Collection Complete**"
        else:
            content = "ℹ️ Collection complete, but no resources were produced."

        await interaction.edit_original_response(
            embed=embed,
            view=self
        )
        await asyncio.sleep(1.0)

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

class BuildConstructionView(ui.View):
    # Class-level definitions for easy access in embed generation
    BUILDING_INFO = {
        "logging_camp": "Generates Timber over time.",
        "quarry":       "Generates Stone over time.",
        "foundry":      "Converts Ore into Ingots (for high-tier crafting).",
        "sawmill":      "Converts Logs into Planks (for settlement upgrades).",
        "reliquary":    "Converts Bones into Essence (for enchantments).",
        "market":       "Generates Passive Gold based on workforce size.",
        "barracks":     "Passive: Grants +1% Base Atk/Def per tier.",
        "temple":       "Passive: Grants +5% Propagate follower gain per tier."
    }

    def __init__(self, bot, user_id, slot_index, parent_view):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.slot_index = slot_index
        self.parent = parent_view
        
        self.COSTS = {
            "logging_camp": {"gold": 100, "stone": 0},
            "quarry":       {"gold": 100, "timber": 0},
            "foundry":      {"gold": 5000, "timber": 200, "stone": 200},
            "sawmill":      {"gold": 5000, "timber": 200, "stone": 200},
            "reliquary":    {"gold": 5000, "timber": 200, "stone": 200},
            "market":       {"gold": 10000, "timber": 500, "stone": 500},
            "barracks":     {"gold": 15000, "timber": 1000, "stone": 1000},
            "temple":       {"gold": 20000, "timber": 1500, "stone": 1500}
        }
        
        self.setup_select()

    def build_embed(self):
        embed = discord.Embed(
            title="🏗️ Construction Site", 
            description="Select a blueprint to begin construction.\n\n__**Available Blueprints**__", 
            color=discord.Color.blue()
        )

        existing_types = {b.building_type for b in self.parent.settlement.buildings}

        for b_type, info in self.BUILDING_INFO.items():
            # Formatting
            name = b_type.replace("_", " ").title()
            cost = self.COSTS[b_type]
            
            cost_str = f"💰 {cost.get('gold', 0):,}"
            if cost.get('timber'): cost_str += f" | 🪵 {cost['timber']}"
            if cost.get('stone'): cost_str += f" | 🪨 {cost['stone']}"

            status_icon = "✅"
            if b_type in existing_types:
                status_icon = "🔒 (Already Built)"
            
            # Add field
            embed.add_field(
                name=f"{status_icon} {name}",
                value=f"{info}\n*Cost: {cost_str}*",
                inline=False
            )
            
        return embed
    
    async def on_timeout(self):
        try:
            expired_embed = discord.Embed(
                title="Construction Menu Expired",
                description="This construction selection session has timed out.\n\n"
                            "Open the empty slot again from the settlement dashboard to build.",
                color=discord.Color.dark_grey()
            )
            await self.parent.message.edit(embed=expired_embed, view=None)
        except:
            pass
        finally:
            self.stop()


    def setup_select(self):
        self.clear_items()

        existing_types = {b.building_type for b in self.parent.settlement.buildings}
        options = []
        
        for key, cost in self.COSTS.items():
            if key in existing_types: continue

            lbl = key.replace("_", " ").title()
            # Brief description for dropdown
            desc = f"Cost: {cost.get('gold',0)}g"
            if cost.get('timber'): desc += f", {cost['timber']} Wood"
            
            options.append(SelectOption(label=lbl, value=key, description=desc))
            
        if not options:
            self.add_item(ui.Button(label="No New Blueprints Available", style=ButtonStyle.gray, disabled=True))
        else:
            select = ui.Select(placeholder="Select Blueprint...", options=options)
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


    async def on_timeout(self):
        try:
            expired_embed = discord.Embed(
                title="Building Session Expired",
                description=f"Management for **{self.building.name}** has timed out.\n\n"
                            "Open the building again from the settlement dashboard to continue.",
                color=discord.Color.dark_grey()
            )
            await self.parent.message.edit(embed=expired_embed, view=None)
        except:
            pass
        finally:
            self.stop()

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

    ITEM_NAMES = {
        "magma_core": "Magma Core",
        "life_root": "Life Root",
        "spirit_shard": "Spirit Shard"
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

    BUILDING_INFO = {
        "logging_camp": "Generates Timber. Required for upgrades.",
        "quarry":       "Generates Stone. Required for upgrades.",
        "foundry":      "Converts Ore -> Ingots (Crafting/Upgrades).",
        "sawmill":      "Converts Logs -> Planks (Crafting/Upgrades).",
        "reliquary":    "Converts Bones -> Essence (Crafting/Upgrades).",
        "market":       "Generates Passive Gold based on workforce.",
        "barracks":     "Passive: +1% Atk/Def per tier.",
        "temple":       "Passive: +5% Propagate growth per tier."
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

        info = self.BUILDING_INFO.get(self.building.building_type)
        if info:
            embed.add_field(name="Function", value=info, inline=False)

        # Upgrade Cost Preview (Simplified for display)
        next_cost = self._get_upgrade_cost(self.building.tier + 1)
        if self.building.tier < 5:
            cost_str = f"🪵 {next_cost.get('timber'):,} | 🪨 {next_cost.get('stone'):,} | 💰 {next_cost.get('gold'):,}"
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
        if target_tier >= 3:
            # Map building type -> db_column -> Display Name
            special_col = self.SPECIAL_MAP.get(self.building.building_type, "magma_core")
            display_name = self.ITEM_NAMES.get(special_col, "Special Material")
            
            cost['special_key'] = special_col # For DB logic
            cost['special'] = display_name    # For Display logic
            
            # Quantity Logic
            if target_tier == 3: cost['special_qty'] = 1
            elif target_tier == 4: cost['special_qty'] = 2
            elif target_tier == 5: cost['special_qty'] = 3
            
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
            return await interaction.response.send_message(
                "Building already at optimal capacity.",
                ephemeral=True
            )

        await interaction.response.defer()
        
        await self.bot.database.settlement.assign_workers(self.building.id, target_amount)

        # Refresh settlement from DB to sync worker counts for all buildings
        self.parent.settlement = await self.bot.database.settlement.get_settlement(
            self.user_id,
            self.parent.server_id
        )

        # Refresh this building reference from the updated settlement
        for b in self.parent.settlement.buildings:
            if b.id == self.building.id:
                self.building = b
                break

        # Rebuild parent grid (so button labels & 🟢/🔴 match)
        self.parent.update_grid()
        
        await interaction.edit_original_response(
            embed=self.build_embed(),
            view=self
        )

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
            if val < 0:
                raise ValueError
            
            # Validation: Cap check
            max_w = SettlementMechanics.get_max_workers(self.parent_view.building.tier)
            if val > max_w:
                return await interaction.response.send_message(
                    f"This building can only hold {max_w} workers.", ephemeral=True
                )
            
            # Validation: Total Available
            total_assigned_global = sum(
                b.workers_assigned for b in self.parent_view.parent.settlement.buildings
            )
            currently_in_this = self.parent_view.building.workers_assigned
            free_followers = (
                self.parent_view.parent.follower_count
                - (total_assigned_global - currently_in_this)
            )
            
            if val > free_followers:
                return await interaction.response.send_message(
                    f"You only have {free_followers} available followers.", ephemeral=True
                )

            # Update DB
            await self.parent_view.bot.database.settlement.assign_workers(
                self.parent_view.building.id, val
            )

            # Refresh settlement from DB so the grid state is accurate
            self.parent_view.parent.settlement = await self.parent_view.bot.database.settlement.get_settlement(
                self.parent_view.user_id,
                self.parent_view.parent.server_id
            )

            # Update local building reference (same object, but we re-sync)
            # Find the updated building in the refreshed settlement
            for b in self.parent_view.parent.settlement.buildings:
                if b.id == self.parent_view.building.id:
                    self.parent_view.building = b
                    break

            # Rebuild parent grid so green/red icons match worker assignments
            self.parent_view.parent.update_grid()

            await interaction.response.edit_message(
                embed=self.parent_view.build_embed(),
                view=self.parent_view
            )
            
        except ValueError:
            await interaction.response.send_message("Invalid number.", ephemeral=True)