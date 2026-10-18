"""Shared builders for detection tests. All text here is synthetic."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import pytest

CHAR_WIDTH = 0.01
LINE_HEIGHT = 0.03
WORD_HEIGHT = 0.02
LEFT = 0.1
TOP = 0.1


def build_ocr_page(lines: Sequence[str], page_number: int = 1) -> dict[str, Any]:
    """An OCR page in the R2 JSON shape, with one box per word laid out by character position."""
    page_lines = []
    for line_index, line in enumerate(lines):
        y = round(TOP + line_index * LINE_HEIGHT, 6)
        words = []
        column = 0
        for token in line.split(" "):
            if token:
                words.append(
                    {
                        "text": token,
                        "bbox": {
                            "x": round(LEFT + column * CHAR_WIDTH, 6),
                            "y": y,
                            "width": round(len(token) * CHAR_WIDTH, 6),
                            "height": WORD_HEIGHT,
                        },
                    }
                )
            column += len(token) + 1
        page_lines.append(
            {
                "text": line,
                "bbox": {"x": LEFT, "y": y, "width": round(len(line) * CHAR_WIDTH, 6), "height": WORD_HEIGHT},
                "words": words,
            }
        )
    return {"pageNumber": page_number, "width": 612.0, "height": 792.0, "hasTextLayer": True, "lines": page_lines}


@pytest.fixture
def make_ocr_page() -> Callable[..., dict[str, Any]]:
    return build_ocr_page


RESUME_LINES = (
    "Jane Doe",
    "jane.doe@gmail.com | (212) 555-0199",
    "linkedin.com/in/janedoe",
    "123 Main Street",
    "Springfield, IL 62704",
    "Class of 2019",
)


@pytest.fixture
def resume_page() -> dict[str, Any]:
    return build_ocr_page(RESUME_LINES)
