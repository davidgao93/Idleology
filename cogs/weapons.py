import discord
import asyncio
import random
from discord.ext import commands
from discord import app_commands, Interaction, Message, ButtonStyle
from discord.ui import View, Button

# Core Imports
from core.models import Weapon
from core.items.factory import create_weapon
from core.items.equipment_mechanics import EquipmentMechanics
from core.ui.inventory import InventoryUI

class Weapons(commands.Cog, name="weapons"):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def _fetch_and_parse_weapons(self, user_id: str) -> list[Weapon]:
        """Helper to fetch raw DB data and convert to Objects."""
        raw_items = await self.bot.database.equipment.get_all(user_id, 'weapon')
        if not raw_items: 
            return []
        return [create_weapon(item) for item in raw_items]

    @app_commands.command(name="weapons", description="View your character's weapons and modify them.")
    async def view_weapons(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        if not await self.bot.check_is_active(interaction, user_id): return

        self.bot.state_manager.set_active(user_id, "inventory")
        
        # 2. Pagination Setup
        # REDUCED TO 5 TO PREVENT 1024 CHAR LIMIT ERROR
        items_per_page = 5 
        current_page = 0
        message = None

        # 3. Main Navigation Loop
        while True:
            # A. Fetch Data
            weapons = await self._fetch_and_parse_weapons(user_id)
            
            # Handle Empty Inventory
            if not weapons:
                if message:
                    await message.edit(content="Your weapon pouch is empty.", embed=None, view=None)
                else:
                    await interaction.response.send_message("You search your gear for weapons, you find none.")
                break

            # B. Sort: Equipped first, then by Level
            equipped_raw = await self.bot.database.equipment.get_equipped(user_id, "weapon")
            equipped_id = equipped_raw[0] if equipped_raw else None
            
            weapons.sort(key=lambda w: (w.item_id == equipped_id, w.level), reverse=True)
            
            # C. Pagination Math
            total_pages = (len(weapons) + items_per_page - 1) // items_per_page
            current_page = min(current_page, max(0, total_pages - 1))
            
            # D. Slice Items
            start_idx = current_page * items_per_page
            page_items = weapons[start_idx:start_idx + items_per_page]

            # E. Generate UI
            embed = InventoryUI.get_list_embed(
                existing_user[3], page_items, current_page, total_pages, equipped_id, "⚔️"
            )
            
            # Build View
            view = View(timeout=60)
            for i, _ in enumerate(page_items):
                view.add_item(Button(label=f"{i+1}", style=ButtonStyle.primary, custom_id=f"select_{i}"))
            
            if current_page > 0: view.add_item(Button(label="Prev", custom_id="prev"))
            if current_page < total_pages - 1: view.add_item(Button(label="Next", custom_id="next"))
            view.add_item(Button(label="Close", style=ButtonStyle.danger, custom_id="close"))

            # F. Send or Edit Message
            if message:
                await message.edit(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view)
                message = await interaction.original_response()

            # G. Wait for Interaction
            def check(i: Interaction): return i.user.id == interaction.user.id and i.message.id == message.id
            
            try:
                act = await self.bot.wait_for('interaction', timeout=60, check=check)
                await act.response.defer()
                
                cid = act.data['custom_id']
                if cid == "close": 
                    break
                elif cid == "prev": 
                    current_page -= 1
                elif cid == "next": 
                    current_page += 1
                elif cid.startswith("select_"):
                    idx = int(cid.split("_")[1])
                    selected_weapon = page_items[idx]
                    await self._handle_item_actions(interaction, message, selected_weapon, equipped_id == selected_weapon.item_id)
            
            except asyncio.TimeoutError:
                break
        
        self.bot.state_manager.clear_active(user_id)
        if message:
            try: await message.delete()
            except: pass

    async def _handle_item_actions(self, interaction: Interaction, message: Message, weapon: Weapon, is_equipped: bool):
        """Sub-loop for a specific item's actions."""
        user_id = str(interaction.user.id)
        
        while True:
            # Re-fetch item to get live stats
            raw = await self.bot.database.equipment.get_by_id(weapon.item_id, 'weapon')
            if not raw: 
                await interaction.followup.send("Item no longer exists.", ephemeral=True)
                return
            weapon = create_weapon(raw)
            
            # Check equipped status dynamically
            equipped_raw = await self.bot.database.equipment.get_equipped(user_id, "weapon")
            is_equipped = equipped_raw and equipped_raw[0] == weapon.item_id

            embed = InventoryUI.get_item_details_embed(weapon, is_equipped)
            
            # Add Action Guide
            guide = ["- Equip/Unequip", "- Refine (Gold)", "- Discard", "- Back"]
            if weapon.forges_remaining > 0: guide.insert(1, "- Forge (Mats)")
            
            user_data = await self.bot.database.users.get(user_id, interaction.guild.id)
            if user_data[30] > 0 and is_equipped and weapon.u_passive == 'none':
                guide.append("- Voidforge (Void Key)")
            
            embed.add_field(name="Actions", value="\n".join(guide), inline=False)

            # Build View
            view = View(timeout=60)
            view.add_item(Button(label="Unequip" if is_equipped else "Equip", style=ButtonStyle.primary, custom_id="equip"))
            if weapon.forges_remaining > 0:
                view.add_item(Button(label="Forge", style=ButtonStyle.success, custom_id="forge"))
            view.add_item(Button(label="Refine", style=ButtonStyle.secondary, custom_id="refine"))
            
            if user_data[30] > 0 and is_equipped and weapon.u_passive == 'none':
                view.add_item(Button(label="Voidforge", style=ButtonStyle.primary, custom_id="voidforge"))
            
            view.add_item(Button(label="Discard", style=ButtonStyle.danger, custom_id="discard"))
            view.add_item(Button(label="Back", style=ButtonStyle.secondary, custom_id="back"))

            await message.edit(embed=embed, view=view)

            def check(i: Interaction): return i.user.id == interaction.user.id and i.message.id == message.id
            try:
                act = await self.bot.wait_for('interaction', timeout=60, check=check)
                await act.response.defer()
                
                cid = act.data['custom_id']
                if cid == "back": return
                elif cid == "equip":
                    if is_equipped: await self.bot.database.equipment.unequip(user_id, 'weapon')
                    else: await self.bot.database.equipment.equip(user_id, weapon.item_id, 'weapon')
                elif cid == "discard":
                    if await self._confirm_action(message, act.user, "Discard this weapon? Irreversible."):
                        await self.bot.database.equipment.discard(weapon.item_id, 'weapon')
                        return
                elif cid == "forge":
                    await self._forge_weapon_flow(message, act.user, weapon)
                elif cid == "refine":
                    await self._refine_weapon_flow(message, act.user, weapon)
                elif cid == "voidforge":
                    await self._voidforge_flow(message, act.user, weapon)

            except asyncio.TimeoutError:
                return

    async def _confirm_action(self, message: Message, user, text: str) -> bool:
        """Generic confirmation helper."""
        embed = discord.Embed(title="Confirm", description=text, color=discord.Color.red())
        view = View(timeout=30)
        view.add_item(Button(label="Confirm", style=ButtonStyle.danger, custom_id="yes"))
        view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="no"))
        await message.edit(embed=embed, view=view)
        
        def check(i): return i.user.id == user.id and i.message.id == message.id
        try:
            act = await self.bot.wait_for('interaction', timeout=30, check=check)
            await act.response.defer()
            return act.data['custom_id'] == "yes"
        except: return False

    async def _forge_weapon_flow(self, message: Message, user, weapon: Weapon):
        """Handles the Forging UI and Logic."""
        costs = EquipmentMechanics.calculate_forge_cost(weapon)
        if not costs: return

        # Resource check
        uid, gid = str(user.id), str(message.guild.id)
        mining = await self.bot.database.skills.get_data(uid, gid, 'mining')
        wood = await self.bot.database.skills.get_data(uid, gid, 'woodcutting')
        fish = await self.bot.database.skills.get_data(uid, gid, 'fishing')
        player_gold = (await self.bot.database.users.get(uid, gid))[6]

        ore_idx = {'iron': 3, 'coal': 4, 'gold': 5, 'platinum': 6, 'idea': 7}.get(costs['ore_type'])
        log_idx = {'oak': 3, 'willow': 4, 'mahogany': 5, 'magic': 6, 'idea': 7}.get(costs['log_type'])
        bone_idx = {'desiccated': 3, 'regular': 4, 'sturdy': 5, 'reinforced': 6, 'titanium': 7}.get(costs['bone_type'])

        has_resources = (
            mining[ore_idx] >= costs['ore_qty'] and
            wood[log_idx] >= costs['log_qty'] and
            fish[bone_idx] >= costs['bone_qty'] and
            player_gold >= costs['gold']
        )

        cost_str = (
            f"• {costs['ore_qty']} {costs['ore_type'].title()} Ore ({mining[ore_idx]})\n"
            f"• {costs['log_qty']} {costs['log_type'].title()} Logs ({wood[log_idx]})\n"
            f"• {costs['bone_qty']} {costs['bone_type'].title()} Bones ({fish[bone_idx]})\n"
            f"• {costs['gold']:,} Gold ({player_gold:,})"
        )

        embed = discord.Embed(
            title=f"Forge {weapon.name}", 
            description=f"**Costs:**\n{cost_str}",
            color=discord.Color.green() if has_resources else discord.Color.red()
        )

        if not has_resources:
            embed.set_footer(text="Insufficient resources.")
            await message.edit(embed=embed, view=None)
            await asyncio.sleep(3)
            return

        view = View(timeout=30)
        view.add_item(Button(label="Forge!", style=ButtonStyle.success, custom_id="do_forge"))
        view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel"))
        await message.edit(embed=embed, view=view)

        def check(i): return i.user.id == user.id and i.message.id == message.id
        try:
            act = await self.bot.wait_for('interaction', timeout=30, check=check)
            await act.response.defer()
            if act.data['custom_id'] != "do_forge": return

            await self.bot.database.skills.update_single_resource(uid, gid, 'mining', costs['ore_type'], -costs['ore_qty'])
            await self.bot.database.skills.update_single_resource(uid, gid, 'woodcutting', f"{costs['log_type']}_logs", -costs['log_qty'])
            await self.bot.database.skills.update_single_resource(uid, gid, 'fishing', f"{costs['bone_type']}_bones", -costs['bone_qty'])
            await self.bot.database.users.modify_gold(uid, -costs['gold'])

            success, new_passive = EquipmentMechanics.roll_forge_outcome(weapon)
            
            if success:
                await self.bot.database.equipment.update_passive(weapon.item_id, 'weapon', new_passive)
                embed = discord.Embed(title="Forge Success! 🔨", description=f"Weapon passive is now **{new_passive.title()}**!", color=discord.Color.gold())
            else:
                embed = discord.Embed(title="Forge Failed 💥", description="Materials consumed, but magic failed.", color=discord.Color.dark_grey())
            
            await self.bot.database.equipment.update_counter(weapon.item_id, 'weapon', 'forges_remaining', weapon.forges_remaining - 1)
            await message.edit(embed=embed, view=None)
            await asyncio.sleep(3)

        except asyncio.TimeoutError:
            pass

    async def _refine_weapon_flow(self, message: Message, user, weapon: Weapon):
        uid = str(user.id)
        if weapon.refines_remaining <= 0:
            runes = await self.bot.database.users.get_currency(uid, 'refinement_runes')
            if runes > 0:
                if await self._confirm_action(message, user, f"No refines left. Use a **Rune of Refinement**? ({runes} owned)"):
                    await self.bot.database.users.modify_currency(uid, 'refinement_runes', -1)
                    await self.bot.database.equipment.update_counter(weapon.item_id, 'weapon', 'refines_remaining', 1)
                    return 
                return
            else:
                embed = discord.Embed(title="Limit Reached", description="No refines or runes remaining.", color=discord.Color.red())
                await message.edit(embed=embed, view=None)
                await asyncio.sleep(2)
                return

        cost = 1000
        player_gold = (await self.bot.database.users.get(uid, str(message.guild.id)))[6]
        
        if player_gold < cost:
            embed = discord.Embed(title="Poor", description=f"Need {cost} gold.", color=discord.Color.red())
            await message.edit(embed=embed, view=None)
            await asyncio.sleep(2)
            return

        if await self._confirm_action(message, user, f"Refine for **{cost}** Gold?"):
            atk_gain = random.randint(1, 3)
            def_gain = random.randint(1, 3)
            
            await self.bot.database.users.modify_gold(uid, -cost)
            await self.bot.database.equipment.increase_stat(weapon.item_id, 'weapon', 'attack', atk_gain)
            await self.bot.database.equipment.increase_stat(weapon.item_id, 'weapon', 'defence', def_gain)
            await self.bot.database.equipment.update_counter(weapon.item_id, 'weapon', 'refines_remaining', weapon.refines_remaining - 1)
            await self.bot.database.equipment.increase_stat(id, 'weapon', 'refinement_lvl', 1)

            embed = discord.Embed(title="Refined! ✨", description=f"+{atk_gain} Atk, +{def_gain} Def", color=discord.Color.blue())
            await message.edit(embed=embed, view=None)
            await asyncio.sleep(2)

    async def _voidforge_flow(self, message: Message, user, weapon: Weapon):
        uid = str(user.id)
        raw_candidates = await self.bot.database.equipment.fetch_void_forge_candidates(uid)
        candidates = [create_weapon(w) for w in raw_candidates if w[0] != weapon.item_id]
        
        if not candidates:
            embed = discord.Embed(title="Voidforge", description="No eligible sacrifice weapons found.\nReq: Unequipped, Refinement >= 5, 0 Forges left.", color=discord.Color.purple())
            await message.edit(embed=embed, view=None)
            await asyncio.sleep(3)
            return

        desc = "Type the **ID** of the weapon to sacrifice:\n"
        for c in candidates[:10]:
            desc += f"**ID {c.item_id}**: {c.name} (Passive: {c.passive})\n"
        
        embed = discord.Embed(title="Select Sacrifice", description=desc, color=discord.Color.purple())
        await message.edit(embed=embed, view=None)

        def check(m): return m.author.id == user.id and m.channel.id == message.channel.id and m.content.isdigit()
        try:
            msg = await self.bot.wait_for('message', timeout=30, check=check)
            sid = int(msg.content)
            await msg.delete()
            
            target = next((c for c in candidates if c.item_id == sid), None)
            if not target: return

            if await self._confirm_action(message, user, f"Sacrifice **{target.name}** to Voidforge **{weapon.name}**?"):
                await self.bot.database.users.modify_currency(uid, 'void_keys', -1)
                
                roll = random.random()
                outcome = ""
                
                if roll < 0.25:
                    if weapon.p_passive == 'none':
                        await self.bot.database.equipment.update_passive(weapon.item_id, 'weapon', target.passive, "pinnacle_passive")
                        outcome = "Success! Pinnacle Passive added."
                    else:
                        await self.bot.database.equipment.update_passive(weapon.item_id, 'weapon', target.passive, "utmost_passive")
                        outcome = "Success! Utmost Passive added."
                elif roll < 0.50:
                    await self.bot.database.equipment.update_passive(weapon.item_id, 'weapon', target.passive)
                    outcome = "Chaos! Main passive overwritten."
                else:
                    outcome = "Failure. The essence dissipated."

                await self.bot.database.equipment.discard(target.item_id, 'weapon')
                embed = discord.Embed(title="Voidforge Result", description=outcome, color=discord.Color.purple())
                await message.edit(embed=embed, view=None)
                await asyncio.sleep(4)

        except asyncio.TimeoutError:
            pass

async def setup(bot) -> None:
    await bot.add_cog(Weapons(bot))