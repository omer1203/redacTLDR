"""Turn page text into one validated summary. The model is injected so tests never call Bedrock.

Documents longer than `CHUNK_PAGES` are summarized in pieces, then those pieces
are merged. The merge sees only the partial summaries, never the original pages,
so a value that was tokenized stays tokenized. After every call the output is
checked against the values safe mode removed; a repeat fails the summary and
nothing is stored.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from services.shared.summary_contract import CHUNK_PAGES, SCHEMA_VERSION
from services.worker.app.redaction.matching import compact, occurrences
from services.worker.app.summary.errors import SummaryError
from services.worker.app.summary.schemas import MODELS
from services.worker.app.summary.source import PageSource

_SYSTEM = (
    "You summarize one document for its reviewer. Use only the text you are given. "
    "Sensitive values may already be replaced by tokens such as [EMAIL] or [NAME]. "
    "Never guess what a token stands for, and never invent an email, phone number, "
    "address, or identifier. Every concrete claim needs a citation with the page "
    "number and a short quote copied from that page. Leave a field empty when the "
    "pages do not support it."
)


class TokenUse:
    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0

    def add(self, other: "TokenUse") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.calls += other.calls


@dataclass(frozen=True)
class ModelResult:
    data: dict
    input_tokens: int
    output_tokens: int


class Summarizer(Protocol):
    def complete(self, mode: str, system: str, user: str) -> ModelResult: ...


@dataclass(frozen=True)
class GeneratedSummary:
    payload: dict
    input_tokens: int
    output_tokens: int
    calls: int
    truncated: bool
    pages_used: int


def _reject_leaks(text: str, forbidden: Sequence[str]) -> None:
    folded = compact(text)
    for value in forbidden:
        needle = compact(value)
        if needle and len(occurrences(folded, needle)) > 0:
            raise SummaryError(
                "OUTPUT_LEAK",
                "The summary repeated a redacted value, so it was not saved. You can try again.",
                retryable=False,
            )


def _parse(mode: str, data: dict) -> dict:
    model = MODELS.get(mode)
    if model is None:
        raise SummaryError("UNKNOWN_MODE", "This document's mode has no summary format.", retryable=False)
    try:
        return model.model_validate(data).model_dump()
    except ValidationError as exc:
        raise SummaryError(
            "OUTPUT_INVALID",
            "The summary did not match the expected format, so it was not saved. You can try again.",
            retryable=False,
        ) from exc


def _chunk_prompt(pages: Sequence[PageSource], *, mode: str, part: int, parts: int) -> str:
    blocks = [f"--- page {page.page_number} ---\n{page.text}" for page in pages]
    return (
        f"Document mode: {mode}. This is part {part} of {parts}. "
        "Summarize only these pages.\n\n" + "\n\n".join(blocks)
    )


def generate_summary(
    *,
    mode: str,
    pages: Sequence[PageSource],
    forbidden: Sequence[str],
    model: Summarizer,
    max_pages: int,
) -> GeneratedSummary:
    if mode not in MODELS:
        raise SummaryError("UNKNOWN_MODE", "This document's mode has no summary format.", retryable=False)
    if not pages:
        raise SummaryError("OCR_MISSING", "The document has no extracted text to summarize.", retryable=False)

    truncated = len(pages) > max_pages
    used = list(pages[:max_pages])
    chunks = [used[index : index + CHUNK_PAGES] for index in range(0, len(used), CHUNK_PAGES)]
    usage = TokenUse()
    partials: list[dict] = []
    for number, chunk in enumerate(chunks, start=1):
        prompt = _chunk_prompt(chunk, mode=mode, part=number, parts=len(chunks))
        _reject_leaks(prompt, forbidden)
        result = model.complete(mode, _SYSTEM, prompt)
        parsed = _parse(mode, result.data)
        _reject_leaks(json.dumps(parsed), forbidden)
        partials.append(parsed)
        usage.input_tokens += result.input_tokens
        usage.output_tokens += result.output_tokens
        usage.calls += 1

    if len(partials) == 1:
        body = partials[0]
    else:
        merge = (
            "Merge these partial summaries of one document into a single summary. "
            "Drop duplicates, keep the citations, and do not add anything the partials do not say.\n\n"
            + json.dumps(partials)
        )
        _reject_leaks(merge, forbidden)
        result = model.complete(mode, _SYSTEM, merge)
        body = _parse(mode, result.data)
        _reject_leaks(json.dumps(body), forbidden)
        usage.input_tokens += result.input_tokens
        usage.output_tokens += result.output_tokens
        usage.calls += 1

    return GeneratedSummary(
        payload=body,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        calls=usage.calls,
        truncated=truncated,
        pages_used=len(used),
    )


def envelope(*, mode: str, safe_mode: bool, generated: GeneratedSummary) -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": mode,
        "safeMode": safe_mode,
        "truncated": generated.truncated,
        "pagesUsed": generated.pages_used,
        "summary": generated.payload,
    }
