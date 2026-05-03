"""
Phase 3 — Upload local assets to Discord CDN and record the CDN URLs.

Run from the project root:
    python tools/seed_discord_images.py

Reads:
    assets/images/url_map.json           — { imgur_url: local_path }

Outputs:
    assets/images/discord_url_map.json   — { imgur_url: discord_cdn_url }

The bot uploads every local file to the designated asset channel in batches
of 10 (Discord's per-message attachment limit). CDN URLs are extracted from
the response and written to discord_url_map.json when done.
"""

import argparse
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

ROOT = Path(__file__).resolve().parent.parent
URL_MAP      = ROOT / "assets" / "images" / "url_map.json"
CDN_MAP_OUT  = ROOT / "assets" / "images" / "discord_url_map.json"

ASSET_GUILD_ID   = 699690514051629086
ASSET_CHANNEL_ID = 1334637411363323996

BATCH_SIZE = 10          # Discord max attachments per message
BATCH_DELAY = 1.2        # seconds between batches (rate-limit headroom)

# ---------------------------------------------------------------------------
# Load env
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser()
parser.add_argument("--limit", type=int, default=0, help="Only upload this many files (0 = all). Useful for testing.")
args = parser.parse_args()

load_dotenv(ROOT / ".env")
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    sys.exit("ERROR: TOKEN not found in .env")

# ---------------------------------------------------------------------------
# Build work list
# ---------------------------------------------------------------------------

url_map: dict[str, str] = json.loads(URL_MAP.read_text(encoding="utf-8"))

# Filter to entries whose local file actually exists
work: list[tuple[str, Path]] = []
missing = 0
for imgur_url, rel_path in url_map.items():
    local = ROOT / rel_path
    if local.exists():
        work.append((imgur_url, local))
    else:
        print(f"WARN: missing local file, skipping: {rel_path}")
        missing += 1

if missing:
    print(f"{missing} local file(s) skipped (not found on disk).")

if args.limit:
    work = work[: args.limit]
    print(f"[TEST MODE] limiting to {args.limit} file(s)")

print(f"Files to upload : {len(work)}")
print(f"Batches (~{BATCH_SIZE}/msg): {-(-len(work) // BATCH_SIZE)}")  # ceil div
print()

# ---------------------------------------------------------------------------
# Resume support — load any CDN URLs already mapped from a previous run
# ---------------------------------------------------------------------------

existing_cdn: dict[str, str] = {}
if CDN_MAP_OUT.exists():
    existing_cdn = json.loads(CDN_MAP_OUT.read_text(encoding="utf-8"))
    already_done = sum(1 for u in work if u[0] in existing_cdn)
    if already_done:
        print(f"Resuming: {already_done} URLs already in discord_url_map.json, skipping those.")
        work = [(u, p) for u, p in work if u not in existing_cdn]
        print(f"Remaining to upload: {len(work)}\n")

# ---------------------------------------------------------------------------
# Discord client
# ---------------------------------------------------------------------------

cdn_map: dict[str, str] = dict(existing_cdn)  # start from any prior progress


def _batches(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


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

        total_batches = -(-len(work) // BATCH_SIZE)
        uploaded = 0
        failed_urls = []

        for batch_idx, batch in enumerate(_batches(work, BATCH_SIZE), 1):
            files = []
            for imgur_url, local_path in batch:
                try:
                    files.append(discord.File(str(local_path), filename=local_path.name))
                except Exception as e:
                    print(f"  WARN: could not open {local_path.name}: {e}")

            if not files:
                continue

            try:
                msg = await channel.send(files=files)
            except discord.HTTPException as e:
                print(f"  Batch {batch_idx}/{total_batches} FAILED: {e}")
                for imgur_url, _ in batch:
                    failed_urls.append(imgur_url)
                await asyncio.sleep(BATCH_DELAY)
                continue

            # Map each sent attachment back to its imgur URL
            # Attachments are in the same order as files sent
            att_by_name = {att.filename: att.url for att in msg.attachments}
            for imgur_url, local_path in batch:
                cdn_url = att_by_name.get(local_path.name)
                if cdn_url:
                    cdn_map[imgur_url] = cdn_url
                    uploaded += 1
                else:
                    print(f"  WARN: no attachment matched {local_path.name}")
                    failed_urls.append(imgur_url)

            # Save progress after every batch so a crash doesn't lose work
            CDN_MAP_OUT.write_text(json.dumps(cdn_map, indent=2), encoding="utf-8")

            print(f"  Batch {batch_idx:>4}/{total_batches}  ({uploaded} uploaded so far)")
            await asyncio.sleep(BATCH_DELAY)

        # Final save
        CDN_MAP_OUT.write_text(json.dumps(cdn_map, indent=2), encoding="utf-8")

        print(f"\nDone.")
        print(f"  Uploaded : {uploaded}")
        print(f"  Failed   : {len(failed_urls)}")
        if failed_urls:
            print("  Failed URLs:")
            for u in failed_urls:
                print(f"    {u}")
        print(f"\nCDN map written to {CDN_MAP_OUT.relative_to(ROOT).as_posix()}")

        await self.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    client = UploaderClient()
    client.run(TOKEN, log_handler=None)
