"""Custom rules: what they catch, and that labels stay outside the span."""

import pytest

from services.worker.app.detection.rules import run_rules


def _hits(text: str) -> list[tuple[str, str]]:
    return sorted((hit.entity_type, text[hit.start : hit.end]) for hit in run_rules(text))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("linkedin.com/in/jane-doe", ("SOCIAL_PROFILE_URL", "linkedin.com/in/jane-doe")),
        ("https://www.linkedin.com/in/janedoe/", ("SOCIAL_PROFILE_URL", "https://www.linkedin.com/in/janedoe/")),
        ("see github.com/janedoe for code", ("SOCIAL_PROFILE_URL", "github.com/janedoe")),
        ("Student ID: S1234567", ("STUDENT_ID", "S1234567")),
        ("MRN 00451288", ("MEDICAL_RECORD_NUMBER", "00451288")),
        ("Medical Record Number: AB-77120", ("MEDICAL_RECORD_NUMBER", "AB-77120")),
        ("Member ID: XGH448812", ("POLICY_NUMBER", "XGH448812")),
        ("Policy No. 44-8812-AC", ("POLICY_NUMBER", "44-8812-AC")),
        ("Class of 2019", ("GRADUATION_YEAR", "2019")),
        ("Graduated May 2021", ("GRADUATION_YEAR", "2021")),
        ("DOB: 04/12/1988", ("DATE_OF_BIRTH", "04/12/1988")),
        ("Date of Birth March 3, 1990", ("DATE_OF_BIRTH", "March 3, 1990")),
    ],
)
def test_rule_captures_only_the_value(text: str, expected: tuple[str, str]) -> None:
    assert expected in _hits(text)


def test_address_across_a_line_break() -> None:
    text = "Jane Doe\n123 Main Street\nSpringfield, IL 62704\nClass of 2019"
    assert ("ADDRESS", "123 Main Street\nSpringfield, IL 62704") in _hits(text)


def test_address_on_one_line_with_unit() -> None:
    text = "Ship to 42 W Elm Ave, Apt 3B, Chicago, IL 60601-1234 today"
    assert ("ADDRESS", "42 W Elm Ave, Apt 3B, Chicago, IL 60601-1234") in _hits(text)


def test_us_phone_formats() -> None:
    hits = _hits("Call (212) 555-0199 or 212.555.0100 or +1 212-555-0111")
    phones = [value for kind, value in hits if kind == "PHONE"]
    assert phones == sorted(["(212) 555-0199", "212.555.0100", "+1 212-555-0111"])


@pytest.mark.parametrize(
    "text",
    [
        "Student ID: pending",  # no digit in the value
        "SSN 123-45-6789",  # 3-2-4 is not a phone
        "Order 2125550199",  # no separators, not a formatted phone
        "Revenue grew 2019 to 2020",  # year without a graduation label
        "Room 12 Main Hall",  # no street suffix and no city line
    ],
)
def test_rules_do_not_fire_on_lookalikes(text: str) -> None:
    kinds = {kind for kind, _ in _hits(text)}
    assert kinds.isdisjoint({"STUDENT_ID", "PHONE", "GRADUATION_YEAR", "ADDRESS"})


def test_long_input_is_handled_quickly() -> None:
    # A bounded pattern set stays linear on a pathological run of digits and spaces.
    text = ("1 " * 20000) + "Street"
    run_rules(text)
