"""Value types passed between the detection steps.

Offsets (`start`, `end`, `char_start`, `char_end`) always index the page text
produced by `page_text.build_page_text`. R5 rebuilds that same text from the
OCR JSON to verify an export, so the builder must stay deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

Box = dict[str, float]


class DetectionError(Exception):
    """A detection failure whose `message` is safe to show the user. It never contains document text."""

    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class WordSpan:
    """One OCR word and where it sits in the page text."""

    start: int
    end: int
    # Index into the OCR page's `lines` list, so later phases can find the source line.
    line_index: int
    bbox: Box


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str
    words: tuple[WordSpan, ...]


@dataclass(frozen=True)
class Candidate:
    """A raw hit from Comprehend or a custom rule, before policy and merging."""

    start: int
    end: int
    entity_type: str
    confidence: float
    source: str  # "comprehend" or "rule"
    rule_id: str | None = None


@dataclass(frozen=True)
class Finding:
    """A detection ready to store: policy applied, boxes computed, text masked."""

    page_number: int
    entity_type: str
    confidence: float
    source: str
    rule_id: str | None
    char_start: int
    char_end: int
    rects: tuple[Box, ...]
    bbox: Box
    block_ref: str
    masked_text: str
    policy_action: str
    accepted: bool
    # Kept out of repr so a logged Finding cannot leak the value.
    raw_text: str = field(repr=False)
