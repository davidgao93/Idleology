import random

def simulate_keys(num_iterations):
    draconic_keys = 0
    angelic_keys = 0

    for _ in range(num_iterations):
        # Check for Draconic Key
        if random.random() <= 0.03:
            draconic_keys += 1
        
        # Check for Angelic Key
        if random.random() >= 0.97:
            angelic_keys += 1

    return draconic_keys, angelic_keys

# Run the simulation for 10,000 iterations
num_iterations = 100000
draconic_keys, angelic_keys = simulate_keys(num_iterations)

# Print the results
print(f"After {num_iterations} iterations:")
print(f"Draconic Keys: {draconic_keys}")
print(f"Angelic Keys: {angelic_keys}")
