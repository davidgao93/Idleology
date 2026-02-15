import discord
from discord.ext import commands
from discord import app_commands, Interaction

# Core
from core.items.factory import create_weapon, create_armor, create_accessory, create_glove, create_boot, create_helmet
from core.inventory.views import InventoryListView

class Inventory(commands.Cog, name="inventory"):
    def __init__(self, bot):
        self.bot = bot

    async def _generic_inventory_command(self, interaction: Interaction, item_type: str, factory_func, emoji: str):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        if not await self.bot.check_is_active(interaction, user_id): return

        self.bot.state_manager.set_active(user_id, "inventory")

        # 2. Fetch Data
        raw_items = await self.bot.database.equipment.get_all(user_id, item_type)
        if not raw_items:
            self.bot.state_manager.clear_active(user_id)
            return await interaction.response.send_message(f"You search your bags for {item_type}s, but find nothing.")

        # 3. Process Models
        items = [factory_func(item) for item in raw_items]
        
        # 4. Sort (Equipped first, then Level descending)
        equipped_raw = await self.bot.database.equipment.get_equipped(user_id, item_type)
        equipped_id = equipped_raw[0] if equipped_raw else None
        
        items.sort(key=lambda x: (x.item_id == equipped_id, x.level), reverse=True)

        # 5. Launch View
        view = InventoryListView(self.bot, user_id, items, emoji)
        # Note: We need to pass the user name for the embed title
        embed = await view.get_current_embed(interaction.user.display_name)
        
        await interaction.response.send_message(embed=embed, view=view)

    # --- Commands ---

    @app_commands.command(name="inventory", description="Check your inventory summary.")
    async def inventory_summary(self, interaction: Interaction):
        """Fetch and display the user's inventory status."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return

        # 1. Counts
        w_count = await self.bot.database.equipment.get_count(user_id, 'weapon')
        a_count = await self.bot.database.equipment.get_count(user_id, 'accessory') # Note: 'accessory' not 'accessories' based on type map
        ar_count = await self.bot.database.equipment.get_count(user_id, 'armor')
        g_count = await self.bot.database.equipment.get_count(user_id, 'glove')
        b_count = await self.bot.database.equipment.get_count(user_id, 'boot')
        h_count = await self.bot.database.equipment.get_count(user_id, 'helmet')

        # 2. Currencies (Indices based on your schema comments)
        gold = existing_user[6]
        potions = existing_user[16]
        
        # Runes
        r_refine = existing_user[19]
        r_potential = existing_user[21]
        r_imbue = existing_user[27]
        r_shatter = existing_user[31]

        # Keys/Misc
        k_dragon = existing_user[25]
        k_angel = existing_user[26]
        k_void = existing_user[30]
        soul_cores = existing_user[28]
        void_frags = existing_user[29]
        curios = existing_user[22]

        embed = discord.Embed(
            title=f"{existing_user[3]}'s Bag 🎒",
            description=f"💰 **Gold:** {gold:,}\n🧪 **Potions:** {potions:,}",
            color=0x00FF00
        )
        embed.set_thumbnail(url=existing_user[7])

        embed.add_field(name="📦 **Equipment**", 
            value=(f"⚔️ Weapons: {w_count}\n"
                   f"🛡️ Armor: {ar_count}\n"
                   f"📿 Accessories: {a_count}\n"
                   f"🧤 Gloves: {g_count}\n"
                   f"👢 Boots: {b_count}\n"
                   f"🪖 Helmets: {h_count}"), 
            inline=True
        )

        embed.add_field(name="💎 **Runes**", 
            value=(f"🔨 Refinement: {r_refine}\n"
                   f"✨ Potential: {r_potential}\n"
                   f"🔮 Imbuing: {r_imbue}\n"
                   f"💥 Shatter: {r_shatter}"), 
            inline=True
        )

        embed.add_field(name="🔑 **Key Items**", 
            value=(f"🐉 Draconic Keys: {k_dragon}\n"
                   f"🪽 Angelic Keys: {k_angel}\n"
                   f"🗝️ Void Keys: {k_void}\n"
                   f"❤️‍🔥 Soul Cores: {soul_cores}\n"
                   f"🟣 Void Frags: {void_frags}\n"
                   f"🎁 Curios: {curios}"), 
            inline=True
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="weapons", description="Manage your weapons.")
    async def weapons(self, interaction: Interaction):
        await self._generic_inventory_command(interaction, "weapon", create_weapon, "⚔️")

    @app_commands.command(name="armor", description="Manage your armor.")
    async def armor(self, interaction: Interaction):
        await self._generic_inventory_command(interaction, "armor", create_armor, "🛡️")

    @app_commands.command(name="accessory", description="Manage your accessories.")
    async def accessory(self, interaction: Interaction):
        await self._generic_inventory_command(interaction, "accessory", create_accessory, "📿")

    @app_commands.command(name="gloves", description="Manage your gloves.")
    async def gloves(self, interaction: Interaction):
        await self._generic_inventory_command(interaction, "glove", create_glove, "🧤")

    @app_commands.command(name="boots", description="Manage your boots.")
    async def boots(self, interaction: Interaction):
        await self._generic_inventory_command(interaction, "boot", create_boot, "👢")

    @app_commands.command(name="helmets", description="Manage your helmets.")
    async def helmets(self, interaction: Interaction):
        await self._generic_inventory_command(interaction, "helmet", create_helmet, "🪖")

async def setup(bot):
    await bot.add_cog(Inventory(bot))