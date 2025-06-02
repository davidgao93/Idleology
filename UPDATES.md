### Version 0.3
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
        - Lucky Strikes (1-10) 10/20/30/40/50/60/70/80/90/100% chance to roll lucky hit chance
            - Lucky means an attack chance to hit is rolled twice and the best result is taken
    - Once an accessory hits potential tier X it can no longer be upgraded. It also can't be upgraded once it runs out of potential.
    - You can boost the success rate with a Rune of Potential. These are dropped rarely from various sources.
        - Runes grant a 25% chance to not consume a potential attempt. 
    - Accessories can be sent to other players
    - Accessories are managed using /accessory
    - Accessories drop during combat encounters, their drop rate is lower than that of weapons
        - Accessories are rolled when a roll for a weapon fails
    - You can send accessories using the /send_accessory command

- Added Curious Curios
    - Curios can now be purchased from the tavern shop
    - /checkin is now changed to award 1 curio per cooldown period
        - To prevent abuse, you can only /checkin after your adventurer is 18 hours old
    - Curios cost 8k gold each, and can award from the following loot table:
        - Gold
        - Skilling materials
        - Runes
        - Equipment of your level
        - Accessory of your level
        - A level 100 weapon or accessory
    - You can purchase up to 5 Curios per /checkin, which refreshes the tavern curio stock.

- Added PvP
    - You can initiate a PVP encounter by using /challenge @user #gold_amount you wish to ante
    - The challenged user (needs to have at least the gold amount) then has a minute to accept the challenge
    - Once the PVP encounter starts, a dice roll will determine turn order
    - Players start at 100 HP with a decision to either ATTACK or HEAL
    - ATTACK will roll an attack attempt against the other player
    - HEAL will heal a flat amount of 20 HP
    - The lower your HP is, the higher the potential maximum hit, with a potential max hit of 99 at 1 HP
    - Accuracy stays the same throughout the encounter
    - If a duel times out on your turn it is forfeit and you surrender your gold to the winner
        - A turn has a limit of 60 seconds


    
CHANGES
- Changed /inventory to instead show potions, gold, runes, # of weapons, and # of accessories
- Old /inventory is now /weapons to view weapon inventory
- Changed /send_weapon to /send_weapon
- The leveling curve has been adjusted
- Early combat difficulty has been dramatically reduced
- Monsters at all levels now award a base gold of 20 instead of 1
- You now receive a warning before combat if your weapons/accessory pouches are full
- /stats now displays useful information about your statistics instead
- /inventory now displays the # of weapons, accessories, runes, potions, and gold that you have
- Rare encounters always drop a curious curio
- Updated /getstarted with tips