"""Writs of Devotion — RAID-DESIGN.md's optional difficulty-increasing
modifiers, locked until the player's first full clear (rite.has_first_clear).

Speed writs (group="speed") and the attempts writs (group="attempts") are
each a mutually-exclusive radio group — see core/rite/views/writ_select_view.py.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WritDef:
    key: str
    name: str
    effect: str
    dp: int
    group: str | None = None  # "speed" | "attempts" | None (independent toggle)


WRITS: dict[str, WritDef] = {
    "unyielding_guardian": WritDef(
        "unyielding_guardian",
        "Unyielding Guardian",
        "Aphrodite Reborn has 30% Damage Reduction",
        10,
    ),
    "wrathful_reckoner": WritDef(
        "wrathful_reckoner",
        "Wrathful Reckoner",
        "Lucifer Reborn deals 30% increased damage",
        10,
    ),
    "devouts_burden": WritDef(
        "devouts_burden",
        "Devout's Burden",
        "The Arbiter presents 1 fewer respite option",
        20,
    ),
    "fracture_of_balance": WritDef(
        "fracture_of_balance",
        "Fracture of Balance",
        "Gemini Reborn: true damage portion increases from 80% to 90%",
        80,
    ),
    "hungering_void": WritDef(
        "hungering_void",
        "Hungering Void",
        "NEET Reborn: void drain increases from 1.5% to 3.0% per round",
        80,
    ),
    "abyssal_embrace": WritDef(
        "abyssal_embrace",
        "Abyssal Embrace",
        "Evelynn Reborn: Delirious difficulty instead of Nightmarish",
        150,
    ),
    "devotions_walk": WritDef(
        "devotions_walk",
        "Devotion's Walk",
        "Finish the entire run in under 400 total turns",
        50,
        group="speed",
    ),
    "devotions_run": WritDef(
        "devotions_run",
        "Devotion's Run",
        "Finish the entire run in under 300 total turns",
        100,
        group="speed",
    ),
    "devotions_sprint": WritDef(
        "devotions_sprint",
        "Devotion's Sprint",
        "Finish the entire run in under 200 total turns",
        150,
        group="speed",
    ),
    "trials_drought": WritDef(
        "trials_drought",
        "Trial's Drought",
        "Cannot use potions at any point during the run",
        200,
    ),
    "trials_fury": WritDef(
        "trials_fury",
        "Trial's Fury",
        "All boss base damage is doubled",
        200,
    ),
    "one_last_chance": WritDef(
        "one_last_chance",
        "One Last Chance",
        "Run begins with 2 attempts instead of 3",
        100,
        group="attempts",
    ),
    "no_mercy": WritDef(
        "no_mercy",
        "No Mercy",
        "Run begins with 1 attempt",
        250,
        group="attempts",
    ),
}

TOGGLE_WRIT_KEYS = [k for k, w in WRITS.items() if w.group is None]
SPEED_WRIT_KEYS = [k for k, w in WRITS.items() if w.group == "speed"]
ATTEMPTS_WRIT_KEYS = [k for k, w in WRITS.items() if w.group == "attempts"]

SPEED_TURN_THRESHOLDS = {
    "devotions_walk": 400,
    "devotions_run": 300,
    "devotions_sprint": 200,
}

STARTING_ATTEMPTS_BY_WRIT = {
    "one_last_chance": 2,
    "no_mercy": 1,
}


def starting_attempts(writs: list[str]) -> int:
    from core.rite.run_state import DEFAULT_ATTEMPTS

    for key in ATTEMPTS_WRIT_KEYS:
        if key in writs:
            return STARTING_ATTEMPTS_BY_WRIT[key]
    return DEFAULT_ATTEMPTS


def compute_devotion_points(writs: list[str], total_turns: int) -> int:
    """Sums DP for all selected writs. A speed writ only contributes its DP if
    the run's total_turns actually came in under its threshold — selecting one
    and missing the deadline grants no bonus (but costs nothing extra either).
    """
    dp = 0
    for key in writs:
        writ = WRITS.get(key)
        if writ is None:
            continue
        if writ.group == "speed":
            if total_turns < SPEED_TURN_THRESHOLDS[key]:
                dp += writ.dp
            continue
        dp += writ.dp
    return dp


# Flavor text for the 5 entry keys — display name -> (thematic link, blurb).
RITE_KEY_FLAVOR: dict[str, tuple[str, str]] = {
    "Apex of Dreams": (
        "Aphrodite Reborn",
        "A shard of unbroken devotion, still warm from a dream that refused to end.",
    ),
    "Corruption of Memories": (
        "Lucifer Reborn",
        "Every regret you've ever buried, compressed into something you can hold.",
    ),
    "Scales of Judgment": (
        "Gemini Reborn",
        "Perfectly balanced. It has never once tipped in anyone's favor.",
    ),
    "Devoid of Thoughts": (
        "NEET Reborn",
        "Silence given shape. Holding it feels like forgetting something important.",
    ),
    "Zenith of Nightmares": (
        "Evelynn Reborn",
        "The peak of a fear you haven't had yet. It's been waiting for you.",
    ),
}
