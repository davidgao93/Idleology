import csv
import json

exp_table = {}

# Read the CSV file
with open('assets/exp.csv', mode='r') as file:
    reader = csv.DictReader(file)
    for row in reader:
        level = int(row['level'])
        experience = int(row['experience'])
        exp_table[level] = experience

# Step 2: Write the data to a JSON file
with open('exp.json', 'w') as json_file:
    json.dump({'levels': exp_table}, json_file, indent=4)
