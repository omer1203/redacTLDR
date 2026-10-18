"""Normalized boxes → PyMuPDF rectangles.

PyMuPDF has two coordinate spaces per page:
- `page.rect` is the page as displayed: cropbox size, rotation applied, origin
  at the top-left of the cropbox. Normalized boxes are fractions of this.
- Annotations and text extraction use the unrotated page.
`page.derotation_matrix` maps the first to the second. Both spaces are relative
to the cropbox, so a cropbox offset needs no extra handling. All four rotations,
with and without a cropbox offset, were checked against a rendered page.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pymupdf

from services.worker.app.redaction.models import Box

# Grows every box on each side before it is applied. Textract boxes hug the ink,
# and anti-aliased edges on scans sit just outside them. 1 pt clipped no word on
# a neighboring line on the sample PDFs; redaction removes any glyph the box touches.
EDGE_PADDING_PT = 1.0


def clamp_bbox(bbox: Mapping[str, Any]) -> dict[str, float]:
    """Clamp a normalized box so it stays inside the page.

    Input/output coordinates are expected in [0, 1] relative page space.
    """
    x = max(0.0, min(1.0, float(bbox.get("x", 0.0))))
    y = max(0.0, min(1.0, float(bbox.get("y", 0.0))))
    width = max(0.0, min(1.0 - x, float(bbox.get("width", 0.0))))
    height = max(0.0, min(1.0 - y, float(bbox.get("height", 0.0))))
    return {"x": x, "y": y, "width": width, "height": height}


def usable_box(raw: Any) -> Box | None:
    """A clamped box, or None when `raw` is not a box with a real area.

    Callers decide what None means. For a selected redaction it is an error,
    because skipping it would leave the value in the file.
    """
    if not isinstance(raw, Mapping):
        return None
    try:
        values = [float(raw[key]) for key in ("x", "y", "width", "height")]
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in values):
        return None
    box = clamp_bbox(dict(zip(("x", "y", "width", "height"), values)))
    if box["width"] <= 0 or box["height"] <= 0:
        return None
    return box


def displayed_rect(page: pymupdf.Page, box: Box, padding: float = EDGE_PADDING_PT) -> pymupdf.Rect:
    """The box in displayed page points, padded and kept inside the page."""
    bounds = page.rect
    rect = pymupdf.Rect(
        bounds.x0 + box["x"] * bounds.width - padding,
        bounds.y0 + box["y"] * bounds.height - padding,
        bounds.x0 + (box["x"] + box["width"]) * bounds.width + padding,
        bounds.y0 + (box["y"] + box["height"]) * bounds.height + padding,
    )
    return rect & bounds


def page_rect(page: pymupdf.Page, box: Box, padding: float = EDGE_PADDING_PT) -> pymupdf.Rect:
    """The box in unrotated page points: the space `add_redact_annot` and `get_text` use."""
    rect = displayed_rect(page, box, padding) * page.derotation_matrix
    rect.normalize()
    return rect


def boxes_intersect(a: Box, b: Box) -> bool:
    """Normalized boxes overlap with a positive area."""
    return (
        a["x"] < b["x"] + b["width"]
        and b["x"] < a["x"] + a["width"]
        and a["y"] < b["y"] + b["height"]
        and b["y"] < a["y"] + a["height"]
    )


def center_inside(inner: Box, outer: Box) -> bool:
    cx = inner["x"] + inner["width"] / 2
    cy = inner["y"] + inner["height"] / 2
    return outer["x"] <= cx <= outer["x"] + outer["width"] and outer["y"] <= cy <= outer["y"] + outer["height"]
