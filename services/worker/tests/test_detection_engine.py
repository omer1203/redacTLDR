"""End-to-end detection on a synthetic resume page with a recorded Comprehend response."""

import json
import logging
from pathlib import Path

import pytest

from services.shared.policy import UnknownModeError
from services.worker.app.detection.engine import detect_document
from services.worker.app.detection.models import Candidate
from services.worker.app.detection.page_text import build_page_text

FIXTURE = Path(__file__).parent / "fixtures" / "comprehend_resume_page.json"


class RecordedComprehend:
    """Replays the fixture for the resume page; returns nothing for other text."""

    def __init__(self, expected_text: str) -> None:
        self._expected_text = expected_text
        self.calls = 0

    def detect(self, text: str) -> list[Candidate]:
        self.calls += 1
        if text != self._expected_text:
            return []
        entities = json.loads(FIXTURE.read_text())["Entities"]
        return [
            Candidate(e["BeginOffset"], e["EndOffset"], e["Type"], e["Score"], "comprehend") for e in entities
        ]


@pytest.fixture
def resume_payload(resume_page):
    return {"version": 1, "pageCount": 1, "pages": [resume_page]}


@pytest.fixture
def detector(resume_page):
    return RecordedComprehend(build_page_text(resume_page).text)


def _by_type(result):
    return {finding.entity_type: finding for finding in result.findings}


def test_fixture_offsets_match_the_page_text(resume_page) -> None:
    text = build_page_text(resume_page).text
    entities = {e["Type"]: text[e["BeginOffset"] : e["EndOffset"]] for e in json.loads(FIXTURE.read_text())["Entities"]}
    assert entities["NAME"] == "Jane Doe"
    assert entities["EMAIL"] == "jane.doe@gmail.com"
    assert entities["PHONE"] == "(212) 555-0199"
    assert entities["ADDRESS"] == "123 Main Street\nSpringfield, IL 62704"


def test_resume_mode_finds_contact_details_with_boxes(resume_payload, detector) -> None:
    result = detect_document(resume_payload, mode="resume_anonymization", safe_mode=False, pii_detector=detector)
    found = _by_type(result)

    for entity_type in ("NAME", "EMAIL", "PHONE", "ADDRESS", "SOCIAL_PROFILE_URL"):
        assert found[entity_type].accepted is True
        assert found[entity_type].policy_action == "auto"

    # Comprehend URL and the social-profile rule overlap; the specific type remains.
    assert "URL" not in found
    assert found["SOCIAL_PROFILE_URL"].masked_text == "linkedin.com/in/j***"
    assert found["ADDRESS"].rects and len(found["ADDRESS"].rects) == 2
    assert found["EMAIL"].rects[0] == pytest.approx({"x": 0.1, "y": 0.13, "width": 0.18, "height": 0.02})
    assert found["EMAIL"].masked_text == "j***@g***.com"
    assert found["EMAIL"].block_ref == "p1:l1"

    # Comprehend DATE_TIME and the graduation rule cover "2019"; both are suggestions here.
    year = next(f for f in result.findings if f.char_start == build_page_text(resume_payload["pages"][0]).text.index("2019"))
    assert year.entity_type == "GRADUATION_YEAR"
    assert year.accepted is False
    assert detector.calls == 1


def test_each_mode_accepts_a_different_set(resume_payload, resume_page) -> None:
    accepted = {}
    for mode in (
        "resume_anonymization",
        "employment_paperwork_review",
        "medical_paperwork_safe_sharing",
        "legal_contract_review",
        "terms_and_conditions_summarization",
    ):
        result = detect_document(
            resume_payload,
            mode=mode,
            safe_mode=False,
            pii_detector=RecordedComprehend(build_page_text(resume_page).text),
        )
        accepted[mode] = frozenset(f.entity_type for f in result.findings if f.accepted)
    assert accepted["resume_anonymization"] != accepted["legal_contract_review"]
    assert "SOCIAL_PROFILE_URL" in accepted["resume_anonymization"]
    assert "SOCIAL_PROFILE_URL" not in accepted["employment_paperwork_review"]
    assert "NAME" not in accepted["legal_contract_review"]
    assert accepted["terms_and_conditions_summarization"] == frozenset()


def test_safe_mode_accepts_suggestions(resume_payload, detector) -> None:
    result = detect_document(resume_payload, mode="resume_anonymization", safe_mode=True, pii_detector=detector)
    assert all(finding.accepted for finding in result.findings)


def test_findings_and_logs_do_not_expose_raw_values(resume_payload, detector, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    result = detect_document(resume_payload, mode="resume_anonymization", safe_mode=False, pii_detector=detector)
    logging.getLogger("test").info("summary %s findings %s", result.summary(), list(result.findings))
    for raw in ("jane.doe@gmail.com", "Jane Doe", "555-0199"):
        assert raw not in caplog.text
        assert all(raw not in finding.masked_text for finding in result.findings)
    assert result.summary()["total"] == len(result.findings)


def test_empty_pages_skip_the_detector(make_ocr_page) -> None:
    calls = []

    class Spy:
        def detect(self, text):
            calls.append(text)
            return []

    payload = {"pages": [{"pageNumber": 1, "lines": []}, make_ocr_page([""], page_number=2)]}
    result = detect_document(payload, mode="resume_anonymization", safe_mode=False, pii_detector=Spy())
    assert result.findings == ()
    assert calls == []
    assert result.pages_scanned == 2


def test_out_of_range_offsets_are_ignored(make_ocr_page) -> None:
    class Broken:
        def detect(self, text):
            return [Candidate(0, len(text) + 50, "NAME", 0.99, "comprehend")]

    payload = {"pages": [make_ocr_page(["Jane Doe"])]}
    result = detect_document(payload, mode="resume_anonymization", safe_mode=False, pii_detector=Broken())
    assert result.findings == ()


def test_unknown_mode_fails_before_any_detector_call(resume_payload) -> None:
    class MustNotRun:
        def detect(self, text):
            raise AssertionError("detector called")

    with pytest.raises(UnknownModeError):
        detect_document(resume_payload, mode="nope", safe_mode=False, pii_detector=MustNotRun())
