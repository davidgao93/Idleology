from core.emojis import (
    ACCESSORY_SLOT,
    ARMOR_SLOT,
    ARTEFACT_SLOT,
    BOOT_SLOT,
    GLOVE_SLOT,
    HELMET_SLOT,
    WEAPON_SLOT,
)

# The 6 normal equipment-repo-backed slots. Loadouts and the bulk
# _fetch_all_slots() equipment fetch iterate this — do NOT add "artefact"
# here, it lives in a separate repo (bot.database.rite) with different
# server-scoping and no loadout support. GearView's tabs use
# GEAR_SLOT_ORDER below instead.
SLOT_ORDER = ["weapon", "armor", "helmet", "glove", "boot", "accessory"]

# Display order for the unified Gear view's tabs — the 6 normal slots plus
# the Rite of Convergence Artefact slot, positioned last.
GEAR_SLOT_ORDER = SLOT_ORDER + ["artefact"]

SLOT_EMOJIS = {
    "weapon": WEAPON_SLOT,
    "armor": ARMOR_SLOT,
    "helmet": HELMET_SLOT,
    "glove": GLOVE_SLOT,
    "boot": BOOT_SLOT,
    "accessory": ACCESSORY_SLOT,
    "artefact": ARTEFACT_SLOT,
}

SLOT_LABELS = {
    "weapon": "Weapon",
    "armor": "Armor",
    "helmet": "Helmet",
    "glove": "Glove",
    "boot": "Boot",
    "accessory": "Accessory",
    "artefact": "Artefact",
}
