import random
from collections import Counter

# Define curio rewards and their odds
rewards = {
    "Level 100 Weapon": 0.005,
    "Level 100 Accessory": 0.005,
    "ilvl Weapon": 0.1,
    "ilvl Accessory": 0.05,
    "Rune of Refinement": 0.02,
    "Rune of Potential": 0.02,
    "100k": 0.1,
    "50k": 0.1,
    "10k": 0.1,
    "5k": 0.2,
    "Ore": 0.1,
    "Wood": 0.1,
    "Fish": 0.1,
}

def run_simulation(num_trials):
    # Prepare the reward pool based on the odds.
    reward_pool = []
    for reward, odds in rewards.items():
        count = int(odds * num_trials)  # Scale odds for realistic selection
        reward_pool.extend([reward] * count)

    # Run the selection simulation
    selected_rewards = [random.choice(reward_pool) for _ in range(num_trials)]
    
    # Count the occurrences of each reward
    reward_counts = Counter(selected_rewards)
    return reward_counts

# Run the simulation 1000 times
num_trials = 1000
results = run_simulation(num_trials)

# Print the results
for reward, count in results.items():
    print(f"{reward}: {count} times")
