"""Turn one OCR page into a single string plus the offset of every word.

Layout: words on a line are joined with one space, lines are joined with "\n".
Words come from the OCR `words` list, not the Textract `LINE.Text`, because the
words carry the boxes. Lines with no non-empty words are skipped.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from services.worker.app.detection.models import PageText, WordSpan

# Bump if the layout above changes; stored offsets are only valid for one version.
PAGE_TEXT_VERSION = 1


def build_page_text(page: Mapping[str, Any]) -> PageText:
    parts: list[str] = []
    words: list[WordSpan] = []
    cursor = 0
    emitted_lines = 0

    for line_index, line in enumerate(page.get("lines") or []):
        tokens = [(str(word.get("text") or "").strip(), word) for word in line.get("words") or []]
        tokens = [(token, word) for token, word in tokens if token]
        if not tokens:
            continue
        if emitted_lines:
            parts.append("\n")
            cursor += 1
        emitted_lines += 1
        for position, (token, word) in enumerate(tokens):
            if position:
                parts.append(" ")
                cursor += 1
            parts.append(token)
            words.append(
                WordSpan(
                    start=cursor,
                    end=cursor + len(token),
                    line_index=line_index,
                    bbox=dict(word.get("bbox") or {}),
                )
            )
            cursor += len(token)

    return PageText(page_number=int(page.get("pageNumber") or 1), text="".join(parts), words=tuple(words))
