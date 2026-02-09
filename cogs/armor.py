import discord
import asyncio
import random
from discord.ext import commands
from discord import app_commands, Interaction, Message, ButtonStyle
from discord.ui import View, Button

# Core Imports
from core.models import Armor
from core.items.factory import create_armor
from core.items.equipment_mechanics import EquipmentMechanics
from core.ui.inventory import InventoryUI

class ArmorCog(commands.Cog, name="armor"):
    def __init__(self, bot) -> None:
        self.bot = bot
        # Armor specific passives list
        self.armor_passives = [
            "Invulnerable", "Mystical Might", "Omnipotent",
            "Treasure Hunter", "Unlimited Wealth", "Everlasting Blessing"
        ]

    async def _fetch_and_parse_armors(self, user_id: str) -> list[Armor]:
        """Helper to fetch raw DB data and convert to Objects."""
        raw_items = await self.bot.database.equipment.get_all(user_id, 'armor')
        if not raw_items: 
            return []
        return [create_armor(item) for item in raw_items]

    @app_commands.command(name="armor", description="View your character's armors and modify them.")
    async def view_armor(self, interaction: Interaction) -> None:
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
            armors = await self._fetch_and_parse_armors(user_id)
            
            # Handle Empty Inventory
            if not armors:
                if message:
                    await message.edit(content="Your armor pouch is empty.", embed=None, view=None)
                else:
                    await interaction.response.send_message("You search your gear for armor, you find none.")
                break

            # B. Sort: Equipped first, then by Level
            equipped_raw = await self.bot.database.get_equipped_armor(user_id)
            equipped_id = equipped_raw[0] if equipped_raw else None
            
            armors.sort(key=lambda a: (a.item_id == equipped_id, a.level), reverse=True)
            
            # C. Pagination Math
            total_pages = (len(armors) + items_per_page - 1) // items_per_page
            current_page = min(current_page, max(0, total_pages - 1))
            
            # D. Slice Items
            start_idx = current_page * items_per_page
            page_items = armors[start_idx:start_idx + items_per_page]

            # E. Generate UI
            embed = InventoryUI.get_list_embed(
                existing_user[3], page_items, current_page, total_pages, equipped_id, "🛡️"
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
                    selected_armor = page_items[idx]
                    await self._handle_item_actions(interaction, message, selected_armor)
            
            except asyncio.TimeoutError:
                break
        
        self.bot.state_manager.clear_active(user_id)
        if message:
            try: await message.delete()
            except: pass

    async def _handle_item_actions(self, interaction: Interaction, message: Message, armor: Armor):
        """Sub-loop for a specific item's actions."""
        user_id = str(interaction.user.id)
        
        while True:
            # Re-fetch item
            raw = await self.bot.database.fetch_armor_by_id(armor.item_id)
            if not raw: 
                await interaction.followup.send("Item no longer exists.", ephemeral=True)
                return
            armor = create_armor(raw)
            
            # Check equipped
            equipped_raw = await self.bot.database.get_equipped_armor(user_id)
            is_equipped = equipped_raw and equipped_raw[0] == armor.item_id

            embed = InventoryUI.get_item_details_embed(armor, is_equipped)
            
            # Add Action Guide
            guide = ["- Equip/Unequip", "- Discard", "- Back"]
            
            if armor.temper_remaining > 0: 
                guide.insert(1, "- Temper (Resources)")
            
            # Imbue check: Has rune slot (default logic) and no passive
            if armor.imbue_remaining > 0 and armor.passive == "none":
                guide.insert(1, "- Imbue (Rune)")

            guide.append("- Send")
            
            embed.add_field(name="Actions", value="\n".join(guide), inline=False)

            # Build View
            view = View(timeout=60)
            view.add_item(Button(label="Unequip" if is_equipped else "Equip", style=ButtonStyle.primary, custom_id="equip"))
            
            if armor.temper_remaining > 0:
                view.add_item(Button(label="Temper", style=ButtonStyle.success, custom_id="temper"))
            
            if armor.imbue_remaining > 0 and armor.passive == "none":
                view.add_item(Button(label="Imbue", style=ButtonStyle.primary, custom_id="imbue"))

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
                    if is_equipped: await self.bot.database.equipment.unequip(user_id, 'armor')
                    else: await self.bot.database.equipment.equip(user_id, armor.item_id, 'armor')
                elif cid == "discard":
                    if await self._confirm_action(message, act.user, f"Discard **{armor.name}**? Irreversible."):
                        await self.bot.database.equipment.discard(armor.item_id, 'armor')
                        return
                elif cid == "temper":
                    await self._temper_armor_flow(message, act.user, armor)
                elif cid == "imbue":
                    await self._imbue_armor_flow(message, act.user, armor)
                elif cid == "send":
                    if is_equipped:
                        embed.set_footer(text="Error: Unequip before sending.")
                        await message.edit(embed=embed)
                        await asyncio.sleep(2)
                        continue
                    if await self._send_item_flow(message, act.user, interaction, armor):
                        return

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

    async def _temper_armor_flow(self, message: Message, user, armor: Armor):
        """Handles the Tempering UI and Logic."""
        uid, gid = str(user.id), str(message.guild.id)
        
        costs = EquipmentMechanics.calculate_temper_cost(armor)
        if not costs: return

        # Check Resources
        mining = await self.bot.database.fetch_user_mining(uid, gid)
        wood = await self.bot.database.fetch_user_woodcutting(uid, gid)
        fish = await self.bot.database.fetch_user_fishing(uid, gid)
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
            title=f"Temper {armor.name}", 
            description=f"**Costs:**\n{cost_str}",
            color=discord.Color.green() if has_resources else discord.Color.red()
        )

        if not has_resources:
            embed.set_footer(text="Insufficient resources.")
            await message.edit(embed=embed, view=None)
            await asyncio.sleep(3)
            return

        view = View(timeout=30)
        view.add_item(Button(label="Temper!", style=ButtonStyle.success, custom_id="confirm"))
        view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel"))
        
        await message.edit(embed=embed, view=view)

        def check(i): return i.user.id == user.id and i.message.id == message.id
        try:
            act = await self.bot.wait_for('interaction', timeout=30, check=check)
            await act.response.defer()
            
            if act.data['custom_id'] != "confirm": return

            # Consume
            await self.bot.database.update_mining_resource(uid, gid, costs['ore_type'], -costs['ore_qty'])
            await self.bot.database.update_woodcutting_resource(uid, gid, f"{costs['log_type']}_logs", -costs['log_qty'])
            await self.bot.database.update_fishing_resource(uid, gid, f"{costs['bone_type']}_bones", -costs['bone_qty'])
            await self.bot.database.users.modify_gold(uid, -costs['gold'])

            # Roll
            success, stat, amount = EquipmentMechanics.roll_temper_outcome(armor)
            
            result_embed = discord.Embed(title="Temper Result", color=discord.Color.gold())
            if success:
                await self.bot.database.increase_armor_stat(armor.item_id, stat, amount)
                stat_name = "Percentage Damage Reduction" if stat == "pdr" else "Flat Damage Reduction"
                result_embed.description = f"🎊 Success! Increased **{stat_name}** by **{amount}**!"
            else:
                result_embed.description = "💔 Tempering failed. Resources consumed."
                result_embed.color = discord.Color.dark_grey()

            await self.bot.database.update_armor_temper_count(armor.item_id, armor.temper_remaining - 1)
            
            await message.edit(embed=result_embed, view=None)
            await asyncio.sleep(3)

        except asyncio.TimeoutError:
            pass

    async def _imbue_armor_flow(self, message: Message, user, armor: Armor):
        """Handles Imbuing Logic."""
        uid, gid = str(user.id), str(message.guild.id)
        
        # Check Rune
        user_data = await self.bot.database.users.get(uid, gid)
        imbue_runes = user_data[27] # Imbue runes index

        if imbue_runes <= 0:
            embed = discord.Embed(title="No Runes", description="You need a **Rune of Imbuing**.", color=discord.Color.red())
            await message.edit(embed=embed, view=None)
            await asyncio.sleep(2)
            return

        embed = discord.Embed(
            title="Imbue Armor",
            description=f"Use 1 Rune of Imbuing to apply a passive?\nSuccess Rate: **50%**",
            color=discord.Color.purple()
        )
        view = View(timeout=30)
        view.add_item(Button(label="Imbue", style=ButtonStyle.primary, custom_id="confirm"))
        view.add_item(Button(label="Cancel", style=ButtonStyle.secondary, custom_id="cancel"))
        
        await message.edit(embed=embed, view=view)

        def check(i): return i.user.id == user.id and i.message.id == message.id
        try:
            act = await self.bot.wait_for('interaction', timeout=30, check=check)
            await act.response.defer()
            if act.data['custom_id'] != "confirm": return

            await self.bot.database.users.modify_currency(uid, 'imbue_runes', -1)
            await self.bot.database.update_armor_imbue_count(armor.item_id, 0) # Set remaining to 0

            result_embed = discord.Embed(title="Imbue Result", color=discord.Color.purple())
            
            if random.random() <= 0.5:
                new_passive = random.choice(self.armor_passives)
                await self.bot.database.update_armor_passive(armor.item_id, new_passive)
                result_embed.description = f"✨ Success! Armor imbued with **{new_passive}**!"
            else:
                result_embed.description = "The rune shattered without effect."
                result_embed.color = discord.Color.dark_grey()

            await message.edit(embed=result_embed, view=None)
            await asyncio.sleep(3)

        except asyncio.TimeoutError:
            pass

    async def _send_item_flow(self, message: Message, user, interaction: Interaction, armor: Armor) -> bool:
        """Handles sending item logic. Returns True if sent."""
        uid, gid = str(user.id), str(message.guild.id)
        
        embed = discord.Embed(title=f"Send {armor.name}", description="Please mention the user (@username) to send this item to.", color=discord.Color.blue())
        await message.edit(embed=embed, view=None)

        def msg_check(m: Message): 
            return m.author == user and m.channel == interaction.channel and m.mentions

        try:
            user_msg = await self.bot.wait_for('message', timeout=60, check=msg_check)
            await user_msg.delete()
            receiver = user_msg.mentions[0]

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
            if (armor.level - rec_level > 15) and rec_level < 100:
                embed.description = "Item level gap is too high (>15)."
                await message.edit(embed=embed)
                await asyncio.sleep(2)
                return False
            
            rec_count = await self.bot.database.count_user_armors(str(receiver.id))
            if rec_count >= 58:
                embed.description = "Receiver's inventory is full."
                await message.edit(embed=embed)
                await asyncio.sleep(2)
                return False

            if await self._confirm_action(message, user, f"Send **{armor.name}** to {receiver.mention}?"):
                await self.bot.database.send_armor(str(receiver.id), armor.item_id)
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
    await bot.add_cog(ArmorCog(bot))