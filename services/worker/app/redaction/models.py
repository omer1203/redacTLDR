"""Value types passed between the export steps (R5).

Boxes are normalized 0–1 page fractions with a top-left origin, in the page
orientation a viewer shows. That is the space Textract, the review overlay,
and `manual_redactions.bbox` already use, so nothing is converted before
`geometry.page_rect` turns a box into PDF points.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Box = dict[str, float]


class ExportError(Exception):
    """An export failure whose `message` is safe to show the user. It never contains document text."""

    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class RedactionBox:
    """One area to remove from one page."""

    page_number: int
    rect: Box
    # Entity type label ("Email", "Manual redaction"). Drawn on the box only when labels are requested.
    label: str
    source: str  # "detection" | "manual"


@dataclass(frozen=True)
class LeakProbe:
    """Original text that must not be readable on its page after export.

    Built in memory from the OCR JSON and dropped when the task ends.
    """

    page_number: int
    source: str  # "detection" | "manual"
    # Kept out of repr so a logged probe cannot leak the value.
    text: str = field(repr=False)
    # Matches on the page outside every box, per the OCR text. The export may contain this many.
    allowed: int = 0


@dataclass(frozen=True)
class RedactedPdf:
    """Output of `engine.redact_pdf`.

    `clean` has every box applied and the file scrubbed. `final` is `clean`
    plus the optional labels; it is the file that gets uploaded.
    """

    clean: bytes = field(repr=False)
    final: bytes = field(repr=False)
    page_count: int
    boxes_applied: int
    labels_drawn: int


@dataclass(frozen=True)
class VerificationReport:
    """Counts only, safe for job results and logs."""

    boxes_checked: int
    probes_checked: int
    probes_skipped: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "boxesChecked": self.boxes_checked,
            "probesChecked": self.probes_checked,
            "probesSkipped": self.probes_skipped,
        }
