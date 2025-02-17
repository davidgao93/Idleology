import asyncio
import aiohttp
import csv

API_MONSTERS_URL = "https://www.dnd5eapi.co/api/monsters"
PLACEHOLDER_IMAGE_URL = "https://www.dnd5eapi.co/api/images/monsters/acolyte.png"

async def fetch_monsters():
    async with aiohttp.ClientSession() as session:
        async with session.get(API_MONSTERS_URL) as response:
            if response.status == 200:
                data = await response.json()
                return data['results']
            else:
                print(f"Failed to fetch monsters: {response.status}")
                return []

async def fetch_monster_data(session, monster):
    monster_id = monster['index']
    async with session.get(f"{API_MONSTERS_URL}/{monster_id}") as monster_response:
        if monster_response.status == 200:
            monster_data = await monster_response.json()
            monster_name = monster_data['name']
            monster_level = monster_data.get('challenge_rating', "Unknown")
            
            # Check if an image exists
            if 'image' in monster_data and monster_data['image']:
                image_url = f"https://www.dnd5eapi.co{monster_data['image']}"
            else:
                image_url = PLACEHOLDER_IMAGE_URL
            
            return monster_name, monster_level, image_url
        else:
            print(f"Failed to fetch monster data for {monster['name']}: {monster_response.status}")
            return monster['name'], "Unknown", PLACEHOLDER_IMAGE_URL

async def main():
    monsters = await fetch_monsters()
    
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_monster_data(session, monster) for monster in monsters]
        results = await asyncio.gather(*tasks)

    # Write results to CSV
    with open("monsters.csv", mode='w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        # Write the header
        csv_writer.writerow(["monster_name", "monster_level", "image_url"])
        # Write the monster data
        csv_writer.writerows(results)

if __name__ == "__main__":
    asyncio.run(main())