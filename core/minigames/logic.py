import random
from typing import List, Tuple

class BlackjackLogic:
    SUITS = ["♠️", "♥️", "♣️", "♦️"]
    RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    VALUES = {
        "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
        "J": 10, "Q": 10, "K": 10, "A": 11
    }

    @staticmethod
    def draw_card() -> Tuple[str, str, int]:
        rank = random.choice(BlackjackLogic.RANKS)
        suit = random.choice(BlackjackLogic.SUITS)
        return (rank, suit, BlackjackLogic.VALUES[rank])

    @staticmethod
    def calculate_score(hand: List[Tuple[str, str, int]]) -> int:
        score = sum(card[2] for card in hand)
        aces = sum(1 for card in hand if card[0] == "A")
        while score > 21 and aces > 0:
            score -= 10
            aces -= 1
        return score

    @staticmethod
    def format_hand(hand: List[Tuple[str, str, int]], hide_second: bool = False) -> str:
        if hide_second:
            return f"`{hand[0][0]}{hand[0][1]}` `??`"
        return " ".join([f"`{c[0]}{c[1]}`" for c in hand])

class RouletteLogic:
    # Standard Layout
    RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
    
    @staticmethod
    def spin_wheel() -> int:
        return random.randint(0, 36)

    @staticmethod
    def get_color(number: int) -> str:
        if number == 0: return "green"
        if number in RouletteLogic.RED_NUMBERS: return "red"
        return "black"

    @staticmethod
    def get_color_emoji(color: str) -> str:
        return {"red": "🟥", "black": "⬛", "green": "🟩"}.get(color, "❓")

    @staticmethod
    def check_win(bet_type: str, bet_target: str, result_num: int) -> bool:
        """
        bet_type: 'color', 'number', 'parity' (even/odd)
        bet_target: 'red', 'black', '17', 'even'
        """
        result_color = RouletteLogic.get_color(result_num)
        
        if bet_type == 'color':
            return bet_target == result_color
        elif bet_type == 'number':
            return int(bet_target) == result_num
        elif bet_type == 'parity':
            if result_num == 0: return False # 0 loses even/odd bets
            is_even = (result_num % 2 == 0)
            return (bet_target == 'even' and is_even) or (bet_target == 'odd' and not is_even)
        return False
    

class CrashLogic:
    @staticmethod
    def generate_crash_point() -> float:
        """
        Generates a crash multiplier using an inverse cumulative distribution.
        1% chance to crash instantly (1.00x).
        General formula: E = 0.99 / (1 - U)
        This provides a mathematically fair house edge of 1%.
        """
        u = random.random()
        # 1% instant crash chance
        if u >= 0.99:
            return 1.00
            
        # Standard crash formula
        crash_point = 0.99 / (1 - u)
        
        # Cap at 100x to prevent economy breaking edge cases
        return min(crash_point, 100.00)

    @staticmethod
    def get_next_multiplier(current_multiplier: float, time_elapsed: float) -> float:
        """
        Calculates visual multiplier growth.
        Exponential growth formula: M(t) = 1.0 * e^(0.06 * t)
        This makes it start slow and speed up, creating tension.
        """
        # Simplified incremental logic for Discord loop steps
        # Growth rate scales with current value to simulate acceleration
        growth = 0.1 + (current_multiplier * 0.05)
        return round(current_multiplier + growth, 2)
    

class HorseRaceLogic:
    def __init__(self):
        self.track_length = 20
        self.horses = [
            {"name": "Thunder Hoof", "emoji": "🐎", "pos": 0, "speed_var": (1, 4)},
            {"name": "Lightning Bolt", "emoji": "🦄", "pos": 0, "speed_var": (0, 5)}, # High variance
            {"name": "Old Reliable", "emoji": "🦓", "pos": 0, "speed_var": (2, 3)}, # Steady
            {"name": "Dark Horse", "emoji": "🐫", "pos": 0, "speed_var": (1, 4)}
        ]
        self.winner = None

    def advance_race(self) -> bool:
        """
        Advances all horses. Returns True if race is finished.
        """
        if self.winner: return True

        for horse in self.horses:
            # Random move based on horse's speed variance
            move = random.randint(*horse['speed_var'])
            
            # Small catch-up mechanic: If way behind, slight boost chance
            if horse['pos'] < (max(h['pos'] for h in self.horses) - 5):
                if random.random() < 0.3: move += 2

            horse['pos'] += move
            
            if horse['pos'] >= self.track_length and not self.winner:
                self.winner = horse
        
        return self.winner is not None

    def get_race_string(self) -> str:
        """Generates the visual track string."""
        track = ""
        for horse in self.horses:
            # Calculate progress
            prog = min(self.track_length, horse['pos'])
            
            # Draw lane
            lane = "➖" * prog + horse['emoji'] + "➖" * (self.track_length - prog)
            track += f"`{horse['name']}`\n|{lane}|🏁\n\n"
        return track