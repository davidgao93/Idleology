import random

def calculate_gold_award(encounter_level, rarity, reward_scale):
    """Calculate gold award with diminishing returns based on rarity."""
    # Example diminishing return function
    gold_award = int(encounter_level ** 1.5)    
    final_gold_award = int(gold_award * (1+rarity)) * (1 + (reward_scale ** 1.3))
    
    return final_gold_award

# Simulation parameters
encounter_levels = range(1, 40)  # Testing from level 1 to 20
rarity_levels = [0.0, 0.25, 0.5, 0.75, 1.0]  # Different rarity levels
reward_scale = range(1,10)

# # Run simulations
# print("Encounter Level | Differential | Rarity | Gold Award")
# print("----------------|--------------|-------|-----------")

# for encounter_level in encounter_levels:
#     for reward in reward_scale:
#         for rarity in rarity_levels:
#             gold = calculate_gold_award(encounter_level, rarity, reward)
#             print(f"{encounter_level:<16} | {reward:<6} | {rarity:<6} | {gold:<10}")

# Optionally, you could store results in a list or write to a file for further analysis.

def slot_machine_simulation(iterations, starting_gold, bet_amount, simulations):
    emojis = ["🍒", "🔔", "⭐"]
    total_gold_changes = []

    for sim in range(simulations):
        player_gold = starting_gold
        
        for i in range(iterations):
            # Simulate the slot machine rolls
            reel_results = [random.choices(emojis, k=5) for _ in range(5)]
            
            # Create a counter for line matches
            line_matches = 0

            # Check for horizontal matches
            for row in reel_results:
                if len(set(row)) == 1:  # All items in the row are the same
                    line_matches += 1

            # Check for vertical matches
            for col in range(5):
                if len(set(reel_results[row][col] for row in range(5))) == 1:  # All items in the column are the same
                    line_matches += 1

            # Check for diagonal matches
            if len(set(reel_results[i][i] for i in range(5))) == 1:  # Top-left to bottom-right
                line_matches += 1
            if len(set(reel_results[i][4 - i] for i in range(5))) == 1:  # Top-right to bottom-left
                line_matches += 1

            # Determine if there was a win based on line matches
            win = line_matches > 0
            if win:
                player_gold += bet_amount * (line_matches) * 7
            else:
                player_gold -= bet_amount  # Lose the bet

            # Check if player is out of gold
            if player_gold <= 0:
                break

        total_gold_changes.append(player_gold)

    # Calculate the average expected value
    average_expected_value = sum(total_gold_changes) / len(total_gold_changes)
    return average_expected_value

# Example of running the simulation
iterations = 50    # Number of iterations per simulation
starting_gold = 100000  # Starting amount of gold
bet_amount = 2000   # Amount to bet for each spin
simulations = 1000  # Number of simulations to average

average_value = slot_machine_simulation(iterations, starting_gold, bet_amount, simulations)
print(f"The average expected value after {simulations} simulations is: {average_value:.2f}")