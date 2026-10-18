"""Whitespace- and case-insensitive substring counting for the leak check.

The OCR text (Textract words joined by spaces) and the text PyMuPDF extracts
from the exported PDF break lines and space words differently. Dropping all
whitespace and casefolding both sides makes "Jane\nDoe" and "jane doe" match.
"""

from __future__ import annotations

from collections.abc import Sequence


def compact(text: str) -> str:
    return "".join(ch.casefold() for ch in text if not ch.isspace())


def compact_with_flags(text: str, flags: Sequence[bool]) -> tuple[str, list[bool]]:
    """`compact(text)` plus one flag per output character, copied from the input character.

    Casefolding can turn one character into two ("ß" → "ss"); both get its flag.
    """
    out: list[str] = []
    out_flags: list[bool] = []
    for ch, flag in zip(text, flags, strict=True):
        if ch.isspace():
            continue
        folded = ch.casefold()
        out.append(folded)
        out_flags.extend([flag] * len(folded))
    return "".join(out), out_flags


def occurrences(haystack: str, needle: str) -> list[int]:
    """Start index of every match, overlapping ones included."""
    if not needle:
        return []
    starts: list[int] = []
    index = haystack.find(needle)
    while index != -1:
        starts.append(index)
        index = haystack.find(needle, index + 1)
    return starts


def uncovered_occurrences(haystack: str, flags: Sequence[bool], needle: str) -> int:
    """Matches in which no character is flagged as covered by a redaction box."""
    width = len(needle)
    return sum(1 for start in occurrences(haystack, needle) if not any(flags[start : start + width]))
