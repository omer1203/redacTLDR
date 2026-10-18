"""Redaction policy per document mode (R3).

The worker calls `decide` for every detected entity. The API serves
`policies_payload` so the UI shows the same labels, colors, and defaults.
Both read the tables below, so they cannot drift apart.

Actions:
- AUTO: redacted by default (`accepted=True`).
- SUGGESTED: shown to the reviewer but off by default (`accepted=False`).
- IGNORE: not stored for this mode.

Safe mode lowers every confidence cutoff and turns SUGGESTED into AUTO.
IGNORE stays IGNORE, because those types are not sensitive in that mode.

Mode ids are plain strings that must match `services.api.app.enums.DocumentMode`.
This module does not import the API so the worker can use it without FastAPI.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

POLICY_VERSION = 1

DEFAULT_MIN_CONFIDENCE = 0.80
# Comprehend NAME and DATE_TIME have the most false positives in OCR text.
MIN_CONFIDENCE_BY_TYPE: Mapping[str, float] = {
    "NAME": 0.85,
    "DATE_TIME": 0.85,
    "GRADUATION_YEAR": 0.75,
}
SAFE_MODE_CONFIDENCE_DROP = 0.20
SAFE_MODE_CONFIDENCE_FLOOR = 0.50


class PolicyAction(StrEnum):
    AUTO = "auto"
    SUGGESTED = "suggested"
    IGNORE = "ignore"


class UnknownModeError(ValueError):
    """Raised for a mode id with no policy. Failing is safer than guessing a mode."""


@dataclass(frozen=True)
class EntityTypeInfo:
    label: str
    color: str
    description: str


@dataclass(frozen=True)
class PolicyDecision:
    """Outcome for one entity that survived the policy. IGNORE never reaches here."""

    action: PolicyAction
    accepted: bool
    min_confidence: float


@dataclass(frozen=True)
class ModePolicy:
    mode: str
    label: str
    description: str
    rules: Mapping[str, PolicyAction]

    def action_for(self, entity_type: str) -> PolicyAction:
        # High-risk identifiers are redacted in every mode, whatever the table says.
        if entity_type in HIGH_RISK_TYPES:
            return PolicyAction.AUTO
        # Unlisted types are shown, not dropped, so a new Comprehend type is never silently lost.
        return self.rules.get(entity_type, PolicyAction.SUGGESTED)


_IDENTITY = "#2563eb"
_CONTACT = "#0891b2"
_LOCATION = "#7c3aed"
_ONLINE = "#0d9488"
_DATES = "#ca8a04"
_GOVERNMENT = "#dc2626"
_FINANCIAL = "#ea580c"
_CREDENTIAL = "#be123c"
_MEDICAL = "#db2777"
_EDUCATION = "#4f46e5"

# Comprehend `DetectPiiEntities` types plus the custom rule types in
# `services/worker/app/detection/rules.py`.
ENTITY_TYPES: Mapping[str, EntityTypeInfo] = {
    "NAME": EntityTypeInfo("Name", _IDENTITY, "A person's name."),
    "AGE": EntityTypeInfo("Age", _IDENTITY, "A person's age."),
    "DATE_OF_BIRTH": EntityTypeInfo("Date of birth", _IDENTITY, "A date labeled as a birth date."),
    "EMAIL": EntityTypeInfo("Email", _CONTACT, "An email address."),
    "PHONE": EntityTypeInfo("Phone", _CONTACT, "A phone or fax number."),
    "ADDRESS": EntityTypeInfo("Address", _LOCATION, "A street or mailing address."),
    "URL": EntityTypeInfo("Link", _ONLINE, "A web address."),
    "SOCIAL_PROFILE_URL": EntityTypeInfo("Profile link", _ONLINE, "A LinkedIn or GitHub profile link."),
    "USERNAME": EntityTypeInfo("Username", _ONLINE, "An account user name."),
    "IP_ADDRESS": EntityTypeInfo("IP address", _ONLINE, "An IPv4 or IPv6 address."),
    "MAC_ADDRESS": EntityTypeInfo("MAC address", _ONLINE, "A network hardware address."),
    "DATE_TIME": EntityTypeInfo("Date", _DATES, "A date or time."),
    "GRADUATION_YEAR": EntityTypeInfo("Graduation year", _EDUCATION, "A graduation year, which can reveal age."),
    "STUDENT_ID": EntityTypeInfo("Student ID", _EDUCATION, "A labeled student number."),
    "MEDICAL_RECORD_NUMBER": EntityTypeInfo("Medical record number", _MEDICAL, "A labeled MRN."),
    "POLICY_NUMBER": EntityTypeInfo("Policy / member number", _MEDICAL, "An insurance policy, member, or group number."),
    "SSN": EntityTypeInfo("Social Security number", _GOVERNMENT, "A US Social Security number."),
    "PASSPORT_NUMBER": EntityTypeInfo("Passport number", _GOVERNMENT, "A passport number."),
    "DRIVER_ID": EntityTypeInfo("Driver's license", _GOVERNMENT, "A driver's license number."),
    "US_INDIVIDUAL_TAX_IDENTIFICATION_NUMBER": EntityTypeInfo("ITIN", _GOVERNMENT, "A US tax ID."),
    "UK_NATIONAL_INSURANCE_NUMBER": EntityTypeInfo("UK NI number", _GOVERNMENT, "A UK National Insurance number."),
    "UK_UNIQUE_TAXPAYER_REFERENCE_NUMBER": EntityTypeInfo("UK UTR", _GOVERNMENT, "A UK taxpayer reference."),
    "UK_NATIONAL_HEALTH_SERVICE_NUMBER": EntityTypeInfo("NHS number", _MEDICAL, "A UK NHS number."),
    "CA_SOCIAL_INSURANCE_NUMBER": EntityTypeInfo("Canadian SIN", _GOVERNMENT, "A Canadian Social Insurance number."),
    "CA_HEALTH_NUMBER": EntityTypeInfo("Canadian health number", _MEDICAL, "A Canadian health card number."),
    "IN_AADHAAR": EntityTypeInfo("Aadhaar", _GOVERNMENT, "An Indian Aadhaar number."),
    "IN_PERMANENT_ACCOUNT_NUMBER": EntityTypeInfo("PAN", _GOVERNMENT, "An Indian PAN."),
    "IN_VOTER_NUMBER": EntityTypeInfo("Voter ID", _GOVERNMENT, "An Indian voter ID."),
    "IN_NREGA": EntityTypeInfo("NREGA number", _GOVERNMENT, "An Indian NREGA number."),
    "LICENSE_PLATE": EntityTypeInfo("License plate", _GOVERNMENT, "A vehicle license plate."),
    "VEHICLE_IDENTIFICATION_NUMBER": EntityTypeInfo("VIN", _GOVERNMENT, "A vehicle identification number."),
    "BANK_ACCOUNT_NUMBER": EntityTypeInfo("Bank account", _FINANCIAL, "A bank account number."),
    "BANK_ROUTING": EntityTypeInfo("Routing number", _FINANCIAL, "A bank routing number."),
    "INTERNATIONAL_BANK_ACCOUNT_NUMBER": EntityTypeInfo("IBAN", _FINANCIAL, "An international bank account number."),
    "SWIFT_CODE": EntityTypeInfo("SWIFT code", _FINANCIAL, "A bank SWIFT/BIC code."),
    "CREDIT_DEBIT_NUMBER": EntityTypeInfo("Card number", _FINANCIAL, "A credit or debit card number."),
    "CREDIT_DEBIT_CVV": EntityTypeInfo("Card CVV", _FINANCIAL, "A card security code."),
    "CREDIT_DEBIT_EXPIRY": EntityTypeInfo("Card expiry", _FINANCIAL, "A card expiration date."),
    "PIN": EntityTypeInfo("PIN", _CREDENTIAL, "A personal identification number."),
    "PASSWORD": EntityTypeInfo("Password", _CREDENTIAL, "A password."),
    "AWS_ACCESS_KEY": EntityTypeInfo("AWS access key", _CREDENTIAL, "An AWS access key id."),
    "AWS_SECRET_KEY": EntityTypeInfo("AWS secret key", _CREDENTIAL, "An AWS secret key."),
}

HIGH_RISK_TYPES: frozenset[str] = frozenset(
    {
        "SSN",
        "PASSPORT_NUMBER",
        "DRIVER_ID",
        "US_INDIVIDUAL_TAX_IDENTIFICATION_NUMBER",
        "UK_NATIONAL_INSURANCE_NUMBER",
        "UK_UNIQUE_TAXPAYER_REFERENCE_NUMBER",
        "UK_NATIONAL_HEALTH_SERVICE_NUMBER",
        "CA_SOCIAL_INSURANCE_NUMBER",
        "CA_HEALTH_NUMBER",
        "IN_AADHAAR",
        "IN_PERMANENT_ACCOUNT_NUMBER",
        "IN_VOTER_NUMBER",
        "IN_NREGA",
        "BANK_ACCOUNT_NUMBER",
        "BANK_ROUTING",
        "INTERNATIONAL_BANK_ACCOUNT_NUMBER",
        "SWIFT_CODE",
        "CREDIT_DEBIT_NUMBER",
        "CREDIT_DEBIT_CVV",
        "CREDIT_DEBIT_EXPIRY",
        "PIN",
        "PASSWORD",
        "AWS_ACCESS_KEY",
        "AWS_SECRET_KEY",
    }
)

_A = PolicyAction.AUTO
_S = PolicyAction.SUGGESTED
_I = PolicyAction.IGNORE

# Organization names are not in this table: Comprehend PII does not return them,
# and `DetectEntities` is outside the app's IAM policy. See the R3 status in the roadmap.
MODE_POLICIES: Mapping[str, ModePolicy] = {
    "resume_anonymization": ModePolicy(
        mode="resume_anonymization",
        label="Resume",
        description="Hide contact details and identity. Keep skills and experience readable.",
        rules={
            "NAME": _A,
            "EMAIL": _A,
            "PHONE": _A,
            "ADDRESS": _A,
            "URL": _A,
            "SOCIAL_PROFILE_URL": _A,
            "AGE": _A,
            "DATE_OF_BIRTH": _A,
            "USERNAME": _A,
            "IP_ADDRESS": _A,
            "STUDENT_ID": _A,
            "DATE_TIME": _S,
            "GRADUATION_YEAR": _S,
        },
    ),
    "employment_paperwork_review": ModePolicy(
        mode="employment_paperwork_review",
        label="Employment",
        description="Hide personal identifiers. Keep pay, dates, and deadlines readable.",
        rules={
            "NAME": _A,
            "EMAIL": _A,
            "PHONE": _A,
            "ADDRESS": _A,
            "AGE": _A,
            "DATE_OF_BIRTH": _A,
            "USERNAME": _A,
            "URL": _S,
            "SOCIAL_PROFILE_URL": _S,
            "STUDENT_ID": _S,
            "POLICY_NUMBER": _S,
            # Start dates and deadlines are what this mode exists to review.
            "DATE_TIME": _I,
            "GRADUATION_YEAR": _I,
        },
    ),
    "medical_paperwork_safe_sharing": ModePolicy(
        mode="medical_paperwork_safe_sharing",
        label="Medical",
        description="Hide patient identifiers so instructions can be shared.",
        rules={
            "NAME": _A,
            "EMAIL": _A,
            "PHONE": _A,
            "ADDRESS": _A,
            "AGE": _A,
            "DATE_OF_BIRTH": _A,
            "MEDICAL_RECORD_NUMBER": _A,
            "POLICY_NUMBER": _A,
            "USERNAME": _A,
            "IP_ADDRESS": _A,
            "DATE_TIME": _S,
            "URL": _S,
            "SOCIAL_PROFILE_URL": _S,
            "GRADUATION_YEAR": _I,
        },
    ),
    "legal_contract_review": ModePolicy(
        mode="legal_contract_review",
        label="Legal contract",
        description="Hide contact details. Party names and addresses are suggested, since a review often needs them.",
        rules={
            "EMAIL": _A,
            "PHONE": _A,
            "DATE_OF_BIRTH": _A,
            "POLICY_NUMBER": _A,
            "NAME": _S,
            "ADDRESS": _S,
            "AGE": _S,
            "URL": _S,
            "SOCIAL_PROFILE_URL": _S,
            # Effective dates and terms are the substance of a contract.
            "DATE_TIME": _I,
            "GRADUATION_YEAR": _I,
        },
    ),
    "terms_and_conditions_summarization": ModePolicy(
        mode="terms_and_conditions_summarization",
        label="Terms & conditions",
        description="Public terms rarely hold personal data. Only high-risk identifiers are redacted by default.",
        rules={
            "NAME": _S,
            "EMAIL": _S,
            "PHONE": _S,
            "ADDRESS": _S,
            "URL": _I,
            "SOCIAL_PROFILE_URL": _I,
            "DATE_TIME": _I,
            "GRADUATION_YEAR": _I,
            "AGE": _I,
        },
    ),
}


def get_mode_policy(mode: str) -> ModePolicy:
    try:
        return MODE_POLICIES[mode]
    except KeyError as exc:
        raise UnknownModeError(f"no redaction policy for mode {mode!r}") from exc


def min_confidence(entity_type: str, safe_mode: bool) -> float:
    base = MIN_CONFIDENCE_BY_TYPE.get(entity_type, DEFAULT_MIN_CONFIDENCE)
    if not safe_mode:
        return base
    return max(SAFE_MODE_CONFIDENCE_FLOOR, round(base - SAFE_MODE_CONFIDENCE_DROP, 4))


def decide(mode: str, safe_mode: bool, entity_type: str, confidence: float) -> PolicyDecision | None:
    """Return the decision for one entity, or `None` when it should not be stored."""
    action = get_mode_policy(mode).action_for(entity_type)
    if action is PolicyAction.IGNORE:
        return None
    threshold = min_confidence(entity_type, safe_mode)
    if confidence < threshold:
        return None
    if safe_mode:
        action = PolicyAction.AUTO
    return PolicyDecision(action=action, accepted=action is PolicyAction.AUTO, min_confidence=threshold)


# Type stored on boxes the reviewer draws by hand. It never comes from a detector,
# so it is not part of ENTITY_TYPES or any mode policy.
MANUAL_ENTITY_TYPE = "CUSTOM"
MANUAL_ENTITY_INFO = EntityTypeInfo("Manual redaction", "#475569", "A box drawn by the reviewer.")


def entity_type_info(entity_type: str) -> EntityTypeInfo:
    """Metadata for a type, with a readable fallback for types added later by Comprehend."""
    if entity_type == MANUAL_ENTITY_TYPE:
        return MANUAL_ENTITY_INFO
    info = ENTITY_TYPES.get(entity_type)
    if info:
        return info
    return EntityTypeInfo(entity_type.replace("_", " ").title(), "#64748b", "Sensitive information.")


def policies_payload() -> dict[str, Any]:
    """JSON body for `GET /v1/policies/modes`."""
    types = sorted(set(ENTITY_TYPES))
    return {
        "version": POLICY_VERSION,
        "safeMode": {
            "confidenceDrop": SAFE_MODE_CONFIDENCE_DROP,
            "confidenceFloor": SAFE_MODE_CONFIDENCE_FLOOR,
            "promotesSuggested": True,
        },
        "entityTypes": {
            name: {"label": info.label, "color": info.color, "description": info.description}
            for name, info in sorted(ENTITY_TYPES.items())
        },
        "modes": [
            {
                "id": policy.mode,
                "label": policy.label,
                "description": policy.description,
                "defaultAction": PolicyAction.SUGGESTED.value,
                "rules": [
                    {
                        "entityType": entity_type,
                        "action": policy.action_for(entity_type).value,
                        "minConfidence": min_confidence(entity_type, safe_mode=False),
                        "safeModeMinConfidence": min_confidence(entity_type, safe_mode=True),
                    }
                    for entity_type in types
                ],
            }
            for policy in MODE_POLICIES.values()
        ],
    }
