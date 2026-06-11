"""
reseed_images.py — Re-upload expired Discord CDN images and patch core/images.py.

Discord CDN URLs expire after ~1 year. This script:
  1. Parses every URL from core/images.py.
  2. Checks whether each URL's expiry timestamp (hex `ex=` query param) has passed.
  3. For each expired URL, finds the corresponding local file in assets/images/,
     re-uploads it to the seeding channel, and updates images.py in place.

Usage:
    python scripts/reseed_images.py            # dry-run: show what would change
    python scripts/reseed_images.py --execute  # actually re-upload and patch

The bot token is read from .env (TOKEN=...).
Channel: 1334637411363323996  (guild 699690514051629086)
"""

import asyncio
import importlib.util
import mimetypes
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import aiohttp
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
IMAGES_PY = ROOT / "core" / "images.py"
IMAGES_DIR = ROOT / "assets" / "images"

CHANNEL_ID = "1334637411363323996"
DISCORD_API = "https://discord.com/api/v10"

UPLOAD_DELAY = 1.2  # seconds between uploads to respect rate limits
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


# ── URL helpers ───────────────────────────────────────────────────────────────


def filename_from_url(url: str) -> str:
    return Path(urlparse(url).path).name


def expiry_timestamp(url: str) -> int | None:
    """Return Unix expiry timestamp from the `ex=` hex query param, or None."""
    qs = parse_qs(urlparse(url).query)
    ex_values = qs.get("ex", [])
    if not ex_values:
        return None
    try:
        return int(ex_values[0], 16)
    except ValueError:
        return None


def is_expired(url: str, buffer_days: int = 30) -> bool:
    """
    Return True if the URL is expired or will expire within `buffer_days`.
    Treating non-Discord or unparseable URLs as expired so they get refreshed too.
    """
    exp = expiry_timestamp(url)
    if exp is None:
        return True
    return time.time() > (exp - buffer_days * 86400)


def format_expiry(url: str) -> str:
    exp = expiry_timestamp(url)
    if exp is None:
        return "unknown"
    import datetime

    return datetime.datetime.utcfromtimestamp(exp).strftime("%Y-%m-%d")


# ── Module inspection ─────────────────────────────────────────────────────────


def load_images_module():
    spec = importlib.util.spec_from_file_location("images", IMAGES_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def collect_urls(mod) -> list[tuple[str, str]]:
    """Return [(label, url)] for all Discord CDN URLs in the module."""
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


# ── Local file search ─────────────────────────────────────────────────────────


def build_local_index(images_dir: Path) -> dict[str, Path]:
    """Return {filename: first matching path} for all files under images_dir."""
    index: dict[str, Path] = {}
    for path in images_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            index.setdefault(path.name, path)
    return index


# ── Discord upload ─────────────────────────────────────────────────────────────


async def upload_file(
    session: aiohttp.ClientSession, token: str, filepath: Path
) -> str:
    url = f"{DISCORD_API}/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {token}"}
    fname = filepath.name
    mime = mimetypes.guess_type(fname)[0] or "application/octet-stream"

    with filepath.open("rb") as fh:
        form = aiohttp.FormData()
        form.add_field("files[0]", fh, filename=fname, content_type=mime)

        async with session.post(url, headers=headers, data=form) as resp:
            if resp.status not in (200, 201):
                body = await resp.text()
                raise RuntimeError(f"Discord API {resp.status}: {body}")
            data = await resp.json()
            attachments = data.get("attachments", [])
            if not attachments:
                raise RuntimeError(f"No attachments in response for {fname}")
            return attachments[0]["url"]


# ── images.py patching ────────────────────────────────────────────────────────


def patch_images_py(old_url: str, new_url: str) -> int:
    """Replace all occurrences of old_url with new_url in images.py. Returns count replaced."""
    text = IMAGES_PY.read_text(encoding="utf-8")
    # Escape the URL for use in a regex pattern (handles ? & = etc.)
    escaped = re.escape(old_url)
    new_text, count = re.subn(escaped, new_url, text)
    if count:
        IMAGES_PY.write_text(new_text, encoding="utf-8")
    return count


# ── main ──────────────────────────────────────────────────────────────────────


async def main(execute: bool):
    load_dotenv(ROOT / ".env")
    token = os.getenv("TOKEN")
    if not execute:
        print(
            "DRY-RUN mode. Pass --execute to actually re-upload and patch images.py.\n"
        )
    elif not token:
        sys.exit("ERROR: TOKEN not found in .env")

    mod = load_images_module()
    all_entries = collect_urls(mod)
    local_index = build_local_index(IMAGES_DIR)

    # De-duplicate URLs so we upload each file only once even if shared
    # (e.g. temple.png used by 4 building types).
    seen_urls: dict[str, str] = {}  # old_url -> new_url (populated after upload)
    expired_entries: list[tuple[str, str]] = []

    for label, url in all_entries:
        if is_expired(url) and url not in seen_urls:
            expired_entries.append((label, url))
            seen_urls[url] = ""  # placeholder

    total = len(all_entries)
    expired = len(expired_entries)
    print(
        f"Scanned {total} URL entries. {expired} expired (or expiring within 30 days).\n"
    )

    if expired == 0:
        print("Nothing to reseed.")
        return

    # Show what needs doing
    no_local: list[tuple[str, str]] = []
    uploadable: list[tuple[str, str, Path]] = []

    for label, url in expired_entries:
        fname = filename_from_url(url)
        local_path = local_index.get(fname)
        exp_str = format_expiry(url)

        if local_path is None:
            print(f"  NO LOCAL FILE  {label:<45}  {fname}  (expires {exp_str})")
            no_local.append((label, url))
        else:
            rel = local_path.relative_to(ROOT)
            print(f"  RESEED         {label:<45}  {rel}  (expires {exp_str})")
            uploadable.append((label, url, local_path))

    if no_local:
        print(f"\n  {len(no_local)} URL(s) have no local file — skipping them.")
        print("  Add the originals to assets/images/ then re-run this script.\n")

    if not uploadable:
        print("\nNothing uploadable.")
        return

    if not execute:
        print(f"\n{len(uploadable)} file(s) would be re-uploaded.")
        print("Re-run with --execute to apply changes.")
        return

    print(f"\nRe-uploading {len(uploadable)} file(s)...\n")
    patched_count = 0

    async with aiohttp.ClientSession() as session:
        for i, (label, old_url, local_path) in enumerate(uploadable):
            fname = local_path.name

            # Already uploaded this URL in an earlier dedup pass?
            if seen_urls.get(old_url):
                new_url = seen_urls[old_url]
                print(
                    f"  [{i + 1}/{len(uploadable)}] {fname}  (reusing earlier upload)"
                )
            else:
                print(
                    f"  [{i + 1}/{len(uploadable)}] Uploading {fname} ... ",
                    end="",
                    flush=True,
                )
                try:
                    new_url = await upload_file(session, token, local_path)
                    seen_urls[old_url] = new_url
                    print("OK")
                except Exception as exc:
                    print(f"FAILED — {exc}")
                    continue

            replaced = patch_images_py(old_url, new_url)
            patched_count += replaced
            print(f"         Patched {replaced} occurrence(s) in images.py")

            if i < len(uploadable) - 1:
                await asyncio.sleep(UPLOAD_DELAY)

    print(f"\nDone. {patched_count} URL replacement(s) written to images.py.")


if __name__ == "__main__":
    execute = "--execute" in sys.argv
    asyncio.run(main(execute))
