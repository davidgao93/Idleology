"""
audit_images.py — Verify that every URL in core/images.py has a local copy.

Usage:
    python scripts/audit_images.py

For each URL entry in images.py the script extracts the original filename,
searches all of assets/images/ for it, and prints a status line:

  OK       <var>  ->  assets/images/ui/combat/combat_victory.png
  MISSING  <var>  ->  combat_victory.png  (not found anywhere locally)

A summary is printed at the end.
"""

import importlib.util
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
IMAGES_PY = ROOT / "core" / "images.py"
IMAGES_DIR = ROOT / "assets" / "images"


# ── helpers ───────────────────────────────────────────────────────────────────

def load_images_module():
    spec = importlib.util.spec_from_file_location("images", IMAGES_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def filename_from_url(url: str) -> str:
    """Extract the bare filename from a Discord CDN URL."""
    return Path(urlparse(url).path).name


def build_local_index(images_dir: Path) -> dict[str, list[Path]]:
    """Build {filename: [matching paths]} index from assets/images/."""
    index: dict[str, list[Path]] = {}
    for path in images_dir.rglob("*"):
        if path.is_file():
            name = path.name
            index.setdefault(name, []).append(path)
    return index


def iter_image_entries(mod) -> list[tuple[str, str]]:
    """
    Yield (label, url) pairs from the images module.
    Handles both top-level string assignments and dict-valued assignments
    (e.g. SETTLEMENT_BUILDINGS, CORRUPTED_MONSTERS).
    """
    entries = []
    for attr, value in vars(mod).items():
        if attr.startswith("_"):
            continue
        if isinstance(value, str) and value.startswith("https://"):
            entries.append((attr, value))
        elif isinstance(value, dict):
            for key, v in value.items():
                if isinstance(v, str) and v.startswith("https://"):
                    entries.append((f"{attr}[{key!r}]", v))
    return entries


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    if not IMAGES_PY.exists():
        sys.exit(f"ERROR: {IMAGES_PY} not found.")

    mod = load_images_module()
    entries = iter_image_entries(mod)
    local_index = build_local_index(IMAGES_DIR)

    ok = 0
    missing = []
    duplicate_warning = []

    print(f"\nAuditing {len(entries)} URL entries in images.py ...\n")

    for label, url in entries:
        fname = filename_from_url(url)
        matches = local_index.get(fname, [])

        if not matches:
            status = "MISSING"
            missing.append((label, fname))
            rel = fname
        else:
            status = "OK"
            ok += 1
            rel = str(matches[0].relative_to(ROOT))
            if len(matches) > 1:
                duplicate_warning.append((fname, matches))

        color = "" if status == "OK" else "  <-- NOT FOUND LOCALLY"
        print(f"  {status:<8} {label:<45}  {rel}{color}")

    print(f"\n{'-'*70}")
    print(f"  OK:      {ok}")
    print(f"  MISSING: {len(missing)}")

    if missing:
        print("\nMissing files (need to be added to assets/images/):")
        for label, fname in missing:
            print(f"    {label}: {fname}")

    if duplicate_warning:
        print("\nDuplicate filenames across subfolders (may need review):")
        for fname, paths in duplicate_warning:
            print(f"  {fname}")
            for p in paths:
                print(f"    {p.relative_to(ROOT)}")

    print()


if __name__ == "__main__":
    main()
