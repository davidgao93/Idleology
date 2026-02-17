import random
from typing import List, Dict, Tuple, Any

class EncounterManager:
    @staticmethod
    def check_boss_door(player_level: int, currencies: dict) -> Tuple[bool, str, dict]:
        """
        Determines if a boss door appears.
        Returns: (triggered, boss_type, cost_dict)
        """
        roll = random.random()
        
        # 1. Aphrodite (Ascension)
        if player_level >= 20 and currencies['dragon_key'] > 0 and currencies['angel_key'] > 0 and roll < 0.20:
            return True, "aphrodite", {'dragon_key': 1, 'angel_key': 1}

        # 2. Lucifer (Infernal)
        elif player_level >= 20 and currencies['soul_cores'] >= 5 and 0.20 <= roll < 0.40:
            return True, "lucifer", {'soul_cores': 5}
        
        # 3. Gemini
        elif player_level >= 30 and currencies['balance_fragment'] >= 2 and 0.40 <= roll < 0.60:
            return True, "gemini", {'balance_fragment': 2}

        # 4. NEET (Void)
        elif player_level >= 40 and currencies['void_frags'] >= 3 and 0.60 <= roll < 0.80:
            return True, "NEET", {'void_frags': 3}
    


        return False, "", {}

    @staticmethod
    def get_door_details(boss_type: str) -> Dict[str, str]:
        if boss_type == "aphrodite":
            return {
                "title": "Door of Ascension",
                "desc": "Your **Angelic** and **Draconic** keys tremble.\nChallenge the heavens?",
                "img": "https://i.imgur.com/PXOhTbX.png",
                "cost_str": "-1 Dragon Key, -1 Angelic Key"
            }
        elif boss_type == "lucifer":
            return {
                "title": "Door of the Infernal",
                "desc": "Your soul cores tremble. Consume **5** to challenge the depths?",
                "img": "https://i.imgur.com/bWMAksf.png",
                "cost_str": "-5 Soul Cores"
            }
        elif boss_type == "NEET":
            return {
                "title": "Sad Anime Kid",
                "desc": "A sad kid in the rain. Your **void fragments** resonate.\nTake **3** out and investigate?",
                "img": "https://i.imgur.com/6f9OJ4s.jpeg",
                "cost_str": "-3 Void Fragments"
            }
        elif boss_type == "gemini":
            return {
                "title": "The Twin Gates",
                "desc": "Your **Fragments of Balance** hums in resonance.\nWill you attempt to merge them?",
                "img": "https://i.imgur.com/em9ZGer.png", 
                "cost_str": "-2 Fragment of Balance"
            }
        return {}

    @staticmethod
    def get_boss_phases(boss_type: str) -> List[Dict[str, Any]]:
        if boss_type == 'aphrodite':
            return [
                {"name": "Aphrodite, Heaven's Envoy", "level": 886, "modifiers_count": 3, "hp_multiplier": 1.5},
                {"name": "Aphrodite, the Eternal", "level": 887, "modifiers_count": 6, "hp_multiplier": 2},
                {"name": "Aphrodite, Harbinger of Destruction", "level": 888, "modifiers_count": 9, "hp_multiplier": 2.5},
            ]
        elif boss_type == 'lucifer':
            return [
                {"name": "Lucifer, Fallen", "level": 663, "modifiers_count": 2, "hp_multiplier": 1.25},
                {"name": "Lucifer, Maddened", "level": 664, "modifiers_count": 3, "hp_multiplier": 1.5},
                {"name": "Lucifer, Enraged", "level": 665, "modifiers_count": 4, "hp_multiplier": 1.75},
                {"name": "Lucifer, Unbound", "level": 666, "modifiers_count": 5, "hp_multiplier": 2},
            ]
        elif boss_type == 'NEET':
            return [
                {"name": "NEET, Sadge", "level": 444, "modifiers_count": 1, "hp_multiplier": 1.25},
                {"name": "NEET, Madge", "level": 445, "modifiers_count": 2, "hp_multiplier": 1.5},
                {"name": "NEET, REEEEEE", "level": 446, "modifiers_count": 3, "hp_multiplier": 1.75},
                {"name": "NEET, Deadge", "level": 447, "modifiers_count": 5, "hp_multiplier": 0.2},
            ]
        elif boss_type == 'gemini':
            return [
                {"name": "Castor the Mortal", "level": 555, "modifiers_count": 3, "hp_multiplier": 1.2}, # High Phys Def
                {"name": "Pollux the Divine", "level": 556, "modifiers_count": 3, "hp_multiplier": 1.2}, # High Magic/Dodge
                {"name": "The Gemini Twins", "level": 557, "modifiers_count": 5, "hp_multiplier": 2.0}, # Enraged
            ]
        return []