import discord
from typing import List, Union
from core.models import Weapon, Armor, Accessory, Glove, Boot

Equipment = Union[Weapon, Armor, Accessory, Glove, Boot]

class InventoryUI:
    @staticmethod
    def get_list_embed(player_name: str, 
                       items: List[Equipment], 
                       page: int, 
                       total_pages: int, 
                       equipped_id: int = None,
                       category_emoji: str = "🎒") -> discord.Embed:
        """
        Generates the inventory list embed.
        """
        embed = discord.Embed(
            title=f"{category_emoji}",
            description=f"{player_name}'s Inventory (Page {page + 1}/{total_pages})",
            color=0x00FF00
        )
        
        if not items:
            embed.description = "This pouch is empty."
            return embed

        display_text = ""
        for index, item in enumerate(items):
            # Safe Stop if text gets too long
            if len(display_text) > 950:
                display_text += f"... and {len(items) - index} more on this page."
                break

            # Status flags
            is_equipped = (item.item_id == equipped_id)
            status_icon = " [E]" if is_equipped else ""
            
            # Details string construction
            details = []
            if hasattr(item, 'passive') and item.passive != "none":
                p_lvl = getattr(item, 'passive_lvl', '')
                p_lvl_str = f" {p_lvl}" if p_lvl else ""
                details.append(f"{item.passive.title()}{p_lvl_str}")
            
            # Weapon specific extra passives
            if isinstance(item, Weapon):
                if item.p_passive != "none": details.append(item.p_passive.title())
                if item.u_passive != "none": details.append(item.u_passive.title())

            details_str = f" - {', '.join(details)}" if details else ""
            
            display_text += f"**{index + 1}.**{status_icon} **{item.name}** (i{item.level}){details_str}\n"

        embed.add_field(name="Items", value=display_text, inline=False)
        embed.set_footer(text="Select an item number to view details/actions.")
        return embed

    @staticmethod
    def get_item_details_embed(item: Equipment, is_equipped: bool) -> discord.Embed:
        # ... (Same as before) ...
        embed = discord.Embed(
            title=f"**{item.name}** (i{item.level})",
            description="**[Equipped]**" if is_equipped else "Unequipped",
            color=0x00FFFF
        )

        stats = {
            "Attack": getattr(item, 'attack', 0),
            "Defence": getattr(item, 'defence', 0),
            "Rarity": getattr(item, 'rarity', 0),
            "Ward": getattr(item, 'ward', 0),
            "Crit": getattr(item, 'crit', 0),
            "Block": getattr(item, 'block', 0),
            "Evasion": getattr(item, 'evasion', 0),
            "PDR": getattr(item, 'pdr', 0),
            "FDR": getattr(item, 'fdr', 0),
        }

        for label, value in stats.items():
            if value > 0:
                val_str = f"{value}%" if label in ["Rarity", "Ward", "Crit", "PDR"] else str(value)
                embed.add_field(name=label, value=val_str, inline=True)

        main_passive = getattr(item, 'passive', 'none')
        if main_passive != 'none':
            lvl = getattr(item, 'passive_lvl', 0)
            lvl_str = f" (Lvl {lvl})" if lvl > 0 else ""
            embed.add_field(name="Passive", value=f"{main_passive.title()}{lvl_str}", inline=False)
        
        if isinstance(item, Weapon):
            if item.p_passive != 'none':
                embed.add_field(name="Pinnacle Passive", value=item.p_passive.title(), inline=False)
            if item.u_passive != 'none':
                embed.add_field(name="Utmost Passive", value=item.u_passive.title(), inline=False)
            embed.add_field(name="Refinement", value=f"+{item.refinement_lvl}", inline=True)

        return embed