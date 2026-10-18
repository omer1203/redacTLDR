"""Field names for each mode's summary. The worker's models and the API schema both use this.

A stored summary is ``{"schemaVersion", "mode", "safeMode", "truncated", "pagesUsed", "summary"}``
and ``summary`` has exactly the keys listed for that mode. Bump ``SCHEMA_VERSION`` when a key
changes meaning; adding a key is still version 1 until a caller depends on the old set.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

# Pages per model call. Longer documents are summarized in chunks and then merged.
CHUNK_PAGES = 6

MODE_SUMMARY_FIELDS: dict[str, tuple[str, ...]] = {
    "resume_anonymization": (
        "skills",
        "experienceSummary",
        "yearsExperience",
        "roles",
        "education",
        "highlights",
        "citations",
        "confidence",
    ),
    "employment_paperwork_review": (
        "compensation",
        "startDate",
        "deadlines",
        "benefits",
        "obligations",
        "restrictions",
        "risks",
        "citations",
        "confidence",
    ),
    "medical_paperwork_safe_sharing": (
        "visitSummary",
        "instructions",
        "medications",
        "followUps",
        "whatToShare",
        "billing",
        "importantDates",
        "citations",
        "confidence",
    ),
    "legal_contract_review": (
        "parties",
        "term",
        "payment",
        "obligations",
        "fees",
        "penalties",
        "termination",
        "renewal",
        "liabilities",
        "riskyClauses",
        "citations",
        "confidence",
    ),
    "terms_and_conditions_summarization": (
        "dataCollected",
        "dataSharing",
        "cancellation",
        "refunds",
        "autoRenewal",
        "dataUse",
        "liability",
        "gotchas",
        "citations",
        "confidence",
    ),
}

# Scalar fields. Everything else in MODE_SUMMARY_FIELDS is a list.
SCALAR_FIELDS = {
    "experienceSummary": "",
    "yearsExperience": None,
    "startDate": None,
    "visitSummary": "",
    "term": None,
    "payment": None,
    "confidence": 0,
}


def empty_summary(mode: str) -> dict:
    """A valid, empty summary object for `mode`. Unknown modes raise KeyError."""
    body = {}
    for key in MODE_SUMMARY_FIELDS[mode]:
        body[key] = SCALAR_FIELDS[key] if key in SCALAR_FIELDS else []
    return body
