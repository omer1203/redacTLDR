"""Pattern rules for values Comprehend misses or that a mode needs by name.

Label-anchored rules (student ID, MRN, policy number, date of birth, graduation
year) capture only the value after the label, so the label stays readable.
Email and US phone duplicate Comprehend on purpose: OCR text sometimes breaks
Comprehend's context, and the merge step removes the overlap.

Every pattern is bounded (no nested unbounded repeats) so a hostile PDF cannot
cause catastrophic backtracking.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from services.worker.app.detection.models import Candidate

_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
# An identifier value: 4–20 chars, letters/digits/dashes, at least one digit.
_ID_VALUE = r"((?=[A-Za-z0-9-]*\d)[A-Za-z0-9][A-Za-z0-9-]{3,19})\b"
_STREET_SUFFIX = (
    r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place"
    r"|Ter|Terrace|Pkwy|Parkway|Hwy|Highway|Cir|Circle|Sq|Square)"
)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    entity_type: str
    pattern: re.Pattern[str]
    confidence: float
    # 0 = the whole match; otherwise only this capture group is the sensitive value.
    group: int = 0


RULES: tuple[Rule, ...] = (
    Rule(
        "social_profile_url",
        "SOCIAL_PROFILE_URL",
        re.compile(r"\b(?:https?://)?(?:www\.)?(?:linkedin\.com/in|github\.com)/[A-Za-z0-9_-]{1,100}/?", re.IGNORECASE),
        0.97,
    ),
    Rule(
        "email",
        "EMAIL",
        re.compile(r"\b[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,255}\.[A-Za-z]{2,24}\b"),
        0.95,
    ),
    Rule(
        "us_phone",
        "PHONE",
        re.compile(r"(?<![\w-])(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]\d{4}(?![\w-])"),
        0.85,
    ),
    Rule(
        "date_of_birth",
        "DATE_OF_BIRTH",
        re.compile(
            r"\b(?:DOB|D\.O\.B\.?|date\s+of\s+birth|birth\s*date)\s*[:#]?\s*"
            r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2}|" + _MONTH + r"\s+\d{1,2},?\s+\d{4})",
            re.IGNORECASE,
        ),
        0.95,
        group=1,
    ),
    Rule(
        "student_id",
        "STUDENT_ID",
        re.compile(r"\bstudent\s*(?:id|number|no\.?|#)\s*[:#]?\s*" + _ID_VALUE, re.IGNORECASE),
        0.90,
        group=1,
    ),
    Rule(
        "medical_record_number",
        "MEDICAL_RECORD_NUMBER",
        re.compile(r"\b(?:MRN|medical\s+record\s*(?:number|no\.?|#)?)\s*[:#]?\s*" + _ID_VALUE, re.IGNORECASE),
        0.92,
        group=1,
    ),
    Rule(
        "policy_number",
        "POLICY_NUMBER",
        re.compile(
            r"\b(?:policy|member|subscriber|group|insurance)\s*(?:id|number|no\.?|#)\s*[:#]?\s*" + _ID_VALUE,
            re.IGNORECASE,
        ),
        0.90,
        group=1,
    ),
    Rule(
        "graduation_year",
        "GRADUATION_YEAR",
        re.compile(
            r"\b(?:class\s+of|graduat(?:ed|ion|ing))\s*(?:in|date|year)?\s*[:,]?\s*(?:" + _MONTH + r"\s+)?((?:19|20)\d{2})\b",
            re.IGNORECASE,
        ),
        0.80,
        group=1,
    ),
    # US street line followed by "City, ST 12345", on one line (comma) or across a line break.
    Rule(
        "us_address",
        "ADDRESS",
        re.compile(
            r"(?<!\w)\d{1,6}[ ]+(?:[A-Za-z0-9.'#-]{1,30}[ ]+){0,5}" + _STREET_SUFFIX + r"\.?"
            r"(?:,?[ ]+(?:Apt|Apartment|Suite|Ste|Unit|#)\.?[ ]*[A-Za-z0-9-]{1,10})?"
            r"[ ]*(?:,[ ]*\n?|\n)[ ]*[A-Za-z][A-Za-z .'-]{1,40},[ ]*[A-Z]{2}[ ]+\d{5}(?:-\d{4})?\b"
        ),
        0.90,
    ),
)


def run_rules(text: str, rules: Iterable[Rule] = RULES) -> list[Candidate]:
    candidates: list[Candidate] = []
    for rule in rules:
        for match in rule.pattern.finditer(text):
            start, end = match.span(rule.group)
            if start < 0 or end <= start:
                continue
            candidates.append(
                Candidate(
                    start=start,
                    end=end,
                    entity_type=rule.entity_type,
                    confidence=rule.confidence,
                    source="rule",
                    rule_id=rule.rule_id,
                )
            )
    return candidates
