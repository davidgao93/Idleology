import random
import math

def simulate_crash_probabilities(num_simulations: int):
    probabilities = {}
    for _ in range(num_simulations):
        crash_point = round(min(10.0, -math.log(random.random()) / 2), 2)

        # Increment the probability for various cash out multipliers
        for multiplier in [i * 0.1 for i in range(1, 101)]:  # From 0.1 to 10.0
            if multiplier <= crash_point:
                if multiplier not in probabilities:
                    probabilities[multiplier] = 0
                probabilities[multiplier] += 1
                
    # Normalize probabilities
    for multiplier in probabilities:
        probabilities[multiplier] /= num_simulations
    
    return probabilities

def calculate_expected_values(probabilities):
    expected_values = {}
    bet_amount = 1  # Assume a bet amount of 1

    for multiplier, prob in probabilities.items():
        payout = multiplier * bet_amount
        exp_value = (prob * payout) - ((1 - prob) * bet_amount)
        expected_values[multiplier] = exp_value
    
    return expected_values

def find_optimal_cash_out(expected_values):
    optimal_multiplier = max(expected_values, key=expected_values.get)
    max_expected_value = expected_values[optimal_multiplier]
    
    return optimal_multiplier, max_expected_value

if __name__ == "__main__":
    num_simulations = 100000  # Number of simulations to run for better accuracy

    probabilities = simulate_crash_probabilities(num_simulations)
    expected_values = calculate_expected_values(probabilities)
    
    optimal_multiplier, max_expected_value = find_optimal_cash_out(expected_values)
    
    print(f"Optimal cash-out multiplier: {optimal_multiplier:.2f}, Max Expected Value: {max_expected_value:.4f}")
