from discord import Message


def load_list(filepath: str) -> list:
    """Load a list from a text file."""
    with open(filepath, "r") as file:
        return [line.strip() for line in file.readlines()]


def stars(n: int) -> str:
    """Returns a star-rating string for a weapon base rarity (1–3 → ★ / ★★ / ★★★)."""
    return "★" * max(0, n)


async def clear_msg(message: Message):
    if message:
        await message.delete()