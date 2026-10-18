"""Re-open the exported bytes and prove the redacted content is gone.

Two independent checks. Either one failing stops the export; nothing is uploaded.

1. Geometry (on the clean file, before labels): no character may remain inside
   any box. This covers every box, including drawn boxes over areas OCR did not
   read and detections without stored offsets.
2. Text (on the final file): each redacted value, rebuilt from the OCR JSON,
   may appear on its page at most as often as it appears outside every box.
   This catches a copy the geometry check cannot see, such as a value whose
   PDF glyphs sit away from where Textract saw the ink.

Scanned pages have no text layer, so only the boxes' pixels matter there;
`engine` blanks those with `PDF_REDACT_IMAGE_PIXELS`, and the tests check it.

Failure messages and logs carry counts and page numbers, never the values.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import pymupdf

from services.worker.app.redaction.geometry import page_rect
from services.worker.app.redaction.matching import compact, occurrences
from services.worker.app.redaction.models import ExportError, LeakProbe, RedactedPdf, RedactionBox, VerificationReport

logger = logging.getLogger(__name__)

# Characters touching a box edge by float noise are not leftovers.
GEOMETRY_TOLERANCE_PT = 0.25
# Values shorter than this ("IL", "5") match too much unrelated text to be a useful signal.
MIN_PROBE_CHARS = 3


def _leak_error() -> ExportError:
    return ExportError(
        "VERIFICATION_FAILED",
        "The redacted copy still contained text from a redacted area, so it was not saved. "
        "Drawing a slightly larger box over the item usually fixes this.",
        retryable=False,
    )


def _open(data: bytes, expected_pages: int) -> pymupdf.Document:
    document = pymupdf.open(stream=data, filetype="pdf")
    if document.page_count != expected_pages:
        document.close()
        raise ExportError("VERIFICATION_FAILED", "The redacted copy has the wrong number of pages.", retryable=False)
    return document


def _character_boxes(page: pymupdf.Page) -> list[pymupdf.Rect]:
    """Every non-space character on the page, in unrotated page points."""
    boxes: list[pymupdf.Rect] = []
    for block in page.get_text("rawdict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                for char in span["chars"]:
                    if not char["c"].isspace():
                        boxes.append(pymupdf.Rect(char["bbox"]))
    return boxes


def _touches(char: pymupdf.Rect, area: pymupdf.Rect) -> bool:
    # The center test catches zero-width glyph boxes, which `intersects` treats as empty.
    center = pymupdf.Point((char.x0 + char.x1) / 2, (char.y0 + char.y1) / 2)
    return char.intersects(area) or area.contains(center)


def verify_geometry(clean: bytes, boxes: Sequence[RedactionBox], expected_pages: int) -> int:
    """Return the number of boxes checked."""
    document = _open(clean, expected_pages)
    leaking_pages: set[int] = set()
    leaks = 0
    try:
        chars_by_page: dict[int, list[pymupdf.Rect]] = {}
        for box in boxes:
            page = document[box.page_number - 1]
            if box.page_number not in chars_by_page:
                chars_by_page[box.page_number] = _character_boxes(page)
            area = page_rect(page, box.rect)
            area = pymupdf.Rect(
                area.x0 + GEOMETRY_TOLERANCE_PT,
                area.y0 + GEOMETRY_TOLERANCE_PT,
                area.x1 - GEOMETRY_TOLERANCE_PT,
                area.y1 - GEOMETRY_TOLERANCE_PT,
            )
            if area.is_empty:
                continue
            if any(_touches(char, area) for char in chars_by_page[box.page_number]):
                leaks += 1
                leaking_pages.add(box.page_number)
    finally:
        document.close()
    if leaks:
        logger.error("export verification geometry leaks=%s pages=%s", leaks, sorted(leaking_pages))
        raise _leak_error()
    return len(boxes)


def verify_text(final: bytes, probes: Sequence[LeakProbe], expected_pages: int) -> tuple[int, int]:
    """Return `(checked, skipped)` probe counts."""
    document = _open(final, expected_pages)
    texts: dict[int, str] = {}
    checked = skipped = leaks = 0
    leaking_pages: set[int] = set()
    try:
        for probe in probes:
            needle = compact(probe.text)
            if len(needle) < MIN_PROBE_CHARS:
                skipped += 1
                continue
            if not 1 <= probe.page_number <= expected_pages:
                raise _leak_error()
            if probe.page_number not in texts:
                texts[probe.page_number] = compact(document[probe.page_number - 1].get_text("text"))
            checked += 1
            if len(occurrences(texts[probe.page_number], needle)) > probe.allowed:
                leaks += 1
                leaking_pages.add(probe.page_number)
    finally:
        document.close()
    if leaks:
        logger.error("export verification text leaks=%s pages=%s", leaks, sorted(leaking_pages))
        raise _leak_error()
    return checked, skipped


def verify_export(
    redacted: RedactedPdf,
    boxes: Sequence[RedactionBox],
    probes: Sequence[LeakProbe],
    *,
    probes_skipped: int = 0,
) -> VerificationReport:
    """Run both checks. Raises `ExportError("VERIFICATION_FAILED")` on any leftover."""
    boxes_checked = verify_geometry(redacted.clean, boxes, redacted.page_count)
    checked, skipped = verify_text(redacted.final, probes, redacted.page_count)
    return VerificationReport(
        boxes_checked=boxes_checked,
        probes_checked=checked,
        probes_skipped=skipped + probes_skipped,
    )
