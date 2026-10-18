"""Builders for the R5 export tests. Every value here is synthetic.

`ocr_payload_for` stands in for Textract: it reads the PDF's own words with
small glyph heights (ink-tight boxes, like Textract) and stores them in the
R2 OCR JSON shape, normalized to the displayed page.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from typing import Any

import pikepdf
import pymupdf

from services.worker.app.detection.boxes import rects_for_span
from services.worker.app.detection.page_text import build_page_text


def make_pdf(pages: Sequence[Sequence[str]], *, rotation: int = 0, fontsize: float = 11, render_mode: int = 0) -> bytes:
    """One page per entry, one text line per string, Helvetica, 24 pt line pitch."""
    document = pymupdf.open()
    for lines in pages:
        page = document.new_page(width=612, height=792)
        for index, line in enumerate(lines):
            page.insert_text((72, 100 + index * 24), line, fontsize=fontsize, render_mode=render_mode)
        page.set_rotation(rotation)
    return document.tobytes()


def make_scanned_pdf(lines: Sequence[str], dpi: int = 150) -> bytes:
    """Render text to an image and put only the image on a page: no text layer, like a scan."""
    source = pymupdf.open(stream=make_pdf([lines]), filetype="pdf")
    pixmap = source[0].get_pixmap(dpi=dpi)
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.insert_image(page.rect, pixmap=pixmap)
    return document.tobytes()


def _normalized(rect: pymupdf.Rect, page: pymupdf.Page) -> dict[str, float]:
    shown = rect * page.rotation_matrix
    shown.normalize()
    bounds = page.rect
    return {
        "x": round(shown.x0 / bounds.width, 6),
        "y": round(shown.y0 / bounds.height, 6),
        "width": round(shown.width / bounds.width, 6),
        "height": round(shown.height / bounds.height, 6),
    }


def ocr_payload_for(pdf_bytes: bytes, *, words_from: bytes | None = None) -> dict[str, Any]:
    """OCR JSON for `pdf_bytes`. `words_from` reads words from another file (the digital twin of a scan)."""
    target = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    source = pymupdf.open(stream=words_from or pdf_bytes, filetype="pdf")
    pages = []
    pymupdf.TOOLS.set_small_glyph_heights(True)
    try:
        for page, word_page in zip(target, source, strict=True):
            lines: dict[tuple[int, int], list[dict[str, Any]]] = {}
            for x0, y0, x1, y1, word, block, line, _ in word_page.get_text("words"):
                box = _normalized(pymupdf.Rect(x0, y0, x1, y1), word_page)
                lines.setdefault((block, line), []).append({"text": word, "bbox": box})
            page_lines = [
                {"text": " ".join(w["text"] for w in words), "bbox": words[0]["bbox"], "words": words}
                for words in lines.values()
            ]
            pages.append(
                {
                    "pageNumber": page.number + 1,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "hasTextLayer": bool(page.get_text().strip()),
                    "wordCount": sum(len(line["words"]) for line in page_lines),
                    "lines": page_lines,
                }
            )
    finally:
        pymupdf.TOOLS.set_small_glyph_heights(False)
    return {"version": 1, "pageCount": len(pages), "pages": pages}


def detection_row(payload: dict[str, Any], value: str, *, page_number: int = 1, entity_type: str = "EMAIL") -> dict[str, Any]:
    """A `detections` row for `value`, with offsets and line rects the way R3 stores them."""
    page_text = build_page_text(payload["pages"][page_number - 1])
    start = page_text.text.index(value)
    end = start + len(value)
    return {
        "entity_type": entity_type,
        "page_number": page_number,
        "rects": rects_for_span(page_text, start, end),
        "bbox": {},
        "char_start": start,
        "char_end": end,
    }


def extracted_text(pdf_bytes: bytes) -> str:
    document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    return "\n".join(page.get_text("text") for page in document)


def raw_contains(pdf_bytes: bytes, value: str) -> bool:
    """Search the fully decompressed file bytes, independent of PyMuPDF's text extraction.

    Base-14 fonts write text as literal or hex strings, so both forms are checked.
    """
    buffer = io.BytesIO()
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        pdf.save(buffer, compress_streams=False, stream_decode_level=pikepdf.StreamDecodeLevel.all)
    data = buffer.getvalue()
    encoded = value.encode("latin-1")
    return encoded in data or encoded.hex().encode() in data.lower()
