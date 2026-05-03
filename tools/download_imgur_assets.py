"""
Phase 2 — Download all imgur assets to local disk.

Run from the project root:
    python tools/download_imgur_assets.py

Outputs:
    assets/images/ui/<category>/<name>.<ext>   — UI constants from core/images.py
    assets/images/monsters/<name>.<ext>         — Monster images from monsters.csv
    assets/images/partners/<name>.<ext>         — Partner portraits from partners.csv
    assets/images/curios/<item>.<ext>           — Curio reward images from curios.csv
    assets/images/url_map.json                  — { imgur_url: relative_asset_path }
"""

import csv
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
IMAGES_PY = ROOT / "core" / "images.py"
MONSTERS_CSV = ROOT / "assets" / "monsters.csv"
PARTNERS_CSV = ROOT / "assets" / "partners.csv"
CURIOS_CSV = ROOT / "assets" / "curios.csv"
OUT_ROOT = ROOT / "assets" / "images"
URL_MAP_OUT = OUT_ROOT / "url_map.json"

REQUEST_DELAY = 0.4  # seconds between downloads — be polite to imgur

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Maps constant name prefix → subfolder under assets/images/ui/
_PREFIX_TO_FOLDER = {
    "COMBAT_":     "ui/combat",
    "BOSS_":       "ui/bosses",
    "MONSTER_":    "ui/bosses",
    "VICTORY_":    "ui/bosses",
    "INVENTORY_":  "ui/inventory",
    "SLOT_":       "ui/inventory",
    "UPGRADE_":    "ui/inventory",
    "CURIO_":      "ui/curios",
    "ALCHEMY_":    "ui/alchemy",
    "ASCENT_":     "ui/ascent",
    "CODEX_":      "ui/codex",
    "CONSUME_":    "ui/consume",
    "COMPANIONS_": "ui/companions",
    "DELVE_":      "ui/delve",
    "DUELS_":      "ui/duels",
    "EVENT_":      "ui/events",
    "ENCOUNTER_":  "ui/encounters",
    "MAW_":        "ui/maw",
    "PARTNERS_":   "ui/partners",
    "GACHA_":      "ui/partners",
    "SETTLEMENT_": "ui/settlement",
    "SLAYER_":     "ui/slayer",
    "TAVERN_":     "ui/general",
    "DEFAULT_":    "ui/general",
    "TOOL_":       "ui/skills",
}


def _folder_for_const(name: str) -> str:
    for prefix, folder in _PREFIX_TO_FOLDER.items():
        if name.startswith(prefix):
            return folder
    return "ui/misc"


def _ext(url: str) -> str:
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    return suffix if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"} else ".jpg"


def _slug(text: str) -> str:
    """Make a filesystem-safe slug from arbitrary text."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


# ---------------------------------------------------------------------------
# Source 1: core/images.py  (scalar constants + SETTLEMENT_BUILDINGS dict)
# ---------------------------------------------------------------------------

def collect_images_py() -> dict[str, Path]:
    """Returns {url: dest_path} for everything declared in core/images.py."""
    source = IMAGES_PY.read_text(encoding="utf-8")
    entries: dict[str, Path] = {}

    # Scalar constants: NAME = "https://..."
    for m in re.finditer(r'^([A-Z_0-9]+)\s*=\s*"(https://i\.imgur\.com/[^"]+)"', source, re.MULTILINE):
        name, url = m.group(1), m.group(2)
        folder = _folder_for_const(name)
        filename = name.lower() + _ext(url)
        entries[url] = OUT_ROOT / folder / filename

    # SETTLEMENT_BUILDINGS dict values: "key": "https://..."
    dict_block_m = re.search(r"SETTLEMENT_BUILDINGS\s*=\s*\{(.+?)\}", source, re.DOTALL)
    if dict_block_m:
        for m in re.finditer(r'"([^"]+)"\s*:\s*"(https://i\.imgur\.com/[^"]+)"', dict_block_m.group(1)):
            key, url = m.group(1), m.group(2)
            filename = key + _ext(url)
            dest = OUT_ROOT / "ui/settlement" / filename
            # Don't overwrite if a scalar constant already claimed this URL
            if url not in entries:
                entries[url] = dest

    return entries


# ---------------------------------------------------------------------------
# Source 2: monsters.csv
# ---------------------------------------------------------------------------

def collect_monsters() -> dict[str, Path]:
    entries: dict[str, Path] = {}
    with open(MONSTERS_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            url = row.get("url", "").strip()
            name = row.get("name", "unknown").strip()
            if not url.startswith("http"):
                continue
            filename = _slug(name) + _ext(url)
            entries[url] = OUT_ROOT / "monsters" / filename
    return entries


# ---------------------------------------------------------------------------
# Source 3: partners.csv  (image_url + affinity_image_url)
# ---------------------------------------------------------------------------

def collect_partners() -> dict[str, Path]:
    entries: dict[str, Path] = {}
    with open(PARTNERS_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = _slug(row.get("name", "unknown").strip())
            for col, suffix in [("image_url", ""), ("affinity_image_url", "_affinity")]:
                url = row.get(col, "").strip()
                if not url.startswith("http"):
                    continue
                filename = name + suffix + _ext(url)
                entries[url] = OUT_ROOT / "partners" / filename
    return entries


# ---------------------------------------------------------------------------
# Source 4: curios.csv
# ---------------------------------------------------------------------------

def collect_curios() -> dict[str, Path]:
    entries: dict[str, Path] = {}
    with open(CURIOS_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            url = row.get("URL", "").strip()
            item = row.get("Item", "unknown").strip()
            if not url.startswith("http"):
                continue
            filename = _slug(item) + _ext(url)
            entries[url] = OUT_ROOT / "curios" / filename
    return entries


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        dest.write_bytes(data)
        return True
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}  {url}")
        return False
    except Exception as e:
        print(f"  ERROR {e}  {url}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Collect all sources
    all_entries: dict[str, Path] = {}

    print("Collecting URLs from core/images.py …")
    all_entries.update(collect_images_py())

    print("Collecting URLs from monsters.csv …")
    all_entries.update(collect_monsters())

    print("Collecting URLs from partners.csv …")
    all_entries.update(collect_partners())

    print("Collecting URLs from curios.csv …")
    all_entries.update(collect_curios())

    total = len(all_entries)
    print(f"\nUnique URLs to download: {total}\n")

    url_map: dict[str, str] = {}
    success = 0
    skipped = 0
    failed = 0

    for i, (url, dest) in enumerate(all_entries.items(), 1):
        rel = dest.relative_to(ROOT).as_posix()

        if dest.exists():
            print(f"[{i:>4}/{total}] skip  {rel}")
            url_map[url] = rel
            skipped += 1
            continue

        print(f"[{i:>4}/{total}] dl    {rel}")
        ok = download(url, dest)
        if ok:
            url_map[url] = rel
            success += 1
        else:
            failed += 1

        time.sleep(REQUEST_DELAY)

    # Write url_map.json
    URL_MAP_OUT.parent.mkdir(parents=True, exist_ok=True)
    URL_MAP_OUT.write_text(json.dumps(url_map, indent=2), encoding="utf-8")

    print(f"\nDone.  downloaded={success}  skipped={skipped}  failed={failed}")
    print(f"URL map written to {URL_MAP_OUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
