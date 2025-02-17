# Mapping of passive categories to their associated messages
passive_messages = {
    "burning": "Increases your maximum hit (1d6).",
    "flaming": "Increases your maximum hit. (2d6)",
    "scorching": "Increases your maximum hit. (3d6)",
    "incinerating": "Increases your maximum hit. (4d6)",
    "carbonising": "Increases your maximum hit. (5d6)",
    
    "poisonous": "Additional damage on misses. (3d6)",
    "noxious": "Additional damage on misses. (4d6)",
    "venomous": "Additional damage on misses. (5d6)",
    "toxic": "Additional damage on misses. (6d6)",
    "lethal": "Additional damage on misses. (7d6)",
    
    "polished": "Reduce monster's defence. (5%)",
    "honed": "Reduce monster's defence. (10%)",
    "gleaming": "Reduce monster's defence. (15%)",
    "tempered": "Reduce monster's defence. (20%)",
    "flaring": "Reduce monster's defence. (25%)",
    
    "sparking": "Additional damage on normal hits. (2d6)",
    "shocking": "Additional damage on normal hits. (3d6)",
    "discharging": "Additional damage on normal hits. (4d6)",
    "electrocuting": "Additional damage on normal hits. (5d6)",
    "vapourising": "Additional damage on normal hits. (6d6)",
    
    "sturdy": "Additional defence. (+3)",
    "reinforced": "Additional defence. (+6)",
    "thickened": "Additional defence. (+9)",
    "impregnable": "Additional defence. (+12)",
    "impenetrable": "Additional defence. (+15)",
    
    "piercing": "Additional crit chance. (3%)",
    "keen": "Additional crit chance. (6%)",
    "incisive": "Additional crit chance. (9%)",
    "puncturing": "Additional crit chance. (12%)",
    "penetrating": "Additional crit chance. (15%)",
    
    "strengthened": "Culling strike.",
    "forceful": "Culling strike.",
    "overwhelming": "Culling strike.",
    "devastating": "Culling strike.",
    "catastrophic": "Culling strike.",
    
    "accurate": "Increased accuracy.",
    "precise": "Increased accuracy.",
    "sharpshooter": "Increased accuracy.",
    "deadeye": "Increased accuracy.",
    "bullseye": "Increased accuracy.",
    
    "echo": "Echo normal hits.",
    "echoo": "Echo normal hits.",
    "echooo": "Echo normal hits.",
    "echoooo": "Echo normal hits.",
    "echoes": "Echo normal hits."
}

# Function to get the message for a given passive
def get_passive_message(passive):
    # Check if the passive is among the defined categories
    if passive in passive_messages:
        return passive_messages[passive]
    return "Passive effect not recognized."

# Example usage
passives = [
    "burning", "flaming", "scorching", "incinerating", "carbonising",
    "poisonous", "noxious", "venomous", "toxic", "lethal",
    "polished", "honed", "gleaming", "tempered", "flaring",
    "sparking", "shocking", "discharging", "electrocuting", "vapourising",
    "sturdy", "reinforced", "thickened", "impregnable", "impenetrable",
    "piercing", "keen", "incisive", "puncturing", "penetrating",
    "strengthened", "forceful", "overwhelming", "devastating", "catastrophic",
    "accurate", "precise", "sharpshooter", "deadeye", "bullseye",
    "echo", "echoo", "echooo", "echoooo", "echoes"
]

for passive in passives:
    message = get_passive_message(passive)
    print(f"{passive}: {message}")

