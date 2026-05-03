"""
Phase 4 — Swap all imgur URLs for Discord CDN URLs.

Run from the project root:
    python tools/apply_discord_urls.py

Rewrites:
    core/images.py          — all string constants
    assets/monsters.csv     — url column
    assets/partners.csv     — image_url and affinity_image_url columns
    assets/curios.csv       — URL column
"""

import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CDN_MAP_PATH = ROOT / "assets" / "images" / "discord_url_map.json"

# ---------------------------------------------------------------------------
# Load map
# ---------------------------------------------------------------------------

if not CDN_MAP_PATH.exists():
    sys.exit(f"ERROR: {CDN_MAP_PATH} not found — run seed_discord_images.py first.")

cdn_map: dict[str, str] = json.loads(CDN_MAP_PATH.read_text(encoding="utf-8"))
print(f"Loaded {len(cdn_map)} URL mappings.\n")


def swap(text: str) -> tuple[str, int]:
    """Replace every imgur URL in text with its CDN counterpart. Returns (new_text, count)."""
    count = 0
    for imgur_url, cdn_url in cdn_map.items():
        if imgur_url in text:
            text = text.replace(imgur_url, cdn_url)
            count += 1
    return text, count


# ---------------------------------------------------------------------------
# 1. core/images.py
# ---------------------------------------------------------------------------

images_py = ROOT / "core" / "images.py"
original = images_py.read_text(encoding="utf-8")
updated, n = swap(original)
images_py.write_text(updated, encoding="utf-8")
print(f"core/images.py          — {n} URL(s) replaced")


# ---------------------------------------------------------------------------
# 2. assets/monsters.csv  (column: url)
# ---------------------------------------------------------------------------

def rewrite_csv(path: Path, url_columns: list[str]) -> int:
    """Rewrite URL columns in a CSV file in-place. Returns total replacements."""
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    fieldnames = reader.fieldnames or []

    total = 0
    for row in rows:
        for col in url_columns:
            if col in row and row[col]:
                new_val, n = swap(row[col])
                row[col] = new_val
                total += n

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(out.getvalue(), encoding="utf-8")
    return total


n = rewrite_csv(ROOT / "assets" / "monsters.csv", ["url"])
print(f"assets/monsters.csv     — {n} URL(s) replaced")

n = rewrite_csv(ROOT / "assets" / "partners.csv", ["image_url", "affinity_image_url"])
print(f"assets/partners.csv     — {n} URL(s) replaced")

n = rewrite_csv(ROOT / "assets" / "curios.csv", ["URL"])
print(f"assets/curios.csv       — {n} URL(s) replaced")

# ---------------------------------------------------------------------------
# Verify — scan all four files for any remaining imgur URLs
# ---------------------------------------------------------------------------

print("\nVerifying…")
import re

targets = [
    ROOT / "core" / "images.py",
    ROOT / "assets" / "monsters.csv",
    ROOT / "assets" / "partners.csv",
    ROOT / "assets" / "curios.csv",
]

all_clean = True
for path in targets:
    text = path.read_text(encoding="utf-8")
    hits = re.findall(r"https?://i\.imgur\.com/\S+", text)
    if hits:
        print(f"  WARN: {path.relative_to(ROOT)} still contains {len(hits)} imgur URL(s):")
        for h in hits[:5]:
            print(f"    {h}")
        all_clean = False
    else:
        print(f"  OK  {path.relative_to(ROOT)}")

print()
if all_clean:
    print("All files clean. Phase 4 complete.")
else:
    print("Some imgur URLs remain — check the warnings above.")
