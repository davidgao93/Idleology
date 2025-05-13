### Version 0.2
CONTENT
- Added accessories
    - Accessories can roll between atk, def, rarity, crit, and ward (bonus shield based off max hp granted before each combat)
    - Accessories can only have ONE stat
    - Accessories can have up to 10 potential
    - If an accessory does not have potential, potential can be unlocked, upon success, potential picks from the following:
        - Obliterate (1-10) 2/4/6/8/10/12/14/16/18/20% chance to deal double damage
        - Absorb (1-10) 2/4/6/8/10/12/14/16/18/20% chance to absorb 10% of the monsters stats and add to your own
        - Prosper (1-10) 5/10/15/20/25/30/35/40/45/50% chance to double gold earned
        - Infinite Wisdom (1-10) 5/10/15/20/25/30/35/40/45/50% chance to double exp earned
        - Lucky Strikes (1-10) 10/20/30/40/50/60/70/80/90/100% chance to roll lucky damage
            - Lucky means an attack hit is rolled twice and the best result is taken
            - This only affects the base damage and does not take into account any other passive sources
    - Once an accessory hits potential tier X it can no longer be upgraded. It also can't be upgraded once it runs out of potential.
    - You can boost the success rate with a Rune of Potential. These are dropped rarely from various sources.
        - Runes grant a 25% chance to not consume a potential attempt. 
    - Accessories can be sent to other players
    - Accessories are managed using /accessory
    - Accessories drop during combat encounters, their drop rate is lower than that of weapons
    - You can send accessories using the /send_accessory command

- Added Curious Curios
    - Curios can now be purchased from the tavern shop
    - /checkin is now changed to award 1 curio per cooldown period
        - To prevent abuse, you can only /checkin after your adventurer is 1 day old
    - Curios cost 8k gold each, and can award from the following loot table:
        - Gold
        - Skilling materials
        - Runes
        - Equipment of your level
        - Accessory of your level
        - A level 100 weapon or accessory
    - You can purchase up to 3 Curios per day.

- Added PvP
    - /pvp will display the current PVP leaderboards
    - You can initiate a PVP encounter by using /challenge @user you wish to challenge
    - The challenged user then has a minute to accept the challenge
    - Once the PVP encounter starts, a dice roll will determine turn order
    - Players start at 100 HP with a decision to either ATTACK or HEAL
    - ATTACK will roll an attack attempt against the other player
    - HEAL will heal a flat amount of 20 HP
    - The lower your HP is, the higher the potential maximum hit, with a potential max hit of 99 at 1 HP
    - Accuracy stays the same throughout the encounter
    - Winning a PVP encounter will award 500 Glory, while the loser gets nothing
    - You are limited to sending 1 /challenge per hour, but can participate in an unlimited amount of encounters per hour
    - Glory can be spent in the /arena 
        - You can buy a sack of gold for 500 Glory
        - A bundle of gold for 5,000 Glory
        - A casket of gold for 10,000 Glory
        - A curious curio for 4,000 Glory
        - These will award varying amounts of gold with higher tier versions offering a better chance for 100k gold
- Added some variation to rare encounters
    - Rare encounters have a chance to also drop a curious curio


CHANGES
- Changed /inventory to instead show potions, gold, runes, # of weapons, and # of accessories
- Old /inventory is now /weapons to view weapon inventory
- Changed /send_item to /send_weapon
- The leveling curve has been adjusted to smooth out the full experience
- Early combat difficulty has been dramatically reduced
- Monsters at all levels now award a base gold of 20 instead of 1