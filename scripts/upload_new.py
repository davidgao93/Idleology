"""
upload_new.py — Upload new images from assets/images/upload/ to Discord.

Usage:
    python scripts/upload_new.py [--dry-run]

  --dry-run    List files that would be uploaded without actually uploading.

For each image file found in assets/images/upload/ the script:
  1. Uploads it to the seeding channel via the Discord bot API.
  2. Appends a line to assets/images/upload_log.txt:
         filename  |  <discord cdn url>
  3. Moves the file to assets/images/upload/done/ so it won't be re-uploaded.

The bot token is read from .env (TOKEN=...).
Channel: 1334637411363323996  (guild 699690514051629086)
"""

import asyncio
import mimetypes
import os
import shutil
import sys
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = ROOT / "assets" / "images" / "upload"
DONE_DIR = UPLOAD_DIR / "done"
LOG_FILE = ROOT / "assets" / "images" / "upload_log.txt"

CHANNEL_ID = "1334637411363323996"
DISCORD_API = "https://discord.com/api/v10"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
BATCH_SIZE = 10

# Respect Discord's per-channel rate limit: ~5 msg/5s.
UPLOAD_DELAY = 1.2  # seconds between messages


# ── Discord upload ─────────────────────────────────────────────────────────────


async def upload_batch(
    session: aiohttp.ClientSession, token: str, filepaths: list[Path]
) -> list[tuple[str, str]]:
    """Upload up to 10 files in one message; return [(filename, cdn_url), ...]."""
    url = f"{DISCORD_API}/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {token}"}

    file_handles = []
    try:
        form = aiohttp.FormData()
        for i, filepath in enumerate(filepaths):
            mime = mimetypes.guess_type(filepath.name)[0] or "application/octet-stream"
            fh = filepath.open("rb")
            file_handles.append(fh)
            form.add_field(f"files[{i}]", fh, filename=filepath.name, content_type=mime)

        async with session.post(url, headers=headers, data=form) as resp:
            if resp.status not in (200, 201):
                body = await resp.text()
                raise RuntimeError(f"Discord API {resp.status}: {body}")
            data = await resp.json()
            attachments = data.get("attachments", [])
            # Discord returns attachments sorted by filename; map back by filename.
            url_by_name = {a["filename"]: a["url"] for a in attachments}
            return [(fp.name, url_by_name[fp.name]) for fp in filepaths]
    finally:
        for fh in file_handles:
            fh.close()


# ── log helpers ───────────────────────────────────────────────────────────────


def append_log(fname: str, cdn_url: str):
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"{fname}  |  {cdn_url}\n")


def already_logged(fname: str) -> bool:
    if not LOG_FILE.exists():
        return False
    with LOG_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith(fname + "  |"):
                return True
    return False


# ── main ──────────────────────────────────────────────────────────────────────


async def main(dry_run: bool):
    load_dotenv(ROOT / ".env")
    token = os.getenv("TOKEN")
    if not token:
        sys.exit("ERROR: TOKEN not found in .env")

    if not UPLOAD_DIR.exists():
        sys.exit(f"ERROR: Upload folder not found: {UPLOAD_DIR}")

    files = sorted(
        p
        for p in UPLOAD_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )

    if not files:
        print("No new images found in upload/.")
        return

    # Filter out already-logged files before batching.
    pending = [f for f in files if not already_logged(f.name)]
    skipped = len(files) - len(pending)

    print(
        f"Found {len(files)} image(s): {len(pending)} to upload, {skipped} already logged.\n"
    )

    if dry_run:
        for f in files:
            flag = " (already in log)" if already_logged(f.name) else ""
            print(f"  [DRY-RUN] {f.name}{flag}")
        batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\n{len(pending)} file(s) across {batches} message(s).")
        return

    if not pending:
        print("Nothing to upload.")
        return

    DONE_DIR.mkdir(exist_ok=True)

    # Split into batches of up to BATCH_SIZE.
    batches = [pending[i : i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
    total_batches = len(batches)

    async with aiohttp.ClientSession() as session:
        for b_idx, batch in enumerate(batches):
            names = ", ".join(f.name for f in batch)
            print(
                f"  [msg {b_idx + 1}/{total_batches}] Uploading {len(batch)} file(s): {names} ... ",
                end="",
                flush=True,
            )
            try:
                results = await upload_batch(session, token, batch)
                for fname, cdn_url in results:
                    append_log(fname, cdn_url)
                    shutil.move(str(UPLOAD_DIR / fname), str(DONE_DIR / fname))
                print("OK")
                for fname, cdn_url in results:
                    print(f"    {fname}  ->  {cdn_url}")
            except Exception as exc:
                print(f"FAILED — {exc}")

            if b_idx < total_batches - 1:
                await asyncio.sleep(UPLOAD_DELAY)

    print(f"\nLog saved to: {LOG_FILE.relative_to(ROOT)}")
    print(f"Uploaded files moved to: {DONE_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(main(dry_run))
