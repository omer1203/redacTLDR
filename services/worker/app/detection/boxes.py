"""Turn a character span into page rectangles.

Every OCR word that overlaps the span is included in full, so a value glued to
a label in one OCR word ("Email:jane@x.com") covers the whole word. That
over-redacts slightly, which is the safe direction. Words are grouped by OCR
line and each line becomes one rectangle, so a wrapped address gets one box per line.

Boxes are normalized 0–1 page coordinates, top-left origin, same as Textract.
"""

from __future__ import annotations

from collections.abc import Iterable

from services.worker.app.detection.models import Box, PageText, WordSpan

_PRECISION = 6


def words_in_span(page: PageText, start: int, end: int) -> list[WordSpan]:
    return [word for word in page.words if word.start < end and word.end > start]


def union_boxes(boxes: Iterable[Box]) -> Box | None:
    left = top = right = bottom = None
    for box in boxes:
        x0 = float(box.get("x", 0.0))
        y0 = float(box.get("y", 0.0))
        x1 = x0 + float(box.get("width", 0.0))
        y1 = y0 + float(box.get("height", 0.0))
        left = x0 if left is None else min(left, x0)
        top = y0 if top is None else min(top, y0)
        right = x1 if right is None else max(right, x1)
        bottom = y1 if bottom is None else max(bottom, y1)
    if left is None or top is None or right is None or bottom is None:
        return None
    left, top = max(0.0, left), max(0.0, top)
    right, bottom = min(1.0, right), min(1.0, bottom)
    return {
        "x": round(left, _PRECISION),
        "y": round(top, _PRECISION),
        "width": round(max(0.0, right - left), _PRECISION),
        "height": round(max(0.0, bottom - top), _PRECISION),
    }


def rects_for_span(page: PageText, start: int, end: int) -> list[Box]:
    by_line: dict[int, list[Box]] = {}
    for word in words_in_span(page, start, end):
        # dict keeps insertion order, and words are in reading order, so lines stay in order.
        by_line.setdefault(word.line_index, []).append(word.bbox)
    rects = [union_boxes(boxes) for boxes in by_line.values()]
    return [rect for rect in rects if rect]
