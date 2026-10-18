"""Merge and dedupe, and masked display values."""

import pytest

from services.shared.policy import PolicyAction, PolicyDecision
from services.worker.app.detection.masking import mask_value
from services.worker.app.detection.merge import Scored, merge_overlapping
from services.worker.app.detection.models import Candidate

AUTO = PolicyDecision(PolicyAction.AUTO, True, 0.8)
SUGGESTED = PolicyDecision(PolicyAction.SUGGESTED, False, 0.8)


def _scored(start: int, end: int, kind: str, confidence: float, decision: PolicyDecision = AUTO) -> Scored:
    return Scored(Candidate(start, end, kind, confidence, "comprehend"), decision)


def test_identical_spans_collapse_to_the_higher_confidence() -> None:
    merged = merge_overlapping([_scored(0, 10, "EMAIL", 0.95), _scored(0, 10, "EMAIL", 0.99)])
    assert len(merged) == 1
    assert merged[0].winner.candidate.confidence == 0.99


def test_overlap_keeps_the_union_range() -> None:
    merged = merge_overlapping([_scored(0, 15, "ADDRESS", 0.99), _scored(10, 30, "ADDRESS", 0.9)])
    assert [(item.start, item.end) for item in merged] == [(0, 30)]


def test_auto_beats_a_higher_scoring_suggestion() -> None:
    merged = merge_overlapping(
        [_scored(5, 15, "DATE_TIME", 0.99, SUGGESTED), _scored(5, 15, "DATE_OF_BIRTH", 0.95, AUTO)]
    )
    assert merged[0].winner.candidate.entity_type == "DATE_OF_BIRTH"


def test_specific_type_beats_generic_when_both_redact() -> None:
    merged = merge_overlapping([_scored(0, 14, "DATE_TIME", 1.0), _scored(0, 14, "DATE_OF_BIRTH", 0.95)])
    assert merged[0].winner.candidate.entity_type == "DATE_OF_BIRTH"


def test_redaction_still_beats_specificity() -> None:
    merged = merge_overlapping(
        [_scored(0, 4, "DATE_TIME", 0.9, AUTO), _scored(0, 4, "GRADUATION_YEAR", 0.8, SUGGESTED)]
    )
    assert merged[0].winner.candidate.entity_type == "DATE_TIME"


def test_touching_spans_stay_separate() -> None:
    merged = merge_overlapping([_scored(0, 5, "NAME", 0.9), _scored(5, 9, "PHONE", 0.9)])
    assert len(merged) == 2


def test_transitive_overlap_forms_one_cluster() -> None:
    merged = merge_overlapping([_scored(0, 5, "A", 0.9), _scored(4, 9, "A", 0.9), _scored(8, 12, "A", 0.9)])
    assert [(item.start, item.end) for item in merged] == [(0, 12)]


@pytest.mark.parametrize(
    ("kind", "raw", "masked"),
    [
        ("EMAIL", "jane.doe@gmail.com", "j***@g***.com"),
        ("PHONE", "(212) 555-0199", "(***) ***-**99"),
        ("SSN", "123-45-6789", "***-**-**89"),
        ("NAME", "Jane Doe", "J*** D***"),
        ("ADDRESS", "123 Main Street\nSpringfield, IL", "*** M*** S*** S*** I***"),
        ("DATE_TIME", "January 6, 2025", "J*** ** ***"),
        ("SOCIAL_PROFILE_URL", "linkedin.com/in/janedoe", "linkedin.com/in/j***"),
        ("URL", "https://janedoe.dev/about", "https://j***.dev/a***"),
        ("GRADUATION_YEAR", "2019", "**19"),
        ("NAME", "A", "*"),
    ],
)
def test_mask_value(kind: str, raw: str, masked: str) -> None:
    assert mask_value(kind, raw) == masked


def test_mask_never_contains_the_raw_value() -> None:
    for kind, raw in [("EMAIL", "jane.doe@gmail.com"), ("NAME", "Jane Doe"), ("PHONE", "212-555-0199")]:
        assert raw not in mask_value(kind, raw)
