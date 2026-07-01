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

ROTATION_MULTIPLIER_MIN = 0.55
ROTATION_MULTIPLIER_MAX = 1.55

BASE_HOLDINGS_CAP = 200


class NetherMarketMechanics:
    # ------------------------------------------------------------------
    # Rotation / pricing
    # ------------------------------------------------------------------

    @staticmethod
    def roll_price(true_value: int) -> int:
        """Listed price = true_value * a multiplier in [0.55, 1.55], rounded to
        the nearest 5% step so the displayed deviation is always a clean number."""
        multiplier = random.uniform(ROTATION_MULTIPLIER_MIN, ROTATION_MULTIPLIER_MAX)
        step = round(multiplier / 0.05) * 0.05
        return max(1, round(true_value * step))

    @staticmethod
    def roll_rotation() -> dict:
        """Picks 1 item per offer tier and rolls its listed price."""
        result = {}
        for tier in ("cheap", "med", "expensive"):
            item = random.choice(ITEM_POOL[tier])
            result[f"{tier}_item"] = item["key"]
            result[f"{tier}_price"] = NetherMarketMechanics.roll_price(item["true_value"])
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
        """Returns {item_key: listed_price} for the 3 currently active offers."""
        return {
            rotation["cheap_item"]: rotation["cheap_price"],
            rotation["med_item"]: rotation["med_price"],
            rotation["expensive_item"]: rotation["expensive_price"],
        }

    # ------------------------------------------------------------------
    # Wealth tiers
    # ------------------------------------------------------------------

    @staticmethod
    def compute_holdings_value(holdings: dict, rotation: dict | None) -> int:
        """holdings: {item_key: qty}. Uses the rotation's listed price when the
        item is currently offered, otherwise falls back to true value."""
        listed_lookup = NetherMarketMechanics.active_offers(rotation) if rotation else {}
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
    def get_tree_bonuses(nodes_owned: dict) -> dict:
        """Converts raw nodes_owned dict into a structured bool map for UI use."""
        return {node_id: bool(nodes_owned.get(node_id)) for node_id in NETHER_MARKET_NODES}

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
        charges: int, last_charge_time: float | None, regen_seconds: float = CHARGE_REGEN_SECONDS
    ) -> int:
        charges, _ = NetherMarketMechanics.calculate_charges(charges, last_charge_time, regen_seconds)
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
    # Plunder resolution
    # ------------------------------------------------------------------

    @staticmethod
    def roll_plunder_pct(defender_nodes: dict) -> float:
        ceiling = TIGHT_GRIP_MAX_PCT if defender_nodes.get("sb_grip") else MAX_PLUNDER_PCT
        pct = random.uniform(MIN_PLUNDER_PCT, max(MIN_PLUNDER_PCT, ceiling))
        return max(PLUNDER_PCT_FLOOR, pct)

    @staticmethod
    def apply_plunder(
        holdings: dict, pct: float, attacker_free_slots: int
    ) -> tuple[dict, int]:
        """Splits `pct` of each stack in `holdings` off to the attacker, capped by
        `attacker_free_slots` (overflow converts to gold at true value). Returns
        (moved: {item_key: qty}, overflow_gold). If holdings exist but rounding
        would move nothing, forces 1 unit from the largest stack."""
        moved: dict[str, int] = {}
        for item_key, qty in holdings.items():
            take = round(qty * pct)
            if take > 0:
                moved[item_key] = take

        if not moved and holdings:
            largest_key = max(holdings, key=holdings.get)
            if holdings[largest_key] > 0:
                moved[largest_key] = 1

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

        return moved, overflow_gold
