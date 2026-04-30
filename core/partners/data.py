import csv
import json
import os
from typing import Any, Dict

PARTNER_DATA: Dict[int, dict] = {}
AFFINITY_STORIES: Dict[tuple[int, int], dict[str, Any]] = {}


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


def _load_affinity_stories() -> None:
    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "assets",
        "partners",
        "affinity_stories.json",
    )
    try:
        with open(path, encoding="utf-8") as f:
            raw_data = json.load(f)

        AFFINITY_STORIES.clear()
        for pid_str, stories in raw_data.items():
            pid = int(pid_str)
            for idx_str, story_data in stories.items():
                idx = int(idx_str)
                AFFINITY_STORIES[(pid, idx)] = {
                    "title": story_data["title"],
                    "text": story_data["text"],
                    "image_url": story_data.get("image_url"),  # can be None
                }
    except Exception as e:
        print(f"Error loading affinity stories: {e}")


_load()
_load_affinity_stories()
