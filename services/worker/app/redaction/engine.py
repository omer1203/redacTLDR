"""True redaction with PyMuPDF: remove content under each box, then scrub the file.

Order matters:
1. Apply redaction annotations the PDF already carries (the author's own intent).
2. Bake annotations and form fields into page content, so a field value or a
   comment appearance under a box is removed with the page text.
3. Apply our boxes: text under a box is deleted, image pixels under it are
   blanked, vector paths fully inside it are dropped, a black box is drawn.
4. Delete invisible text everywhere (OCR layers, render mode 3), without fill.
5. Rewrite with garbage collection, then scrub metadata, XMP, JavaScript,
   links, attachments, thumbnails, and bookmarks, and rewrite again.
6. Optionally draw white type labels on the boxes ("Email"). This happens
   after the clean file exists, so labels are never mistaken for leftovers.

The output is always a full rewrite, never an incremental save, so removed
objects do not survive in an older revision of the file.

`Document.scrub(hidden_text=True)` is not used: it covers invisible spans with
the default white fill, which would paint over the visible text of a scanned page.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pymupdf

from services.worker.app.redaction.geometry import page_rect
from services.worker.app.redaction.models import ExportError, RedactedPdf, RedactionBox

MAX_PDF_BYTES = 20 * 1024 * 1024
BOX_FILL = (0, 0, 0)
LABEL_COLOR = (1, 1, 1)
LABEL_FONT = "helv"
MAX_LABEL_FONT_PT = 9.0
MIN_LABEL_FONT_PT = 4.0

_SAVE_OPTIONS = {"garbage": 4, "deflate": True, "clean": True, "encryption": pymupdf.PDF_ENCRYPT_NONE}


def _unreadable() -> ExportError:
    return ExportError("UNSUPPORTED_PDF", "The original file is not a readable PDF.", retryable=False)


def open_pdf(pdf_bytes: bytes) -> pymupdf.Document:
    """Open the original for writing. Password-protected files are refused."""
    if not pdf_bytes:
        raise ExportError("UNSUPPORTED_PDF", "The original file is empty.", retryable=False)
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ExportError("UNSUPPORTED_PDF", "The original file is larger than the 20 MB limit.", retryable=False)
    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 — PyMuPDF raises several types for bad files
        raise _unreadable() from exc
    if document.needs_pass or document.is_encrypted:
        document.close()
        raise ExportError(
            "ENCRYPTED_PDF",
            "The original PDF is password protected, so it cannot be redacted.",
            retryable=False,
        )
    if document.page_count < 1:
        document.close()
        raise ExportError("UNSUPPORTED_PDF", "The original PDF has no pages.", retryable=False)
    return document


def _reopen(document: pymupdf.Document) -> pymupdf.Document:
    data = document.tobytes(**_SAVE_OPTIONS)
    document.close()
    return pymupdf.open(stream=data, filetype="pdf")


def _boxes_by_page(boxes: Iterable[RedactionBox], page_count: int) -> dict[int, list[RedactionBox]]:
    grouped: dict[int, list[RedactionBox]] = {}
    for box in boxes:
        if not 1 <= box.page_number <= page_count:
            raise ExportError(
                "PAGE_MISMATCH",
                "A redaction points at a page the PDF does not have, so nothing was exported.",
                retryable=False,
            )
        grouped.setdefault(box.page_number, []).append(box)
    return grouped


def _apply_existing_redactions(document: pymupdf.Document) -> None:
    for page in document:
        if any(True for _ in page.annots(types=(pymupdf.PDF_ANNOT_REDACT,))):
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                text=pymupdf.PDF_REDACT_TEXT_REMOVE,
            )


def _apply_boxes(document: pymupdf.Document, grouped: dict[int, list[RedactionBox]]) -> int:
    applied = 0
    for page_number, page_boxes in grouped.items():
        page = document[page_number - 1]
        for box in page_boxes:
            page.add_redact_annot(page_rect(page, box.rect), fill=BOX_FILL, cross_out=False)
            applied += 1
        # Vector paths are removed only when fully covered. Removing every path a box
        # touches would also delete table rules and page backgrounds that cross it.
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
            graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )
    return applied


def _remove_invisible_text(document: pymupdf.Document) -> None:
    """Drop text nobody can see, so a hidden copy of a value cannot outlive its box."""
    for page in document:
        page.add_redact_annot(page.rect * page.derotation_matrix, fill=False, cross_out=False)
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE_INVISIBLE,
        )


def _scrub(document: pymupdf.Document) -> None:
    document.scrub(
        attached_files=True,
        clean_pages=True,
        embedded_files=True,
        hidden_text=False,
        javascript=True,
        metadata=True,
        redactions=False,
        remove_links=True,
        reset_fields=True,
        reset_responses=True,
        thumbnails=True,
        xml_metadata=True,
    )
    document.set_toc([])


# Writing direction of `insert_textbox(rotate=...)` in unrotated page space.
_TEXTBOX_DIRECTION = {
    0: pymupdf.Point(1, 0),
    90: pymupdf.Point(0, -1),
    180: pymupdf.Point(-1, 0),
    270: pymupdf.Point(0, 1),
}


def _label_rotation(page: pymupdf.Page, target: pymupdf.Rect) -> int:
    """Run the label along the box's long side, like the text it replaces.

    Of the two directions along that side, pick the one that reads left to right
    on screen, or bottom to top when the box is vertical on screen.
    """
    candidates = (0, 180) if target.width >= target.height else (90, 270)
    spin = pymupdf.Matrix(page.rotation_matrix)
    spin.e = spin.f = 0

    def readability(rotate: int) -> tuple[float, float]:
        shown = _TEXTBOX_DIRECTION[rotate] * spin
        return round(shown.x, 6), -round(shown.y, 6)

    return max(candidates, key=readability)


def _draw_labels(clean: bytes, boxes: Sequence[RedactionBox]) -> tuple[bytes, int]:
    """White type label centered on each box. Boxes too small for 4 pt text stay unlabeled."""
    document = pymupdf.open(stream=clean, filetype="pdf")
    drawn = 0
    try:
        for box in boxes:
            page = document[box.page_number - 1]
            target = page_rect(page, box.rect)
            rotate = _label_rotation(page, target)
            size = min(MAX_LABEL_FONT_PT, min(target.width, target.height) * 0.7)
            while size >= MIN_LABEL_FONT_PT:
                # A negative return means the text did not fit and nothing was written.
                fitted = page.insert_textbox(
                    target,
                    box.label,
                    fontsize=size,
                    fontname=LABEL_FONT,
                    color=LABEL_COLOR,
                    align=pymupdf.TEXT_ALIGN_CENTER,
                    rotate=rotate,
                )
                if fitted >= 0:
                    drawn += 1
                    break
                size -= 1.0
        return document.tobytes(**_SAVE_OPTIONS), drawn
    finally:
        document.close()


def redact_pdf(pdf_bytes: bytes, boxes: Sequence[RedactionBox], *, include_labels: bool) -> RedactedPdf:
    """Return the redacted, scrubbed PDF. Raises `ExportError` for files that cannot be processed."""
    document = open_pdf(pdf_bytes)
    try:
        page_count = document.page_count
        grouped = _boxes_by_page(boxes, page_count)
        _apply_existing_redactions(document)
        document.bake(annots=True, widgets=True)
        applied = _apply_boxes(document, grouped)
        _remove_invisible_text(document)
        # Garbage collection first: `scrub` refuses files with free xref entries.
        document = _reopen(document)
        _scrub(document)
        clean = document.tobytes(**_SAVE_OPTIONS)
    except ExportError:
        raise
    except Exception as exc:  # noqa: BLE001 — a damaged file can fail anywhere inside MuPDF
        raise _rewrite_failed() from exc
    finally:
        if not document.is_closed:
            document.close()

    final, labels_drawn = (clean, 0)
    if include_labels and boxes:
        try:
            final, labels_drawn = _draw_labels(clean, boxes)
        except Exception as exc:  # noqa: BLE001
            raise _rewrite_failed() from exc
    return RedactedPdf(clean=clean, final=final, page_count=page_count, boxes_applied=applied, labels_drawn=labels_drawn)


def _rewrite_failed() -> ExportError:
    return ExportError("REDACTION_FAILED", "The PDF could not be rewritten.", retryable=False)
