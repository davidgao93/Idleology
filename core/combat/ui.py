import discord
from typing import Dict, Optional, Any
from core.models import Player, Monster
from core.gen_mob import get_modifier_description

def get_hp_display(current: int, max_hp: int, ward: int) -> str:
    """Formats HP string, e.g., '100/100 ❤️ (50 🔮)'"""
    display = f"{current}/{max_hp} ❤️"
    if ward > 0:
        display += f" ({ward} 🔮)"
    return display

def create_combat_embed(player: Player, monster: Monster, logs: Dict[str, str] = None, title_override: str = None) -> discord.Embed:
    """
    Generates the main combat interface embed.
    
    Args:
        player: The Player object.
        monster: The Monster object.
        logs: A dictionary where Key is the field name (e.g., 'Player Name') and Value is the log text.
        title_override: Optional title to replace the default 'Witness {player}...'
    """
    logs = logs or {}
    
    # Calculate hit chances for display
    # Note: We re-calculate here purely for display purposes. 
    # Ideally, engine could pass these, but calculating them is cheap.
    from core.combat_calcs import calculate_hit_chance, calculate_monster_hit_chance
    p_hit = int(calculate_hit_chance(player, monster) * 100)
    m_hit = int(calculate_monster_hit_chance(player, monster) * 100)

    # Description generation
    mod_text = ""
    if monster.modifiers:
        mod_text = "\n__Modifiers__\n" + "\n".join([f"**{m}**: {get_modifier_description(m)}" for m in monster.modifiers])
    
    description = (f"A level **{monster.level}** {monster.name} approaches!\n"
                   f"{mod_text}\n\n"
                   f"~{p_hit}% to hit | ~{m_hit}% to be hit")

    title = title_override if title_override else f"Witness {player.name} (Level {player.level})"
    
    embed = discord.Embed(title=title, description=description, color=0x00FF00)
    embed.set_image(url=monster.image)
    
    # Status Fields
    embed.add_field(name="🐲 HP", value=f"{monster.hp}/{monster.max_hp}", inline=True)
    embed.add_field(name="❤️ HP", value=get_hp_display(player.current_hp, player.max_hp, player.combat_ward), inline=True)

    # Log Fields (Attack messages, Heals, etc.)
    for name, message in logs.items():
        if message:
            embed.add_field(name=name, value=message, inline=False)
            
    return embed

def create_victory_embed(player: Player, monster: Monster, rewards: Dict[str, Any]) -> discord.Embed:
    """
    Generates the Victory screen.
    rewards dict expected keys: 'xp', 'gold', 'curios', 'items' (list of strings), 'special' (list of strings)
    """
    embed = discord.Embed(
        title="Victory! 🎉",
        description=f"{player.name} has slain the {monster.name} with {player.current_hp} ❤️ remaining!",
        color=0x00FF00,
    )
    
    # Passive Proc Messages (Prosper, Infinite Wisdom, etc)
    if rewards.get('msgs'):
        for msg in rewards['msgs']:
            embed.add_field(name="Bonus", value=msg, inline=False)

    embed.add_field(name="📚 Experience", value=f"{rewards.get('xp', 0):,} XP")
    embed.add_field(name="💰 Gold", value=f"{rewards.get('gold', 0):,} GP")
    
    if rewards.get('curios', 0) > 0:
        embed.add_field(name="🎁 Curios", value=f"{rewards['curios']} Curious Curios")

    # Items
    items = rewards.get('items', [])
    if items:
        for item_desc in items:
            embed.add_field(name="✨ Loot", value=item_desc, inline=False)
    else:
        embed.add_field(name="✨ Loot", value="None", inline=False)

    # Special Drops (Keys, Runes)
    specials = rewards.get('special', [])
    if specials:
        for special in specials:
            embed.add_field(name="✨ Special Drop", value=special, inline=False)

    return embed

def create_defeat_embed(player: Player, monster: Monster, lost_xp: int) -> discord.Embed:
    """Generates the Defeat screen."""
    total_damage_dealt = monster.max_hp - monster.hp
    description = (f"The {monster.name} deals a fatal blow!\n"
                   f"{player.name} has been defeated after dealing {total_damage_dealt:,} damage.\n"
                   f"The {monster.name} leaves with {monster.hp:,} health remaining.\n"
                   f"Death 💀 takes away {lost_xp:,} XP from your essence...")
    
    embed = discord.Embed(title="Oh dear...", description=description, color=0xFF0000)
    embed.add_field(name="🪽 Redemption 🪽", value=f"({player.name} revives with 1 HP.)")
    return embed