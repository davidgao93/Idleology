"""
core/npc_voices.py — Central repository for NPC greeting quips.

Each key maps to a list of lines. `get_quip(key)` returns one at random.
Add new lines here rather than hardcoding text in view or cog files.
"""

from __future__ import annotations

import random

# ---------------------------------------------------------------------------
# Quip tables — one entry per NPC / feature
# ---------------------------------------------------------------------------

_VOICES: dict[str, list[str]] = {
    # ── Tavern ────────────────────────────────────────────────────────────────
    "shop": [
        "Still alive, adventurer? Good. The shelves are a bit bare today, but I still have what you need.",
        "Another face through my door. Let's see if your gold lasts longer than your luck.",
        "I won't ask where you've been. Just tell me how many potions you need.",
        "You look like you could use a patch-up. Lucky for you, I never close.",
        "Stock's fresh. Don't make me wait all day — what'll it be?",
    ],
    "casino": [
        "Table Stake down. Feeling lucky, or just desperate? Either way, I'm here for it.",
        "The house never sleeps. Neither do I. Place your bet.",
        "You came back. Most people don't after the first time. I respect that.",
        "Fortune favours the bold. Or so they keep telling me. Let's find out.",
        "Sit down. The night is young and your gold has places to be.",
    ],
    "casino_1v1": [
        "Vespera's smile sharpens as a knife slides out of her sleeve. \"Tired of cards? Fine. Let's settle this properly.\"",
        'She sets down her deck, draws a wicked little blade, and cracks her knuckles. "Your call, adventurer — hit or eat."',
        '"The house doesn\'t lose," Vespera purrs, flipping her knife between her fingers, "but I\'ll let you try anyway."',
        'Vespera cracks her neck and draws steel. "Hope you brought more than luck this time."',
        '"Ooh, feisty tonight." Vespera grins, knife glinting. "Let\'s see how you bleed for your gold."',
    ],
    "casino_blackjack_win": [
        'Vespera exhales through her teeth. "Beginner\'s luck. It has to be."',
        '"Well played," Vespera admits, sliding your winnings across the felt. "Don\'t get used to it."',
        'She taps the table twice. "Fine. You earned that one. The house remembers, though."',
        "\"Hm.\" Vespera's smile doesn't quite reach her eyes as she counts out your gold.",
        '"Lucky cards," Vespera mutters, already reshuffling. "Let\'s see if it holds."',
    ],
    "casino_blackjack_loss": [
        '"House wins," Vespera says, not even trying to hide her smirk.',
        "She sweeps your gold away without a word. Just a wink.",
        '"Better luck next hand," Vespera says, though she doesn\'t sound sorry at all.',
        '"Twenty-one isn\'t as easy as it looks, is it?" Vespera grins, stacking her chips.',
        '"That\'s the game," Vespera shrugs, already dealing the next hand.',
    ],
    "casino_roulette_win": [
        'Vespera watches the ball settle and clicks her tongue. "The wheel likes you tonight."',
        '"Lucky number," she says, sliding the payout over. "Don\'t push it."',
        'Vespera\'s smile tightens as she counts out your winnings. "Impressive. Truly."',
        '"Well, would you look at that," Vespera murmurs, more curious than annoyed.',
        'She spins the wheel again before you\'ve even collected. "Again? I insist."',
    ],
    "casino_roulette_loss": [
        '"The house always has the edge," Vespera says, sweeping the table clean.',
        'She doesn\'t even look up. "Better luck on the next spin."',
        '"Red, black, doesn\'t matter," Vespera smirks. "The wheel answers to me."',
        '"Ohh, so close," Vespera lies, pocketing your gold.',
        '"Try again?" Vespera asks, already spinning.',
    ],
    "casino_crash_win": [
        '"You actually cashed out in time," Vespera says, almost impressed. "Rare."',
        'She watches the rocket climb and shakes her head. "Nerves of steel. Or dumb luck."',
        '"Fine," Vespera sighs, handing over your winnings. "You timed that one well."',
        '"Most people get greedy," Vespera says. "Glad you\'re not most people. This time."',
        'She raises an eyebrow. "Cashing out early? Smart. Annoyingly smart."',
    ],
    "casino_crash_loss": [
        '"And there it goes," Vespera says with a satisfied grin as the rocket bursts.',
        '"Greed gets everyone eventually," she says, collecting your gold.',
        '"You waited too long," Vespera tsks. "They always do."',
        'She watches the wreckage with open delight. "Beautiful, isn\'t it?"',
        '"Should\'ve cashed out sooner," Vespera shrugs. "Live and learn."',
    ],
    "casino_horse_win": [
        '"Huh. Didn\'t see that coming," Vespera admits, counting out your winnings.',
        '"Good pick," she says, almost sounding sincere. "Almost."',
        'Vespera narrows her eyes at the track. "That horse wasn\'t supposed to win."',
        '"Lucky eye for horseflesh," Vespera mutters, sliding the gold across.',
        '"Fine, fine," she laughs. "You called it. Don\'t let it go to your head."',
    ],
    "casino_horse_loss": [
        '"That\'s racing," Vespera says, sweeping up your bet with a grin.',
        '"Wrong horse," she shrugs. "There\'s always next time."',
        "\"I could've told you that one wasn't winning,\" Vespera smirks.",
        'She pats the track fondly. "The house breeds these horses, you know."',
        '"Better luck picking next time," Vespera says, not even trying to sound sincere.',
    ],
    "casino_1v1_win": [
        'Vespera lowers her knife, breathing hard. "...Fine. You win this round."',
        'She wipes her blade clean and forces a smile. "Don\'t get used to that."',
        '"Tch." Vespera flicks the blood off her knife. "I underestimated you. Won\'t happen twice."',
        '"Impressive," Vespera admits through gritted teeth, tossing your winnings over.',
        'She sheathes her knife slowly. "You\'ll pay for that bruise to my pride, one way or another."',
    ],
    "casino_1v1_loss": [
        'Vespera twirls her knife and smiles. "The house doesn\'t lose. I told you."',
        '"Down you go," she says sweetly, already counting your gold.',
        '"That\'s what I like to see," Vespera grins, sheathing her blade.',
        '"Good effort," she says, not meaning it at all. "Try again sometime."',
        'Vespera steps over you with a satisfied smirk. "Next."',
    ],
    "rest": [
        "Rough out there? I've got a room with your name on it.",
        "You look like you've been through a war. The bed doesn't judge.",
        "Clean sheets. Warm fire. It's all yours — for the right price.",
        "Rest well. You'll need it.",
    ],
    "checkin": [
        "On time again. I was starting to think you'd forgotten about me.",
        "Day's rewards are ready. Don't spend it all in one place.",
        "There you are. I keep a tally, you know. Consistency counts.",
        "A little something for showing up. It adds up, trust me.",
    ],
    # ── Guild & Quests ────────────────────────────────────────────────────────
    "quests": [
        "There you are. The board's fresh — a few contracts worth risking your neck over. Choose wisely.",
        "Back already? Good. New contracts are up. Don't sit on them.",
        "The board doesn't wait. Neither do I. What are you after?",
        "Results first. Questions later. Pick a contract and get moving.",
        "Every contract here is an opportunity. Whether you see it that way is your problem.",
        "I don't post easy work. If it were easy, someone else would've done it already.",
        "Fresh meat at the board. The good kind, I hope. Make your mark.",
    ],
    "slayer": [
        "Another hunter walks in. Let's see how much blood you've spilled since last time. Don't disappoint me.",
        "I don't hand out easy tasks. If you want a challenge, you came to the right place.",
        "Your record speaks for itself. Whether that's a good or bad thing — that's for you to decide.",
        "The monsters aren't going to slay themselves. Get moving.",
        "I've seen veterans crumble on these tasks. I don't think you will. Prove me right.",
    ],
    "slayer_emblem": [
        "Essences and hearts, adventurer. Essences and hearts.",
        "Your next task is - oh, you don't want a task? Just the emblem? Oh okay.",
        "May your upgrades be lucky and your rerolls sound.",
    ],
    "slayer_shop": [
        "Points are worth more spent than admired.",
        "What would you like to unlock next?",
        "Pick wisely, lest you want to give me your essence for free.",
    ],
    "quest_shop": [
        "Oh good, you're here. Those tokens burning a hole in your pocket? I've got just the thing.",
        "Spend wisely. I only restock what's worth stocking.",
        "Tokens talk. The rest is just noise. What do you need?",
        "The best rewards don't come cheap. But you've already done the hard part.",
        "I don't run charity. You earned these tokens — now spend them on something that matters.",
    ],
    # ── Hatchery ──────────────────────────────────────────────────────────────
    "hatchery": [
        "Welcome back, Adventurer! Got any eggs for me to look after? 🥚",
        "You haven't... eaten any of the eggs you received, have you? You monster!",
        "I can feel great potential in this one, Adventurer — I can't wait to see them all grown up! 🌸",
        "Oh, you're here! I've been singing to the eggs. Don't ask. It works.",
        "Every egg that comes through here gets my full love and attention. Even the grumpy ones.",
        "A fresh delivery? Wonderful! I'll have them cosy in no time. Leave it to me~",
        "These little ones are counting on us, Adventurer. Let's not let them down!",
    ],
    "hatchery_release": [
        "This one has some fight in them! Better not lose your head, Adventurer — literally. 😅",
        "This one's a proper feisty fella! They almost bit my arm off the other day — I'd watch out if I were you!",
        "They've matured beautifully! ...And by that I mean terrifyingly. Please be careful out there.",
        "I'm so proud of them! They've grown into a magnificent killing machine. Come back in one piece, okay?",
        "Hehe, they're ready! Just... maybe stretch first? And bring lots of potions. Lots and lots of potions.",
        "Don't let the cute memories fool you — whatever this thing is now, it is NOT the egg you brought in. Good luck!",
    ],
    # ── Companions & Nursery ──────────────────────────────────────────────────
    "companions": [
        "Back again? Your companions have been restless without you.",
        "Every bond you forge here will carry you further than any weapon.",
        "A tamer is only as strong as the trust between them and their companions.",
        "They fight for you. The least you can do is check in on them.",
        "I've seen a lot of tamers pass through. The ones who care about their partners go the furthest.",
    ],
    "nursery": [
        "A well-staffed Nursery is the heartbeat of any thriving settlement.",
        "More workers, more progress. It's not complicated — it just takes patience.",
        "Every follower we raise here is another pair of hands for the settlement.",
        "The Nursery never rests. Neither should you.",
        "Growth takes time. But it also takes someone tending the flame. That's your job.",
    ],
    # ── Endgame Systems ───────────────────────────────────────────────────────
    "ascent": [
        "Each floor you conquer brings you one step closer to your true self. The summit does not wait.",
        "I've guided many climbers. Few reach the top. I believe you will.",
        "The tower doesn't forgive hesitation. Don't look down.",
        "Every pinnacle floor you unlock is a permanent mark on who you are. Climb well.",
        "The Ascent isn't just a tower. It's a mirror. What you find at the top will surprise you.",
    ],
    "codex": [
        "The Codex rewards those who return to it. Every run teaches you something the last one didn't.",
        "Five chapters. Endless variation. The knowledge is here — you just have to survive it.",
        "I've catalogued every run that's passed through this hall. Yours are among the most interesting.",
        "Don't underestimate the tomes. They compound. So does your potential.",
        "A scholar does not fear difficulty. They study it. Welcome back.",
    ],
    "codex_tome_unlock": [
        "Nice work. Another page surrenders its secrets — the Codex has imparted a new skill upon you.",
        "You've earned this page's trust. I can already feel the knowledge settling into your bones.",
        "A new slot opens. The Codex doesn't give lightly — treasure what it's just shown you.",
        "Well done. The page dissolves into insight. Let's see what it's left behind.",
        "Another secret catalogued. This one, it seems, chose you specifically.",
    ],
    "apex": [
        "The Apex zones are no place for the unprepared. Choose your hunt wisely.",
        "Each zone shapes you differently. The shards you carry are proof of that.",
        "I've tracked every apex hunter across every zone. You have a pattern worth watching.",
        "Defeat teaches more than victory ever could. But winning is better. Go win.",
        "The Soul Stone doesn't care how you got the shards. Only that you did.",
    ],
    "maw": [
        "The Maw stirs again. Strike true — every wound you deal is remembered.",
        "It cannot be killed. But it can be hurt. Show it what you're made of.",
        "Warriors come and go. The Maw endures. So must we.",
        "Faith is striking a thing that will not fall and striking it anyway.",
        "Your contribution matters more than you know. The wound you deal is carried by all of us.",
    ],
    "consume": [
        "What you consume, you become. Choose carefully what you take from the fallen.",
        "The parts of your enemies are not trophies — they're resources. Use them.",
        "Every slot you fill brings you closer to something that can't be brought down easily.",
        "Don't waste what the monsters leave behind. That's just leaving power on the floor.",
        "The body is a vessel. Fill it with something worth carrying.",
    ],
    "hematurgy": [
        "The blood holds secrets that even death cannot silence. I'll show you how to unlock them.",
        "Every passive you unlock here is woven into your very nature. Permanent. Irreversible. Choose wisely.",
        "Monster blood is not a contaminant. It is an inheritance. Let me help you claim it.",
        "This is not for the faint of heart. Good. You don't look faint of heart.",
        "The body adapts. That's the truth every hematurge builds their craft on. Let's adapt you.",
    ],
    "inner_sanctum": [
        "Three paths wind through this place — Vice, Recovery, Deicide. None of them are free.",
        "Every gift here casts a shadow. Choose which weight you're willing to carry into battle.",
        "You want the world to bend toward you? It will. It'll also push back.",
        "Greed, comfort, or conquest — the Sanctum doesn't judge. It just keeps score.",
        "Spend your points wisely. Reversing a choice costs more than making one.",
    ],
    "paradise": [
        "You're here. Good. The Jewel won't cut itself, and I'm not doing it for you.",
        "Decades of lapidary work, and you're the one who ends up with it. Life has a sense of humour.",
        "Cosmic Dust doesn't accumulate through wishful thinking. It accumulates through fighting. Go do more of that.",
        "Don't mistake the Jewel for a trinket. It has outlasted empires. Show it some respect.",
        "I've seen this stone in the hands of fools before. You don't strike me as one. Prove me right.",
        "You want power? Then be precise. The Jewel punishes impatience far more harshly than I do.",
        "Most people expect miracles on a schedule. The Jewel doesn't care about your schedule.",
        "It's responding to you. That means something. I'm not sure what yet — but something.",
    ],
    "paradise_skills": [
        "Skills don't awaken on their own. Choose which one channels through the Jewel.",
        "Every skill responds differently to the Jewel's pull. Pick the one that suits your hand.",
        "The Jewel can only voice one skill at a time. Choose with intent.",
        "Whichever skill you equip becomes an extension of the stone itself. Choose carefully.",
    ],
    "paradise_passives": [
        "The passive slots are where the Jewel truly comes alive. Spend your jewels well.",
        "Passives shape how the Jewel behaves beneath the surface. Subtle, but never small.",
        "Every slot you fill changes the Jewel's temperament. I'd know — I cut enough of them.",
        "Rerolling isn't cheating. It's refinement. The Jewel doesn't mind either way.",
    ],
    "paradise_engram": [
        "Remarkable. This engram's power is formidable, adventurer... please do be careful.",
        "Evelynn's corruption doesn't ask permission — it simply takes root. I hope you're ready.",
        "I've handled a lot of dangerous stone in my time. This one still makes my hands shake.",
        "The Origin of Corruption left more behind than her shattered form. This is a splinter of her will.",
        "Etch this into the Jewel, and there's no undoing it — only rerolling. Proceed with open eyes.",
        "She was the first thing the void ever dreamed of breaking. Some of that dream is still in here.",
    ],
    "paradise_engram_result": [
        "The corruption takes. The Jewel pulses once, darker than before.",
        "It's done. I felt that from here, adventurer. The stone remembers Evelynn now.",
        "There — etched. Try not to look at it too long. It looks back.",
        "The engram dissolves into the Jewel's core. Something of hers lingers now.",
    ],
    "uber": [
        "These are the pinnacle of all you will face. Only those who have proven themselves may challenge them.",
        "Step carefully. These beings did not become what they are by accident.",
        "I do not grant access lightly. I trust you understand what you are walking into.",
        "The Sovereigns are not just powerful. They are patient. Do not let them outlast you.",
        "Every key you spend here is a declaration. Make sure you mean it.",
    ],
    # ── The Rite of Convergence ───────────────────────────────────────────────
    # Guide-mode: shown at respites between wings, before the mask drops.
    "arbiter": [
        "You've earned a moment's respite, adventurer. Choose your aid wisely.",
        "Rest, if you can call it that. The next wing will not be kinder.",
        "Five gods, reborn and broken by my design. You've handled yourself well so far.",
        "Take what aid you need. I've seen stronger adventurers falter for want of it.",
        "I offer this respite freely. What you do with it is entirely your own affair.",
        "Not far now. Or perhaps very far indeed. Time is strange in here.",
    ],
    # Villain-mode: the fifth respite's reveal, transitioning straight into the finale.
    "arbiter_reveal": [
        "Splendid, adventurer. Five gods, reborn and broken by your hand — and every one of them, my design.",
        "You've been my finest creation. My most entertaining toy. Let's see how far the game goes.",
        "Did you think the guide and the architect were different people? How wonderfully naive.",
        "Every respite, every wing, every choice — all of it, mine to arrange. Now, the true test begins.",
        "I built five gods to break you slowly. I built myself to finish the job.",
    ],
    # Defeat dialogue, shown when a Rite run ends in failure (0 attempts remaining).
    "arbiter_defeat": [
        "Splendid, adventurer. You've been my finest creation. My most entertaining toy. Do come find me again.",
        "A worthy attempt. Not worthy enough — but worthy. I'll be here when you're ready to try again.",
        "The Rite does not forgive weakness, only reward its absence. Come back stronger.",
        "You lasted longer than most. That is either a compliment or a warning. Take your pick.",
    ],
    # Still guide-mode: spoken the moment the 5th wing falls, before anything
    # feels wrong. The mask is still fully on here.
    "arbiter_congratulate": [
        "Congratulations, adventurer. Five gods, broken by your own hand. Few ever see this moment.",
        "Well fought. Truly. I did not expect you to still be standing.",
        "You've done what I built five gods to prevent. That deserves acknowledgment, at least.",
        "Five wings, five falls. I confess — I'm almost impressed.",
    ],
    # Screen 2 of the reveal: the Arbiter has just vanished from the player's
    # side and speaks again from within the converging amalgam.
    "arbiter_amalgam_taunt": [
        "Great... guess I'll have to do this myself.",
        "Subtlety was never going to get me this far anyway.",
        "Fine. If the puppets won't finish you, I will.",
        "No sense delaying the inevitable any further, is there?",
    ],
    # The phase 5 -> phase 6 transition: the amalgam's flesh peels away to
    # reveal the true Arbiter had been standing behind it the whole time.
    "arbiter_toying": [
        "You didn't really think I'd let a puppet of flesh do all the work, did you?",
        "That was merely a costume. Let's see how you fare against the tailor.",
        "Amusing — you actually hurt it. Now let's find out if you can hurt me.",
        "The amalgam was a rehearsal. This is the performance.",
    ],
    # Spoken by the Arbiter upon its own defeat — the true final victory,
    # not to be confused with arbiter_defeat (the player losing).
    "arbiter_true_defeat": [
        "...Huh. Didn't see that coming. This isn't the end, adventurer — only the beginning. See you soon.",
        "Splendid. Truly. I have not lost in longer than you'd believe. Rest — you'll want your strength for what comes next.",
        "So it ends. For tonight. Until we meet again, adventurer.",
        "A fair result, I suppose. Don't get comfortable — I always come back.",
    ],
    # ── Upgrade Smiths ───────────────────────────────────────────────────────
    "forge": [
        "Another blade that needs real work. Hand it over — I'll make it sing.",
        "Good metal. Could be better. That's what I'm here for.",
        "Every weapon that leaves this forge is stronger than the one that came in. Yours won't be the exception.",
        "I don't rush. The forge doesn't rush. You shouldn't either — but the work will be worth it.",
        "Costs are fair. Results are better than fair. Trust the process.",
    ],
    "enchant": [
        "Bring it here. Magic doesn't force itself in — it has to be invited. I know how.",
        "Another piece for enchantment. Set it down carefully. I don't redo sloppy work.",
        "Passive levels don't climb by themselves. That's what I'm here for.",
        "You came to the right place. I don't do ordinary.",
        "This is precision work. Not something you rush. Let's begin.",
    ],
    "temper": [
        "Tempering pushes your armor's resistance to its limit — PDR and FDR are on the table. It's not guaranteed, but nothing worth doing ever is.",
        "Step up. Each temper attempt drives more resistance into the metal itself. Success improves PDR or FDR. Failure costs materials, not your nerve.",
        "This is controlled punishment applied to metal. The goal: improved PDR or FDR. The catch: it can fail. The upside: I'm very good at this.",
    ],
    "imbue": [
        "Imbuing is half craft, half faith. If it holds, your armor gains a passive that nothing else can provide. If it doesn't — the rune shatters. That's the risk.",
        "This isn't tempering. Imbuing writes a permanent passive into the weave of the metal itself. Fifty-fifty odds. One Rune. I don't sugarcoat it.",
        "You only get one shot per piece. A success means a powerful armor passive. A failure means we try again when you have another Rune.",
    ],
    "reinforce": [
        "Reinforce builds up your main stat one slot at a time. Reinforcemaxx runs that automatically until your materials are spent. No slots left? A Shatter Rune adds one back.",
        "One slot at a time, or all at once — your call. Reinforce is careful. Reinforcemaxx is relentless. Shatter Runes keep the machine running when the slots dry up.",
        "What I do here is permanent. The main stat climbs with each reinforcement. Reinforcemaxx handles the grind, Shatter Runes extend it. Simple enough.",
    ],
    "refine": [
        "Raw power, added one roll at a time. Refine does it manually. Refinemaxx runs until materials are gone. Refinemaxx ✨ adds Runes to the loop — won't stop until everything's spent.",
        "A weapon that doesn't get better is already falling behind. Refine handles it one refinement at a time, or all at once with Refinemaxx. The star version burns Runes too, for those who want it all.",
        "Refinement isn't glamorous. It's just better numbers. Refine — one at a time. Refinemaxx — runs dry. Refinemaxx ✨ — adds Runes, runs even drier.",
        "Push a weapon deep enough into refinement and even I can't bear to see it scrapped for nothing — dismantle it later and I'll salvage some of the Runes out of the wreckage. The deeper you've pushed it, the more comes back.",
    ],
    # ── Alchemy ───────────────────────────────────────────────────────────────
    "alchemy": [
        "Welcome back to the lab. The reagents are restless today. Try not to disappoint them.",
        "You again. The cauldron hasn't exploded since your last visit. I'm choosing to see that as progress.",
        "Ah. I was beginning to wonder if you'd dissolved.",
        "The lab is open. Whether you emerge from it intact is, as always, entirely up to you.",
        "Back so soon? Either you've been productive, or something has gone terribly wrong. Either way — welcome.",
        "I've had worse visitors. Most of them left voluntarily.",
        "Your timing is acceptable. The fumes have mostly cleared.",
        "Don't touch the red flask. I know you're looking at it. Don't.",
        "Progress requires boldness. It also requires not drinking unlabeled substances. Keep both in mind.",
        "I see you've survived long enough to return. Encouraging.",
    ],
    # ── Prestige ──────────────────────────────────────────────────────────────
    "prestige": [
        "Hello, Adventurer. All that gold weighing down your pockets — let's find it a better home, shall we?",
        "You've clearly got more gold than sense. Come, let Eliza help you spend some of it in style.",
        "Ah, a wealthy face. The vaults only get heavier if you let them, you know. Let's lighten the load.",
        "Gold sitting idle is just gold wasted, Adventurer. I deal exclusively in the finer things — let's talk business.",
        "You didn't fight your way this far just to look the same as everyone else. Let's fix that.",
        "Excess gold has a funny way of finding my counter eventually. Might as well be today.",
        "Welcome, welcome. I don't do potions or trinkets — I do legacy. And legacy isn't cheap.",
        "Every adventurer of means ends up here sooner or later. Glad you didn't keep me waiting.",
    ],
    # ── Settlement ────────────────────────────────────────────────────────────
    "black_market": [
        "Max tilts his head. 'What have you brought me today?'",
        "'Interesting selection,' he murmurs. 'Let's see what this fetches.'",
        "'Ah, another visitor.' He gestures to the scale. 'Place your offering.'",
        "'I trust you've brought something worth my time?' A thin smile. 'Show me.'",
        "'The market is quiet today,' he says. 'Which means I'm in a generous mood.'",
        "'Business is business. Sentiment is not something I trade in.'",
        "'Every deal is a small wager. I have yet to lose one that mattered.'",
    ],
    "nether_market": [
        "'Ah, a fresh face.' Vex doesn't look up from the ledger. 'Prices turn over every hour. Try to keep up.'",
        "'My cousin Max runs the Black Market.' A crooked grin. 'I run the *interesting* one.'",
        "'Everything here is worthless. That's what makes it valuable.' Vex shrugs. 'Buy low, gloat later.'",
        "'Someone's been asking around about your stash.' Vex doesn't say who. 'Watch yourself.'",
        "'Codes, curiosities, and other people's poor decisions.' Vex spreads their hands. 'Welcome.'",
        "'Max thinks I'm reckless.' Vex counts a stack of coin. 'Max has never cracked a good vault.'",
    ],
    "nether_market_holdings": [
        "'Let's see what you've been hoarding.' Vex flips through the ledger. 'Don't worry, I won't judge. Much.'",
        "'Your stash, in all its glory.' Vex smirks. 'Some of that's worth more than you think. Some of it isn't.'",
        "'Everything you own, cataloged and priced.' Vex taps the ledger. 'Knowledge is leverage, friend.'",
        "'A tidy little collection.' Vex eyes the numbers. 'Tidy enough to be worth stealing, anyway.'",
        "'I keep better records on you than you do.' Vex doesn't apologize for it.",
    ],
    "nether_market_browse": [
        "'Looking for a mark?' Vex leans in. 'I won't tell if you don't.'",
        "'Everyone's holdings are somebody else's opportunity.' Vex shrugs. 'That's just economics.'",
        "'Careful who you cross.' Vex nods at the list. 'Some of them remember.'",
        "'Pick your target wisely.' Vex taps the ledger. 'A cracked vault only pays once.'",
        "'The weak get plundered. The careless get plundered twice.' Vex smiles thinly. 'Which one are you?'",
    ],
    "nether_market_mastery": [
        "'Tricks of the trade.' Vex grins. 'Every one of them paid for in blood, sweat, or Marks. Usually Marks.'",
        "'You want to be better at this?' Vex spreads their hands. 'Then invest. That's the whole game.'",
        "'A sharper eye, a quicker hand, a harder lock.' Vex counts the Marks. 'Pick your poison.'",
        "'Nether Marks don't spend themselves.' Vex raises an eyebrow. 'Well? Go on.'",
        "'Every node here makes you a little more dangerous.' Vex smiles. 'I approve.'",
    ],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_quip(key: str) -> str:
    """Return a random quip for the given NPC / feature key.

    Returns an empty string if the key is not found, so callers are safe to
    embed the result directly into description strings without guarding.
    """
    lines = _VOICES.get(key, [])
    return random.choice(lines) if lines else ""
