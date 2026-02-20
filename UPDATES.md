### Version 0.72
3 new settlement buildings:
    Companion Ranch - generates companion cookies that provide XP for pets
    Black Market - Trade refined materials, void keys, and shatter runes for various caches
Fixed item menus not displaying correctly
Fixed resources not being granted by pets and settlements
Killing lucifer once again explains what cores do
Expanded base settlement structures from 3 to 5


### Version 0.71
Pet rerolling can no longer hit the same passive, added confirm to partner rune
Town hall has an upgrade option
Settlements can no longer build dupe buildings and buildings have more info
Fixed item menus not displaying correctly
Fixed resources not being granted by settlements
Add exp to next level for delve and an xp tracker to see how far you are
Player stats now reset properly between each boss phase and won't scale to infinity
Boss pets can now drop, at a 3% drop rate, boss pets are always T3+
Rune of potentials can once again be used to increase enchant chance on accessories
    They can also be used for armor tempers (10% inc), glove/helm/boot passive increase (15% inc)
    

### Version 0.7
CONTENT
- You can now fuse pets together
    Fusing pets picks a passive, look, tier randomly from each donor
    The new pet level will be calculated based on the total exp of the donors

- /combat dummy now generates a dummy to hit, you can simulate 100 turns of combat to calculate your damage per turn.
- You can add a mod, a boss mod, or clear the mod list.
- You can select from a variety of presets (your combat level, +10 combat, +20 combat, +50 combat)
- Added the /delve minigame
    You can delve for curios and obsidian shards
    Spend obsidian shards at the /delve store for delving specific upgrades
    Keep your fuel above 1 to return to the surface with your loot!
    All loot is lost upon failure
    Delve is infinitely repeatable as long as you have gp
- Added the /settlement feature
    You can assign followers to various buildings
    Buildings can be upgraded with materials from the settlement, higher tiers of upgrades are attainable via refined skilling materials and special monster drops
    You start with a 3 building capacity and can upgrade to add more buildings later on.
    Forging weapons and tempering armor will can use both refined materials and unrefined materials at a 1:1 rate
    Refined materials will be used for further enhancements in the future
    You can see your accumulated resources with the /resources command

MECHANIC CHANGES / FIXES
- speedster buffed - combat cooldown reduced by ~~20/40/60/80/100/120s ~~ -> 60/120/180/240/300/360s
- Propagate no longer provides gold

### Version 0.6
CONTENT
- Lose money faster than ever before with restart options when /gambleing
- Added companions AKA pets
    Your menagerie has a limit of 20 companions
    You can have up to 3 active companions at a time
    You have a 5% chance of capturing any victiorious monster encounter as a companion, excluding bosses
    Companions can roll from t1 - t3
    Companions have passives:
    Base Atk boost
    Base Def Boost
    + to all hit rolls
    + to all crit rolls
    % hp as ward
    % base rarity
    % special loot rarity
    + FDR
    + PDR

    You can upgrade companion passives using the rune of partnership, dropped from the new Gemini Twins boss, which can be accessed with Fragments of Balance
    Using a rune rerolls the passive, with a chance of tiering up
    Companions are fully tradeable.
    Companions gather loot every 30 minutes, saving loot up to 2 days. You can collect with /companions collect
    Loot quality increases with levels.
    Companions level up when you discard equipment, only active ones gain exp, which is distributed evenly.

MECHANIC CHANGES / FIXES
- Rewrote random events, leprechaun now grants a curio
- Inventory management rewrite, still same commands but cleaner now
- Rewrote combat / ascent to use buttons, ascent by default auto-skips, combat now lets you do 10 turns at a time (no auto), or full auto but 1s per turn
- Rewrote trade to use a menu
- Rewrote registration to use a menu
- Rewrote skills to use buttons
- Rewrote shop to use buttons
- Rewrote PVP to use buttons
- Upgrade actions for gear are now more easily repeatable
- Curios now opens an interface, /bulk_curios lets you open as many as you want
- Inventory now displays more stats next to items

### Version 0.5
CONTENT
- Giga engine work
- Added helmets, which can roll one of DEF/Ward and PDR/FDR
- Helmets can unlock the following passives:
    Juggernaut (1-5) 4/8/12/16/20% of Base DEF is added as ATK
    Insight (1-5) Increases Crit DMG multiplier by +0.1x/+0.2x/+0.3x/+0.4x/+0.5x (Base 2.0x)
    Volatile (1-5) On Ward break, deal 100/200/300/400/500% of Max HP as damage
    Divine (1-5) 100/200/300/400/500% of potion overheal is converted to Ward
    Frenzy (1-5) 0.5/1.0/1.5/2.0/2.5% increased damage per 1% missing HP
    Leeching (1-5) Heal for 2/4/6/8/10% of base damage dealt
    Thorns (1-5) Reflect 100/200/300/400/500% of blocked damage
    Ghosted (1-5) Gain 10/20/30/40/50 Ward on Dodge
- Aphrodite now only drops 1 curio instead of  1-5
- Ascent monsters now scale faster and drop fewer curios
- Loot drops have been slightly decreased, player rarity now has decreased efficiency at high amounts for equipment drops, however special drops (keys, curios, gold are unaffected)
- Loot table for equipment now have the following odds:
    # Weapon: (35%)
    # Accessory: (25%)
    # Armor: (10%)
    # Gloves: (10%)
    # Boots: (10%)
    # Helmets: (10%)
- Rewrote all games of chance to be way more interactive.
- Removed overwhelm (no ward/evade/block) mod from boss monsters and ascent monsters

### Version 0.4
Added gloves and boots
Similar upgrade system to accessories
Gloves can roll 1 of atk/def and 1 of PDR/FDR
Boots are the same


Gloves have 5 potential levels, passive list:
ward-touched - 1/2/3/4/5% ward generated based on dmg of your hits - this is added to player ward each time during the player turn
ward-fused - 2/4/6/8/10% ward generated based on dmg of your crit - this is added to player ward each time during the player turn
instability - all hits are either 50% or 160/170/180/190/200% of your hit damage - this affects the player's hit multiplier, BEFORE any other changes occur
deftness - raises floor of crits by 5/10/15/20/25%, so 75% at max rank - this adds the value to the current crit value, which should be at 0.5, for a maximum of 0.75 at max rank
adroit - raises floor of hits by 2/4/6/8/10% of maximum hit - this is similar to the sparking passive, where the floor of the hit is increased
equilibrium - grants 5/10/15/20/25% of hit damage as exp - infinite wisdom does not affect this value
plundering - grants 10/20/30/40/50% of hit damage as gold - prosper does not affect this value

Boots have 6 potential levels, passive list:
speedster - combat cooldown reduced by 20/40/60/80/100/120s
skiller - grants 5/10/15/20/25/30% to proc a skill material award (granted based on tool) on victory
treasure tracker - treasure mob chance increased by 0.5/1/1.5/2/2.5/3% - this is handled similar to the treasure hunter armor passive
hearty - 5/10/15/20/25/30% bonus hp
cleric - potions heal 10/20/30/40/50/60% increased hp, so right now its 30% at max rank it'll be 90%
thrill seeker - special drops (boss keys, shatter runes) chance increased by 1/2/3/4/5/6%
Other changes
Curios no longer drop ilvl equipment, can now drop lv100 gloves, boots as well
Added runes of shattering
Added 1k drop

Added a few more monster modifiers
        "Penetrator": "Ignores 20% of Percentage Damage Reduction"
        "Clobberer": "Ignores 5 Flat Damage Reduction"
        "Smothering": "Critical hit damage is reduced by 20%"
        "Dodgy": "Evasion increased by 10%"
        "Prescient": "10% more likely to hit"
        "Vampiric": "Heals for 10 times damage dealt"

shieldbreaker/overwhelm now changed to ward is disabled only on start of combat
Ascent now starts 3 levels above current player level + ascension

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