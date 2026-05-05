"""
Upload corrupted monster images to the Discord CDN asset channel.

Run from the project root:
    python tools/upload_corrupted_images.py

Reads:
    assets/images/corrupted_monsters/*.jpg

Outputs:
    - Appends new entries to assets/images/discord_url_map.json
      (keyed as "corrupted:<stem>", e.g. "corrupted:corrupted_blossom_samurai")
    - Prints ready-to-paste constants for core/images.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import discord
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT             = Path(__file__).resolve().parent.parent
IMAGE_DIR        = ROOT / "assets" / "images" / "corrupted_monsters"
CDN_MAP_OUT      = ROOT / "assets" / "images" / "discord_url_map.json"
ASSET_CHANNEL_ID = 1334637411363323996
BATCH_DELAY      = 1.2  # seconds between batches (rate-limit headroom)

# ---------------------------------------------------------------------------
# Load env
# ---------------------------------------------------------------------------

load_dotenv(ROOT / ".env")
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    sys.exit("ERROR: TOKEN not found in .env")

# ---------------------------------------------------------------------------
# Build work list
# ---------------------------------------------------------------------------

images = sorted(IMAGE_DIR.glob("*.jpg")) + sorted(IMAGE_DIR.glob("*.png"))
if not images:
    sys.exit(f"ERROR: no images found in {IMAGE_DIR}")

print(f"Found {len(images)} corrupted monster image(s):")
for img in images:
    print(f"  {img.name}")
print()

# ---------------------------------------------------------------------------
# Resume support
# ---------------------------------------------------------------------------

existing_cdn: dict[str, str] = {}
if CDN_MAP_OUT.exists():
    existing_cdn = json.loads(CDN_MAP_OUT.read_text(encoding="utf-8"))

cdn_map: dict[str, str] = dict(existing_cdn)

already_done = [img for img in images if f"corrupted:{img.stem}" in existing_cdn]
if already_done:
    print(f"Resuming: {len(already_done)} image(s) already uploaded, skipping:")
    for img in already_done:
        print(f"  {img.name}  →  {existing_cdn[f'corrupted:{img.stem}']}")
    images = [img for img in images if f"corrupted:{img.stem}" not in existing_cdn]
    print()

if not images:
    print("All images already uploaded. Printing constants:\n")
    _print_constants(existing_cdn)
    sys.exit(0)

# ---------------------------------------------------------------------------
# Discord client
# ---------------------------------------------------------------------------

results: dict[str, str] = {}   # stem → cdn_url


def _make_const_name(stem: str) -> str:
    """corrupted_blossom_samurai  →  CORRUPTED_BLOSSOM_SAMURAI"""
    return stem.upper()


def _print_constants(cdn: dict[str, str]) -> None:
    print("# ── CORRUPTED MONSTERS ──────────────────────────────────────────────────────")
    print("CORRUPTED_MONSTERS = {")
    for img in sorted(IMAGE_DIR.glob("*.jpg")) + sorted(IMAGE_DIR.glob("*.png")):
        key = f"corrupted:{img.stem}"
        url = cdn.get(key, "UPLOAD_FAILED")
        # Map filename stem → display key (strip leading "corrupted_" prefix for lookup)
        display_key = img.stem.removeprefix("corrupted_")
        print(f'    "{display_key}": "{url}",')
    print("}")


class UploaderClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f"Logged in as {self.user}  (id={self.user.id})")

        channel = self.get_channel(ASSET_CHANNEL_ID)
        if channel is None:
            channel = await self.fetch_channel(ASSET_CHANNEL_ID)
        if channel is None:
            print(f"ERROR: cannot find channel {ASSET_CHANNEL_ID}")
            await self.close()
            return

        print(f"Uploading to #{channel.name} in {channel.guild.name}\n")

        # All corrupted images fit in one Discord message (≤10 attachments)
        files = []
        for img_path in images:
            try:
                files.append(discord.File(str(img_path), filename=img_path.name))
            except Exception as e:
                print(f"  WARN: could not open {img_path.name}: {e}")

        if not files:
            print("ERROR: no files to upload.")
            await self.close()
            return

        try:
            msg = await channel.send(files=files)
        except discord.HTTPException as e:
            print(f"ERROR: upload failed: {e}")
            await self.close()
            return

        await asyncio.sleep(BATCH_DELAY)

        # Map attachment filenames back to their CDN URLs
        att_by_name = {att.filename: att.url for att in msg.attachments}
        for img_path in images:
            cdn_url = att_by_name.get(img_path.name)
            if cdn_url:
                key = f"corrupted:{img_path.stem}"
                cdn_map[key] = cdn_url
                results[img_path.stem] = cdn_url
                print(f"  ✓  {img_path.name}")
            else:
                print(f"  ✗  {img_path.name}  (no matching attachment returned)")

        # Persist to discord_url_map.json
        CDN_MAP_OUT.write_text(json.dumps(cdn_map, indent=2), encoding="utf-8")
        print(f"\nCDN map updated → {CDN_MAP_OUT.relative_to(ROOT).as_posix()}")

        # Print copy-pasteable constants
        print("\n" + "=" * 72)
        print("Add the following to core/images.py:\n")
        _print_constants(cdn_map)
        print("=" * 72)

        await self.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    client = UploaderClient()
    client.run(TOKEN, log_handler=None)
