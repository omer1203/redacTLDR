"""Build the text the model is allowed to see.

Safe mode replaces every accepted detection, and every word under an active drawn
box, with a typed token such as ``[EMAIL]``. The raw slice is remembered only so
the result can be rejected if the model writes it back. Safe mode off sends the
OCR text unchanged, which is what the reviewer asked for by turning it off.

Offsets come from the same `build_page_text` layout detection used, so a
`char_start:char_end` span covers the value and nothing beside it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from services.worker.app.detection.page_text import build_page_text
from services.worker.app.redaction.geometry import boxes_intersect, usable_box
from services.worker.app.redaction.matching import compact, occurrences
from services.worker.app.summary.errors import SummaryError

# Shorter than this, a redacted value is too easy to collide with an ordinary word.
MIN_FORBIDDEN_CHARS = 3


@dataclass(frozen=True)
class PageSource:
    page_number: int
    text: str


@dataclass(frozen=True)
class SummarySource:
    pages: tuple[PageSource, ...]
    # Values removed from the prompt. The output must not contain them.
    forbidden: tuple[str, ...]


def _token(entity_type: str) -> str:
    # The label is for people ("Email"); the token stays the stable type id.
    return f"[{entity_type or 'REDACTED'}]"


def _boxes(row: Mapping[str, Any]) -> list[dict[str, float]]:
    raw = row.get("rects") or []
    if not raw and row.get("bbox"):
        raw = [row["bbox"]]
    return [box for item in raw if (box := usable_box(item))]


def _char_span(row: Mapping[str, Any], length: int) -> tuple[int, int] | None:
    start, end = row.get("char_start"), row.get("char_end")
    if start is None or end is None:
        return None
    start, end = int(start), int(end)
    if start < 0 or end > length or end <= start:
        return None
    return start, end


def apply_spans(text: str, spans: Sequence[tuple[int, int, str]]) -> tuple[str, list[str]]:
    """Replace spans with their tokens. Overlaps keep the earlier span. Returns the removed slices."""
    pieces: list[str] = []
    removed: list[str] = []
    cursor = 0
    for start, end, token in sorted(spans, key=lambda item: (item[0], -item[1])):
        start = max(0, min(len(text), start))
        end = max(0, min(len(text), end))
        if start < cursor:
            start = cursor
        if end <= start:
            continue
        pieces.append(text[cursor:start])
        pieces.append(token)
        removed.append(text[start:end])
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces), removed


def _word_spans(page_text, row: Mapping[str, Any]) -> list[tuple[int, int]]:
    """Each OCR word the row's box touches. Gaps between words are left as-is."""
    boxes = _boxes(row)
    return [
        (word.start, word.end)
        for word in page_text.words
        if (word_box := usable_box(word.bbox)) and any(boxes_intersect(word_box, box) for box in boxes)
    ]


def build_source(
    ocr_payload: Mapping[str, Any],
    detections: Sequence[Mapping[str, Any]],
    manual: Sequence[Mapping[str, Any]],
    *,
    safe_mode: bool,
) -> SummarySource:
    pages_in = ocr_payload.get("pages")
    if not isinstance(pages_in, list) or not pages_in:
        raise SummaryError(
            "OCR_MISSING",
            "The extracted text was not found, so the summary was not sent. Reprocess the document.",
            retryable=False,
        )

    pages: list[PageSource] = []
    removed: list[str] = []
    for raw_page in pages_in:
        page_text = build_page_text(raw_page)
        number = page_text.page_number
        if not safe_mode:
            pages.append(PageSource(number, page_text.text))
            continue
        spans: list[tuple[int, int, str]] = []
        for row in detections:
            if int(row.get("page_number") or 0) != number:
                continue
            token = _token(str(row.get("entity_type") or ""))
            span = _char_span(row, len(page_text.text))
            word_spans = [] if span else _word_spans(page_text, row)
            if span is None and not word_spans:
                # Sending the page would include a value the reviewer chose to redact.
                raise SummaryError(
                    "REDACTION_UNLOCATED",
                    "A selected item could not be located in the text, so the summary was not sent. Reprocess the document.",
                    retryable=False,
                )
            if span:
                spans.append((span[0], span[1], token))
            spans.extend((start, end, token) for start, end in word_spans)
        for row in manual:
            if int(row.get("page_number") or 0) != number:
                continue
            token = _token(str(row.get("entity_type") or "CUSTOM"))
            spans.extend((start, end, token) for start, end in _word_spans(page_text, row))
        masked, gone = apply_spans(page_text.text, spans)
        pages.append(PageSource(number, masked))
        removed.extend(gone)

    if not safe_mode:
        return SummarySource(tuple(pages), ())

    visible = compact("\n".join(page.text for page in pages))
    forbidden = tuple(
        value
        for value in removed
        if len(compact(value)) >= MIN_FORBIDDEN_CHARS and not occurrences(visible, compact(value))
    )
    return SummarySource(tuple(pages), forbidden)
