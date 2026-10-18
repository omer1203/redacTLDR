"""Review state → what to remove (`RedactionBox`) and what to check for afterwards (`LeakProbe`).

Inputs are plain mappings with the column names of `detections` and
`manual_redactions`, so this module has no database code and is unit-tested
with dicts. Only accepted detections and active manual boxes should be passed in.

Fail closed: a selected item without a usable box stops the export instead of
being skipped, because skipping it would leave its value in the file.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from services.shared.policy import entity_type_info
from services.worker.app.detection.models import PageText
from services.worker.app.detection.page_text import build_page_text
from services.worker.app.redaction.geometry import boxes_intersect, center_inside, usable_box
from services.worker.app.redaction.matching import compact, compact_with_flags, uncovered_occurrences
from services.worker.app.redaction.models import Box, ExportError, LeakProbe, RedactionBox

Row = Mapping[str, Any]


def _invalid_item() -> ExportError:
    return ExportError(
        "INVALID_REDACTION",
        "A selected item has no usable position on the page, so nothing was exported. "
        "Turn that item off or draw a box over it, then export again.",
        retryable=False,
    )


def detection_boxes(row: Row) -> list[Box]:
    """Every rectangle of one detection. `rects` (R3) wins; `bbox` is the pre-R3 fallback."""
    raw_rects = row.get("rects") or []
    if raw_rects:
        boxes = [usable_box(raw) for raw in raw_rects]
        # One bad line box would leave that line of the value in place.
        if any(box is None for box in boxes):
            raise _invalid_item()
        return [box for box in boxes if box is not None]
    fallback = usable_box(row.get("bbox"))
    if fallback is None:
        raise _invalid_item()
    return [fallback]


def _page_number(row: Row) -> int:
    try:
        number = int(row.get("page_number") or 0)
    except (TypeError, ValueError):
        number = 0
    if number < 1:
        raise _invalid_item()
    return number


def build_targets(detections: Iterable[Row], manual_redactions: Iterable[Row]) -> tuple[RedactionBox, ...]:
    """One `RedactionBox` per rectangle, detections first, in page order."""
    boxes: list[RedactionBox] = []
    for row in detections:
        page_number = _page_number(row)
        label = entity_type_info(str(row.get("entity_type") or "")).label
        boxes.extend(RedactionBox(page_number, rect, label, "detection") for rect in detection_boxes(row))
    for row in manual_redactions:
        page_number = _page_number(row)
        rect = usable_box(row.get("bbox"))
        if rect is None:
            raise _invalid_item()
        label = entity_type_info(str(row.get("entity_type") or "")).label
        boxes.append(RedactionBox(page_number, rect, label, "manual"))
    boxes.sort(key=lambda box: box.page_number)
    return tuple(boxes)


def _ocr_pages(ocr_payload: Mapping[str, Any] | None) -> dict[int, PageText]:
    pages: dict[int, PageText] = {}
    for page in (ocr_payload or {}).get("pages") or []:
        page_text = build_page_text(page)
        pages[page_text.page_number] = page_text
    return pages


def _covered_flags(page_text: PageText, page_boxes: Sequence[Box]) -> list[bool]:
    """Per character of the page text: does its OCR word touch any redaction box on the page?"""
    flags = [False] * len(page_text.text)
    for word in page_text.words:
        word_box = usable_box(word.bbox)
        if word_box is None:
            continue
        if any(boxes_intersect(word_box, box) for box in page_boxes):
            for index in range(word.start, word.end):
                flags[index] = True
    return flags


def _manual_phrases(page_text: PageText, box: Box) -> list[str]:
    """Text under a drawn box: words whose center is inside it, one phrase per OCR line."""
    by_line: dict[int, list[str]] = {}
    for word in page_text.words:
        word_box = usable_box(word.bbox)
        if word_box is not None and center_inside(word_box, box):
            by_line.setdefault(word.line_index, []).append(page_text.text[word.start : word.end])
    return [" ".join(words) for words in by_line.values()]


def build_probes(
    ocr_payload: Mapping[str, Any] | None,
    detections: Iterable[Row],
    manual_redactions: Iterable[Row],
    boxes: Sequence[RedactionBox],
) -> tuple[tuple[LeakProbe, ...], int]:
    """Return `(probes, skipped)`.

    A detection's value is its `char_start:char_end` slice of the page text,
    rebuilt with the same builder the detector used. A value may legitimately
    appear elsewhere on the page outside every box; `allowed` counts those
    places so they do not fail the check. Detections without offsets (pre-R3),
    or with offsets that no longer fit the OCR text, are counted as skipped.
    The geometric check in `verify` still covers them.
    """
    pages = _ocr_pages(ocr_payload)
    boxes_by_page: dict[int, list[Box]] = {}
    for box in boxes:
        boxes_by_page.setdefault(box.page_number, []).append(box.rect)
    compacted: dict[int, tuple[str, list[bool]]] = {}

    def allowed_for(page_number: int, value: str) -> int:
        if page_number not in compacted:
            page_text = pages[page_number]
            compacted[page_number] = compact_with_flags(
                page_text.text, _covered_flags(page_text, boxes_by_page.get(page_number, []))
            )
        haystack, flags = compacted[page_number]
        return uncovered_occurrences(haystack, flags, compact(value))

    probes: list[LeakProbe] = []
    skipped = 0
    for row in detections:
        page_number = _page_number(row)
        page_text = pages.get(page_number)
        start, end = row.get("char_start"), row.get("char_end")
        if page_text is None or not isinstance(start, int) or not isinstance(end, int):
            skipped += 1
            continue
        if not 0 <= start < end <= len(page_text.text):
            skipped += 1
            continue
        value = page_text.text[start:end]
        probes.append(LeakProbe(page_number, "detection", value, allowed_for(page_number, value)))

    for row in manual_redactions:
        page_number = _page_number(row)
        page_text = pages.get(page_number)
        rect = usable_box(row.get("bbox"))
        if page_text is None or rect is None:
            skipped += 1
            continue
        for phrase in _manual_phrases(page_text, rect):
            probes.append(LeakProbe(page_number, "manual", phrase, allowed_for(page_number, phrase)))

    return tuple(probes), skipped
