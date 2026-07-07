"""
core/nether_market/mechanics.py — Pure business logic for the Nether Market.

No I/O, no Discord, no DB — everything here is deterministic given inputs.
See docs/design/nether_market.md for the full design rationale.
"""

from __future__ import annotations

import random
import time

from core.nether_market.data import ITEM_POOL, NETHER_MARKET_NODES, WEALTH_TIERS

MAX_CHARGES: int = 3
CHARGE_REGEN_SECONDS: float = 8 * 3600  # 8 hours per charge (matches Apex's cadence)

MIN_PLUNDER_PCT = 0.10
MAX_PLUNDER_PCT = 0.30
TIGHT_GRIP_MAX_PCT = 0.20
PLUNDER_PCT_FLOOR = 0.05
AVERAGE_PLUNDER_PCT = (MIN_PLUNDER_PCT + MAX_PLUNDER_PCT) / 2

NPC_HOLDINGS_TIER_WEIGHTS = (("cheap", 0.5), ("med", 0.3), ("expensive", 0.2))

# Below-value ("lo") and above-value ("hi") multiplier bands — split around 1.0
# so every tier always has one guaranteed bargain and one guaranteed markup.
ROTATION_LOW_MIN = 0.10
ROTATION_LOW_MAX = 0.95
ROTATION_HIGH_MIN = 1.05
ROTATION_HIGH_MAX = 3.00

BASE_HOLDINGS_CAP = 200


class NetherMarketMechanics:
    # ------------------------------------------------------------------
    # Rotation / pricing
    # ------------------------------------------------------------------

    @staticmethod
    def _roll_price(true_value: int, mult_min: float, mult_max: float) -> int:
        multiplier = random.uniform(mult_min, mult_max)
        step = round(multiplier / 0.05) * 0.05
        return max(1, round(true_value * step))

    @staticmethod
    def roll_price_below(true_value: int) -> int:
        """Listed price = true_value * a multiplier in [0.10, 0.95], rounded to
        the nearest 5% step so the displayed deviation is always a clean number."""
        return NetherMarketMechanics._roll_price(
            true_value, ROTATION_LOW_MIN, ROTATION_LOW_MAX
        )

    @staticmethod
    def roll_price_above(true_value: int) -> int:
        """Listed price = true_value * a multiplier in [1.05, 3.00], rounded to
        the nearest 5% step so the displayed deviation is always a clean number."""
        return NetherMarketMechanics._roll_price(
            true_value, ROTATION_HIGH_MIN, ROTATION_HIGH_MAX
        )

    @staticmethod
    def roll_rotation() -> dict:
        """Picks 2 distinct items per offer tier: one ("lo") listed below true
        value, one ("hi") listed above."""
        result = {}
        for tier in ("cheap", "med", "expensive"):
            item_lo, item_hi = random.sample(ITEM_POOL[tier], 2)
            result[f"{tier}_lo_item"] = item_lo["key"]
            result[f"{tier}_lo_price"] = NetherMarketMechanics.roll_price_below(
                item_lo["true_value"]
            )
            result[f"{tier}_hi_item"] = item_hi["key"]
            result[f"{tier}_hi_price"] = NetherMarketMechanics.roll_price_above(
                item_hi["true_value"]
            )
        return result

    @staticmethod
    def deviation_pct(listed_price: int, true_value: int) -> float:
        if true_value <= 0:
            return 0.0
        return ((listed_price - true_value) / true_value) * 100

    @staticmethod
    def get_item(item_key: str) -> dict | None:
        for tier_items in ITEM_POOL.values():
            for item in tier_items:
                if item["key"] == item_key:
                    return item
        return None

    @staticmethod
    def active_offers(rotation: dict) -> dict[str, int]:
        """Returns {item_key: listed_price} for the 6 currently active offers
        (one "lo" bargain + one "hi" markup per tier)."""
        offers: dict[str, int] = {}
        for tier in ("cheap", "med", "expensive"):
            offers[rotation[f"{tier}_lo_item"]] = rotation[f"{tier}_lo_price"]
            offers[rotation[f"{tier}_hi_item"]] = rotation[f"{tier}_hi_price"]
        return offers

    # ------------------------------------------------------------------
    # Wealth tiers
    # ------------------------------------------------------------------

    @staticmethod
    def compute_holdings_value(holdings: dict, rotation: dict | None) -> int:
        """holdings: {item_key: qty}. Uses the rotation's listed price when the
        item is currently offered, otherwise falls back to true value."""
        listed_lookup = (
            NetherMarketMechanics.active_offers(rotation) if rotation else {}
        )
        total = 0
        for item_key, qty in holdings.items():
            item = NetherMarketMechanics.get_item(item_key)
            if not item:
                continue
            price = listed_lookup.get(item_key, item["true_value"])
            total += price * qty
        return total

    @staticmethod
    def get_wealth_tier(holdings_value: int) -> int:
        """Returns the tier index (0-6) for a given holdings value."""
        tier_index = 0
        for i, tier in enumerate(WEALTH_TIERS):
            if holdings_value >= tier["min"]:
                tier_index = i
        return tier_index

    # ------------------------------------------------------------------
    # Mastery tree
    # ------------------------------------------------------------------

    @staticmethod
    def can_purchase(node_id: str, nodes_owned: dict, marks: int) -> tuple[bool, str]:
        node = NETHER_MARKET_NODES.get(node_id)
        if not node:
            return False, "Unknown node."
        if node_id in nodes_owned:
            return False, "Already unlocked."
        prereq = node.get("prereq")
        if prereq and prereq not in nodes_owned:
            return False, f"Requires **{NETHER_MARKET_NODES[prereq]['name']}** first."
        if marks < node["cost"]:
            return False, f"Need **{node['cost']} Nether Marks** (you have {marks})."
        return True, ""

    @staticmethod
    def get_holdings_cap(nodes_owned: dict) -> int:
        cap = BASE_HOLDINGS_CAP
        for node_id in ("trunk_cap_1", "trunk_cap_2", "trunk_cap_3", "trunk_cap_4"):
            if node_id in nodes_owned:
                cap += 25
        return cap

    # ------------------------------------------------------------------
    # Plunder charges — direct port of ApexMechanics.calculate_charges
    # (core/apex/mechanics.py), parameterized so Cutpurse's Quick Fingers
    # nodes can shrink the regen window.
    # ------------------------------------------------------------------

    @staticmethod
    def get_charge_regen_seconds(attacker_nodes: dict) -> float:
        seconds = CHARGE_REGEN_SECONDS
        if attacker_nodes.get("cp_regen_1"):
            seconds = 6 * 3600
        if attacker_nodes.get("cp_regen_2"):
            seconds = 4 * 3600
        return seconds

    @staticmethod
    def calculate_charges(
        charges: int,
        last_charge_time: float | None,
        regen_seconds: float = CHARGE_REGEN_SECONDS,
    ) -> tuple[int, float | None]:
        """Applies elapsed-time charge regeneration and returns
        (new_charge_count, new_last_charge_time). Persist the returned values
        if changed (see NetherMarketRepository.restore_charges)."""
        if charges >= MAX_CHARGES:
            return MAX_CHARGES, None
        if last_charge_time is None:
            return charges, None

        now = time.time()
        elapsed = now - last_charge_time
        regen_count = int(elapsed // regen_seconds)
        if regen_count <= 0:
            return charges, last_charge_time

        new_charges = min(MAX_CHARGES, charges + regen_count)
        if new_charges >= MAX_CHARGES:
            return MAX_CHARGES, None
        new_ts = last_charge_time + regen_count * regen_seconds
        return new_charges, new_ts

    @staticmethod
    def seconds_until_next_charge(
        charges: int,
        last_charge_time: float | None,
        regen_seconds: float = CHARGE_REGEN_SECONDS,
    ) -> int:
        charges, _ = NetherMarketMechanics.calculate_charges(
            charges, last_charge_time, regen_seconds
        )
        if charges >= MAX_CHARGES or last_charge_time is None:
            return 0
        elapsed = time.time() - last_charge_time
        remaining = regen_seconds - (elapsed % regen_seconds)
        return max(0, int(remaining))

    # ------------------------------------------------------------------
    # Plunder session setup
    # ------------------------------------------------------------------

    @staticmethod
    def get_session_params(
        tier_index: int, defender_nodes: dict, attacker_nodes: dict
    ) -> tuple[int, float]:
        """Returns (attempts, shield_seconds) for a plunder session against a
        target at the given wealth tier index, after Cutpurse/Strongbox modifiers."""
        tier = WEALTH_TIERS[tier_index]
        attempts = tier["attempts"]
        shield_seconds = tier["shield_hours"] * 3600

        if attacker_nodes.get("cp_attempts_1"):
            attempts += 2
        if attacker_nodes.get("cp_attempts_2"):
            attempts += 3

        if defender_nodes.get("sb_defense_1"):
            attempts -= 1
        if defender_nodes.get("sb_defense_2"):
            attempts -= 2
        attempts = max(1, attempts)

        if defender_nodes.get("sb_shield_1"):
            shield_seconds += 2 * 3600
        if defender_nodes.get("sb_shield_2"):
            shield_seconds += 4 * 3600

        return attempts, shield_seconds

    @staticmethod
    def get_npc_session_params(npc: dict, attacker_nodes: dict) -> tuple[int, float]:
        """NPCs bake their Strongbox-equivalent defense directly into `attempt_reduction`
        rather than reading it from a nodes_owned dict — they don't have a profile row."""
        tier = WEALTH_TIERS[npc["tier_index"]]
        attempts = max(1, tier["attempts"] - npc["attempt_reduction"])
        if attacker_nodes.get("cp_attempts_1"):
            attempts += 2
        if attacker_nodes.get("cp_attempts_2"):
            attempts += 3
        return attempts, tier["shield_hours"] * 3600

    # ------------------------------------------------------------------
    # Mastermind
    # ------------------------------------------------------------------

    @staticmethod
    def generate_code() -> str:
        return "".join(str(random.randint(0, 9)) for _ in range(4))

    @staticmethod
    def score_guess(code: str, guess: str) -> tuple[int, int]:
        """Classic Mastermind scoring: (black pegs, white pegs).
        Black = correct digit + correct position. White = correct digit, wrong position.
        Digits 0-9, repeats allowed."""
        black = sum(1 for c, g in zip(code, guess) if c == g)
        code_counts: dict[str, int] = {}
        guess_counts: dict[str, int] = {}
        for c, g in zip(code, guess):
            if c != g:
                code_counts[c] = code_counts.get(c, 0) + 1
                guess_counts[g] = guess_counts.get(g, 0) + 1
        white = sum(min(code_counts.get(d, 0), n) for d, n in guess_counts.items())
        return black, white

    # ------------------------------------------------------------------
    # NPC simulated inventory
    # ------------------------------------------------------------------

    @staticmethod
    def build_npc_holdings(npc: dict, rotation: dict) -> dict[str, int]:
        """Builds a simulated holdings dict for an NPC vendor from the server's
        currently active rotation offers (cheap/med/expensive), weighted 50/30/20
        and split evenly between each tier's "lo" and "hi" item. Sized so that an
        average plunder roll (~20%, the midpoint of the player pct range) nets
        roughly the NPC's old flat `reward_gold` in total item value — this is
        what actually gets plundered now instead of raw gold."""
        total_value = npc["reward_gold"] / AVERAGE_PLUNDER_PCT
        holdings: dict[str, int] = {}
        for tier, weight in NPC_HOLDINGS_TIER_WEIGHTS:
            for variant in ("lo", "hi"):
                item_key = rotation[f"{tier}_{variant}_item"]
                price = rotation[f"{tier}_{variant}_price"]
                qty = round((total_value * weight / 2) / price)
                if qty > 0:
                    holdings[item_key] = holdings.get(item_key, 0) + qty
        if not holdings:
            holdings[rotation["cheap_lo_item"]] = 1
        return holdings

    # ------------------------------------------------------------------
    # Plunder resolution
    # ------------------------------------------------------------------

    @staticmethod
    def roll_plunder_pct(defender_nodes: dict) -> float:
        ceiling = (
            TIGHT_GRIP_MAX_PCT if defender_nodes.get("sb_grip") else MAX_PLUNDER_PCT
        )
        pct = random.uniform(MIN_PLUNDER_PCT, max(MIN_PLUNDER_PCT, ceiling))
        return max(PLUNDER_PCT_FLOOR, pct)

    @staticmethod
    def apply_plunder(
        holdings: dict, pct: float, attacker_free_slots: int
    ) -> tuple[dict, int, dict]:
        """Splits `pct` of each stack in `holdings` off the victim's holdings.
        `attacker_free_slots` caps how much of that actually lands in the
        attacker's inventory — the rest is converted to gold at true value, but
        is still removed from the victim (it doesn't just vanish for free).
        Returns (moved: {item_key: qty} the attacker receives as items,
        overflow_gold, total_taken: {item_key: qty} the full amount to deduct
        from the victim — always >= moved per item). If holdings exist but
        rounding would move nothing, forces 1 unit from the largest stack."""
        total_taken: dict[str, int] = {}
        for item_key, qty in holdings.items():
            take = round(qty * pct)
            if take > 0:
                total_taken[item_key] = take

        if not total_taken and holdings:
            largest_key = max(holdings, key=holdings.get)
            if holdings[largest_key] > 0:
                total_taken[largest_key] = 1

        moved = dict(total_taken)
        total_units = sum(moved.values())
        overflow_gold = 0
        if attacker_free_slots >= 0 and total_units > attacker_free_slots:
            excess = total_units - attacker_free_slots
            for item_key in sorted(moved, key=lambda k: moved[k], reverse=True):
                if excess <= 0:
                    break
                trim = min(moved[item_key], excess)
                moved[item_key] -= trim
                excess -= trim
                item = NetherMarketMechanics.get_item(item_key)
                if item:
                    overflow_gold += trim * item["true_value"]
            moved = {k: v for k, v in moved.items() if v > 0}

        return moved, overflow_gold, total_taken
