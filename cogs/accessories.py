import discord
import asyncio
import random
from discord.ext import commands
from discord import app_commands, Interaction, Message, ButtonStyle
from discord.ui import View, Button

# Core Imports
from core.models import Accessory
from core.items.factory import create_accessory
from core.items.equipment_mechanics import EquipmentMechanics
from core.ui.inventory import InventoryUI

class Accessories(commands.Cog, name="accessories"):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def _fetch_and_parse_accessories(self, user_id: str) -> list[Accessory]:
        """Helper to fetch raw DB data and convert to Objects."""
        raw_items = await self.bot.database.equipment.get_all(user_id, 'accessories')
        if not raw_items: 
            return []
        return [create_accessory(item) for item in raw_items]

    @app_commands.command(name="accessory", 
                         description="View your character's accessories and modify them.")
    async def view_accessories(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        if not await self.bot.check_is_active(interaction, user_id): return

        self.bot.state_manager.set_active(user_id, "inventory")
        
        # 2. Pagination Setup
        items_per_page = 5 
        current_page = 0
        message = None

        # 3. Main Navigation Loop
        while True:
            # A. Fetch Data
            accessories = await self._fetch_and_parse_accessories(user_id)
            
            # Handle Empty Inventory
            if not accessories:
                if message:
                    await message.edit(content="Your accessory pouch is empty.", embed=None, view=None)
                else:
                    await interaction.response.send_message("You search your gear for accessories, you find none.")
                break

            # B. Sort: Equipped first, then by Level
            equipped_raw = await self.bot.database.equipment.get_equipped(user_id, "accessory")
            equipped_id = equipped_raw[0] if equipped_raw else None
            
            # Sort lambda: (Is Not Equipped, Level Descending)
            # False sorts before True, so we negate equipped check or use reverse logic
            accessories.sort(key=lambda a: (a.item_id == equipped_id, a.level), reverse=True)
            
            # C. Pagination Math
            total_pages = (len(accessories) + items_per_page - 1) // items_per_page
            current_page = min(current_page, max(0, total_pages - 1))
            
            # D. Slice Items
            start_idx = current_page * items_per_page
            page_items = accessories[start_idx:start_idx + items_per_page]

            # E. Generate UI
            embed = InventoryUI.get_list_embed(
                existing_user[3], page_items, current_page, total_pages, equipped_id, "📿"
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
                    selected_acc = page_items[idx]
                    await self._handle_item_actions(interaction, message, selected_acc)
            
            except asyncio.TimeoutError:
                break
        
        self.bot.state_manager.clear_active(user_id)
        if message:
            try: await message.delete()
            except: pass

    async def _handle_item_actions(self, interaction: Interaction, message: Message, accessory: Accessory):
        """Sub-loop for a specific item's actions."""
        user_id = str(interaction.user.id)
        
        while True:
            # Re-fetch item to get live stats
            raw = await self.bot.database.equipment.get_by_id(accessory.item_id, "accessory")
            if not raw: 
                await interaction.followup.send("Item no longer exists.", ephemeral=True)
                return
            accessory = create_accessory(raw)
            
            # Check equipped status dynamically
            equipped_raw = await self.bot.database.equipment.get_equipped(user_id, "accessory")
            is_equipped = equipped_raw and equipped_raw[0] == accessory.item_id

            embed = InventoryUI.get_item_details_embed(accessory, is_equipped)
            
            # Add Action Guide
            guide = ["- Equip/Unequip", "- Discard", "- Back"]
            
            # Logic: Check if improvable
            # Max passive level is implicitly 10 based on mechanics cost array length, 
            # but usually capped by attempts remaining.
            can_improve = accessory.potential_remaining > 0
            if can_improve: 
                guide.insert(1, "- Unlock/Improve Potential")
            
            guide.append("- Send")
            
            embed.add_field(name="Actions", value="\n".join(guide), inline=False)

            # Build View
            view = View(timeout=60)
            view.add_item(Button(label="Unequip" if is_equipped else "Equip", style=ButtonStyle.primary, custom_id="equip"))
            
            if can_improve:
                view.add_item(Button(label="Potential", style=ButtonStyle.success, custom_id="improve"))
                
            view.add_item(Button(label="Send", style=ButtonStyle.secondary, custom_id="send"))
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
                    if is_equipped: await self.bot.database.equipment.unequip(user_id, 'accessory')
                    else: await self.bot.database.equipment.equip(user_id, accessory.item_id, 'accessory')
                elif cid == "discard":
                    if await self._confirm_action(message, act.user, f"Discard **{accessory.name}**? This cannot be undone."):
                        await self.bot.database.equipment.discard(accessory.item_id, 'accessory')
                        return
                elif cid == "improve":
                    await self._improve_potential_flow(message, act.user, accessory)
                elif cid == "send":
                    if is_equipped:
                        embed.set_footer(text="Error: Unequip before sending.")
                        await message.edit(embed=embed)
                        await asyncio.sleep(2)
                        continue
                    if await self._send_item_flow(message, act.user, interaction, accessory):
                        return # Item sent, exit view

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

    async def _improve_potential_flow(self, message: Message, user, accessory: Accessory):
        """Handles the Potential UI and Logic."""
        uid, gid = str(user.id), str(message.guild.id)
        
        while True:
            cost = EquipmentMechanics.calculate_potential_cost(accessory.passive_lvl)
            player_gold = (await self.bot.database.users.get(uid, gid))[6]
            
            # Calculate Base Success Rate
            # Logic from Mechanics: max(75 - level*5, 30)
            success_rate = max(75 - (accessory.passive_lvl * 5), 30)
            
            title_keyword = "Unlock" if accessory.passive == "none" else "Enhance"
            
            embed = discord.Embed(
                title=f"{title_keyword} Potential", 
                description=(f"Attempts left: **{accessory.potential_remaining}**\n"
                            f"Cost: **{cost:,} GP**\n"
                            f"Success Rate: **{success_rate}%**"),
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url="https://i.imgur.com/Tkikr5b.jpeg")
            if player_gold < cost:
                embed.set_footer(text="Insufficient Gold.")
                await message.edit(embed=embed, view=None)
                await asyncio.sleep(2)
                return

            # Check for Runes
            runes = await self.bot.database.users.get_currency(uid, 'potential_runes')
            
            view = View(timeout=30)
            view.add_item(Button(label="Confirm", style=ButtonStyle.success, custom_id="confirm"))
            if runes > 0:
                view.add_item(Button(label=f"Use Rune (+25%)", style=ButtonStyle.primary, custom_id="use_rune"))
            view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel"))
            
            await message.edit(embed=embed, view=view)

            def check(i): return i.user.id == user.id and i.message.id == message.id
            try:
                act = await self.bot.wait_for('interaction', timeout=30, check=check)
                await act.response.defer()
                
                if act.data['custom_id'] == "cancel": return

                use_rune = (act.data['custom_id'] == "use_rune")
                
                # Re-check gold just in case
                if player_gold < cost: return

                # Consume resources
                await self.bot.database.users.modify_gold(uid, -cost)
                if use_rune:
                    await self.bot.database.users.modify_currency(uid, 'refinement_runes', -1)
                    success_rate += 25

                # Roll
                success = EquipmentMechanics.roll_potential_outcome(accessory.passive_lvl, use_rune)
                
                result_embed = discord.Embed(title="Potential Result", color=discord.Color.gold())
                
                if success:
                    if accessory.passive == "none":
                        new_passive = EquipmentMechanics.get_new_passive('accessory')
                        await self.bot.database.equipment.update_passive(accessory.item_id, 'accessory', new_passive)
                        await self.bot.database.equipment.update_counter(accessory.item_id, 'accessory', 'passive_lvl', 1)
                        result_embed.description = f"🎉 Success! Unlocked **{new_passive}**!"
                    else:
                        new_lvl = accessory.passive_lvl + 1
                        await self.bot.database.equipment.update_counter(accessory.item_id, 'accessory', 'passive_lvl', new_lvl)
                        result_embed.description = f"🎉 Success! Upgraded to **Level {new_lvl}**!"
                else:
                    result_embed.description = "💔 The enhancement failed."
                    result_embed.color = discord.Color.dark_grey()

                # Decrement potential
                await self.bot.database.equipment.update_counter(accessory.item_id, 'accessory', 'potential_remaining', accessory.potential_remaining - 1)
                
                await message.edit(embed=result_embed, view=None)
                await asyncio.sleep(3)

            except asyncio.TimeoutError:
                pass

    async def _send_item_flow(self, message: Message, user, interaction: Interaction, accessory: Accessory) -> bool:
        """Handles sending item logic. Returns True if sent."""
        uid, gid = str(user.id), str(message.guild.id)
        
        embed = discord.Embed(title=f"Send {accessory.name}", description="Please mention the user (@username) to send this item to.", color=discord.Color.blue())
        await message.edit(embed=embed, view=None)

        def msg_check(m: Message): 
            return m.author == user and m.channel == interaction.channel and m.mentions

        try:
            user_msg = await self.bot.wait_for('message', timeout=60, check=msg_check)
            await user_msg.delete()
            receiver = user_msg.mentions[0]

            # Validation
            if receiver.id == user.id:
                embed.description = "You cannot send items to yourself."
                await message.edit(embed=embed)
                await asyncio.sleep(2)
                return False

            receiver_db = await self.bot.database.users.get(str(receiver.id), gid)
            if not receiver_db:
                embed.description = "User is not registered."
                await message.edit(embed=embed)
                await asyncio.sleep(2)
                return False

            # Check Limits
            rec_level = receiver_db[4]
            if (accessory.level - rec_level > 15) and rec_level < 100:
                embed.description = "Item level gap is too high (>15)."
                await message.edit(embed=embed)
                await asyncio.sleep(2)
                return False
            
            rec_count = await self.bot.database.equipment.get_count(str(receiver.id, 'accessories'))
            if rec_count >= 58:
                embed.description = "Receiver's inventory is full."
                await message.edit(embed=embed)
                await asyncio.sleep(2)
                return False

            # Confirmation
            if await self._confirm_action(message, user, f"Send **{accessory.name}** to {receiver.mention}?"):
                await self.bot.database.equipment.transfer(accessory.item_id, str(receiver.id), 'accessory')
                embed.title = "Sent!"
                embed.description = f"Item sent to {receiver.mention}."
                embed.color = discord.Color.green()
                await message.edit(embed=embed, view=None)
                await asyncio.sleep(2)
                return True
            
            return False

        except asyncio.TimeoutError:
            return False

async def setup(bot) -> None:
    await bot.add_cog(Accessories(bot))