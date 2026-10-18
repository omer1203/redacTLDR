"""Mode policy: defaults per mode, safe mode, thresholds, and the API contract."""

import pytest

from services.api.app.enums import DocumentMode
from services.shared.policy import (
    HIGH_RISK_TYPES,
    MODE_POLICIES,
    PolicyAction,
    UnknownModeError,
    decide,
    min_confidence,
    policies_payload,
)

PROBE_TYPES = [
    "NAME",
    "EMAIL",
    "PHONE",
    "ADDRESS",
    "URL",
    "DATE_TIME",
    "GRADUATION_YEAR",
    "MEDICAL_RECORD_NUMBER",
    "POLICY_NUMBER",
    "SSN",
]


def _accepted(mode: str, safe_mode: bool = False) -> set[str]:
    accepted = set()
    for entity_type in PROBE_TYPES:
        decision = decide(mode, safe_mode, entity_type, 0.99)
        if decision and decision.accepted:
            accepted.add(entity_type)
    return accepted


def test_every_document_mode_has_a_policy() -> None:
    assert set(MODE_POLICIES) == {mode.value for mode in DocumentMode}


def test_each_mode_has_a_different_default_accepted_set() -> None:
    sets = {mode: frozenset(_accepted(mode)) for mode in MODE_POLICIES}
    assert len(set(sets.values())) == len(sets)
    assert sets["resume_anonymization"] >= {"NAME", "EMAIL", "PHONE", "ADDRESS", "URL"}
    assert "NAME" not in sets["legal_contract_review"]
    assert "EMAIL" not in sets["terms_and_conditions_summarization"]
    assert "MEDICAL_RECORD_NUMBER" in sets["medical_paperwork_safe_sharing"]
    assert "MEDICAL_RECORD_NUMBER" not in sets["employment_paperwork_review"]


def test_resume_suggests_dates_and_graduation_year() -> None:
    assert decide("resume_anonymization", False, "DATE_TIME", 0.99).action is PolicyAction.SUGGESTED
    assert decide("resume_anonymization", False, "GRADUATION_YEAR", 0.99).accepted is False


def test_ignored_types_are_dropped_even_in_safe_mode() -> None:
    assert decide("legal_contract_review", False, "DATE_TIME", 0.99) is None
    assert decide("legal_contract_review", True, "DATE_TIME", 0.99) is None


def test_safe_mode_promotes_suggestions_and_lowers_thresholds() -> None:
    assert decide("resume_anonymization", True, "DATE_TIME", 0.99).accepted is True
    assert decide("resume_anonymization", False, "NAME", 0.70) is None
    assert decide("resume_anonymization", True, "NAME", 0.70).accepted is True
    assert min_confidence("NAME", safe_mode=True) == pytest.approx(0.65)
    assert min_confidence("EMAIL", safe_mode=True) >= 0.5


@pytest.mark.parametrize("mode", list(MODE_POLICIES))
def test_high_risk_types_are_auto_in_every_mode(mode: str) -> None:
    for entity_type in HIGH_RISK_TYPES:
        assert decide(mode, False, entity_type, 0.99).accepted is True


def test_unknown_type_is_suggested_not_dropped() -> None:
    decision = decide("resume_anonymization", False, "SOME_NEW_TYPE", 0.99)
    assert decision is not None and decision.action is PolicyAction.SUGGESTED


def test_unknown_mode_raises() -> None:
    with pytest.raises(UnknownModeError):
        decide("not_a_mode", False, "NAME", 0.99)


def test_policies_payload_shape() -> None:
    payload = policies_payload()
    assert payload["version"] == 1
    assert {mode["id"] for mode in payload["modes"]} == set(MODE_POLICIES)
    resume = next(mode for mode in payload["modes"] if mode["id"] == "resume_anonymization")
    rules = {rule["entityType"]: rule for rule in resume["rules"]}
    assert rules["EMAIL"]["action"] == "auto"
    assert rules["DATE_TIME"]["action"] == "suggested"
    assert payload["entityTypes"]["EMAIL"]["label"] == "Email"
