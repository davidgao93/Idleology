import random

# Define wheel segments and their weights
segments = [
    (0, 50),   # 50% chance to lose (0x)
    (1, 30),   # 30% chance to break even (1x)
    (2, 15),   # 15% chance to double (2x)
    (5, 4),    # 4% chance for 5x
    (25, 1)    # 1% chance for 25x 
]

# Create a list of outcomes based on the weights
outcomes = [multiplier for multiplier, weight in segments for _ in range(weight)]

def simulate_bets(num_bets, initial_bet):
    total_spent = 0
    total_won = 0

    for _ in range(num_bets):
        total_spent += initial_bet
        result_multiplier = random.choice(outcomes)
        total_won += initial_bet * result_multiplier
    
    profit = total_won - total_spent
    return total_spent, total_won, profit

# Parameters
num_bets = 10000  # Number of bets to simulate
initial_bet = 10000  # Amount for each bet

# Run simulation
total_spent, total_won, profit = simulate_bets(num_bets, initial_bet)

# Display results
print(f"Total Spent: ${total_spent}")
print(f"Total Won: ${total_won}")
print(f"Profit: ${profit}")

if profit > 0:
    print("You are in profit!")
else:
    print("You are at a loss.")
