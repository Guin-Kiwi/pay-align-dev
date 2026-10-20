"""Shared parsing of hours typed as H:MM into whole minutes."""

import re

HOURS_PATTERN = re.compile(r"([0-9]{1,2}):([0-5][0-9])")


def parse_hours(text: str) -> int:
    """Return whole minutes for hours typed as H:MM, for example 6:30 -> 390."""
    match = HOURS_PATTERN.fullmatch(text)
    minutes = int(match[1]) * 60 + int(match[2]) if match else 0
    if minutes == 0:
        raise ValueError("Invalid weekly hours. Use H:MM above 0:00, for example 6:30.")
    return minutes
