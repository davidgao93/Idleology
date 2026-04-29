import csv
import os
from typing import Dict

PARTNER_DATA: Dict[int, dict] = {}


def _load() -> None:
    path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "partners.csv")
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            pid = int(row["partner_id"])
            PARTNER_DATA[pid] = {
                "name": row["name"],
                "title": row["title"],
                "rarity": int(row["rarity"]),
                "pull_message": row["pull_message"],
                "base_attack": int(row["base_attack"]),
                "base_defence": int(row["base_defence"]),
                "base_hp": int(row["base_hp"]),
                "image_url": row["image_url"],
                "affinity_image_url": row["affinity_image_url"],
            }


_load()
