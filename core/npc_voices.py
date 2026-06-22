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

    "slayer": [
        "Another hunter walks in. Let's see how much blood you've spilled since last time. Don't disappoint me.",
        "I don't hand out easy tasks. If you want a challenge, you came to the right place.",
        "Your record speaks for itself. Whether that's a good or bad thing — that's for you to decide.",
        "The monsters aren't going to slay themselves. Get moving.",
        "I've seen veterans crumble on these tasks. I don't think you will. Prove me right.",
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

    "paradise": [
        "The Jewel responds to those who have mastered themselves. Tell me — what power will you seek?",
        "Each cut reveals something inside the stone. Each skill reveals something inside you.",
        "Cosmic Dust doesn't accumulate on its own. It's the residue of effort. Spend it well.",
        "I've watched warriors unlock their first skill and never look back. You'll understand soon.",
        "The Jewel of Paradise is not a reward. It is a beginning.",
    ],

    "uber": [
        "These are the pinnacle of all you will face. Only those who have proven themselves may challenge them.",
        "Step carefully. These beings did not become what they are by accident.",
        "I do not grant access lightly. I trust you understand what you are walking into.",
        "The Sovereigns are not just powerful. They are patient. Do not let them outlast you.",
        "Every key you spend here is a declaration. Make sure you mean it.",
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
