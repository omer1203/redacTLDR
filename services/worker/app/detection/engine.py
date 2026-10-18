"""Detection for one OCR document: text → hits → policy → merge → boxes.

Per page:
1. Build the page text and word offsets (`page_text`).
2. Collect hits from Comprehend and the custom rules.
3. Apply the mode policy; ignored or low-confidence hits are dropped.
4. Merge overlapping hits (`merge`).
5. Map each span to one rectangle per OCR line (`boxes`) and mask the value.

No I/O happens here apart from the injected `PiiDetector`, so the whole
path is testable with a fake detector.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from services.shared.policy import decide, get_mode_policy
from services.worker.app.detection.boxes import rects_for_span, union_boxes, words_in_span
from services.worker.app.detection.comprehend import PiiDetector
from services.worker.app.detection.masking import mask_value
from services.worker.app.detection.merge import Scored, merge_overlapping
from services.worker.app.detection.models import Candidate, Finding, PageText
from services.worker.app.detection.page_text import build_page_text
from services.worker.app.detection.rules import run_rules


@dataclass(frozen=True)
class DetectionResult:
    findings: tuple[Finding, ...]
    pages_scanned: int
    candidates_seen: int

    def summary(self) -> dict[str, Any]:
        """Counts only, safe for job results and logs."""
        return {
            "total": len(self.findings),
            "accepted": sum(1 for finding in self.findings if finding.accepted),
            "byType": dict(sorted(Counter(finding.entity_type for finding in self.findings).items())),
            "pagesScanned": self.pages_scanned,
            "candidatesSeen": self.candidates_seen,
        }


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    """Drop whitespace at the span edges so boxes do not reach into the next line."""
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _in_bounds(candidate: Candidate, length: int) -> bool:
    return 0 <= candidate.start < candidate.end <= length


def detect_page(
    page: Mapping[str, Any],
    *,
    mode: str,
    safe_mode: bool,
    pii_detector: PiiDetector,
) -> tuple[list[Finding], int]:
    """Return `(findings, candidates_seen)` for one OCR page."""
    page_text: PageText = build_page_text(page)
    text = page_text.text
    if not text.strip():
        return [], 0

    candidates = [c for c in pii_detector.detect(text) + run_rules(text) if _in_bounds(c, len(text))]
    scored = [
        Scored(candidate, decision)
        for candidate in candidates
        if (decision := decide(mode, safe_mode, candidate.entity_type, candidate.confidence)) is not None
    ]

    findings: list[Finding] = []
    for merged in merge_overlapping(scored):
        start, end = _trim(text, merged.start, merged.end)
        if end <= start:
            continue
        rects = rects_for_span(page_text, start, end)
        if not rects:
            continue
        envelope = union_boxes(rects) or rects[0]
        first_word = words_in_span(page_text, start, end)[0]
        winner = merged.winner
        raw = text[start:end]
        findings.append(
            Finding(
                page_number=page_text.page_number,
                entity_type=winner.candidate.entity_type,
                confidence=round(winner.candidate.confidence, 4),
                source=winner.candidate.source,
                rule_id=winner.candidate.rule_id,
                char_start=start,
                char_end=end,
                rects=tuple(rects),
                bbox=envelope,
                block_ref=f"p{page_text.page_number}:l{first_word.line_index}",
                masked_text=mask_value(winner.candidate.entity_type, raw),
                policy_action=winner.decision.action.value,
                accepted=winner.decision.accepted,
                raw_text=raw,
            )
        )
    return findings, len(candidates)


def detect_document(
    ocr_payload: Mapping[str, Any],
    *,
    mode: str,
    safe_mode: bool,
    pii_detector: PiiDetector,
) -> DetectionResult:
    # Fail on an unknown mode before paying for any Comprehend call.
    get_mode_policy(mode)
    findings: list[Finding] = []
    candidates_seen = 0
    pages = ocr_payload.get("pages") or []
    for page in pages:
        page_findings, seen = detect_page(page, mode=mode, safe_mode=safe_mode, pii_detector=pii_detector)
        findings.extend(page_findings)
        candidates_seen += seen
    findings.sort(key=lambda finding: (finding.page_number, finding.char_start))
    return DetectionResult(findings=tuple(findings), pages_scanned=len(pages), candidates_seen=candidates_seen)
