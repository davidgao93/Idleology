"""
core/character/prestige_display.py — Shared prestige name formatter.

Combat embeds, the profile Card, and the Prestige Shop preview all need the
identical "{emblem} [TITLE] name" string — centralised here so those call
sites can never drift out of sync.
"""


def format_prestige_name(name: str, title: str = "", emblem: str = "") -> str:
    parts: list[str] = []
    if emblem:
        parts.append(emblem)
    if title:
        parts.append(f"[{title}]")
    parts.append(name)
    return " ".join(parts)
