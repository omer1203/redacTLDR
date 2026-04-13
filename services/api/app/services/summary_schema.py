from typing import Any

from services.api.app.enums import DocumentMode


def mode_summary_template(mode: DocumentMode) -> dict[str, Any]:
    if mode == DocumentMode.RESUME_ANONYMIZATION:
        return {
            "skills": [],
            "experienceSummary": "",
            "yearsExperience": None,
            "citations": [],
            "confidence": {},
        }
    if mode == DocumentMode.EMPLOYMENT_PAPERWORK_REVIEW:
        return {
            "compensation": [],
            "deadlines": [],
            "restrictions": [],
            "risks": [],
            "citations": [],
            "confidence": {},
        }
    if mode == DocumentMode.MEDICAL_PAPERWORK_SAFE_SHARING:
        return {
            "instructions": [],
            "followUps": [],
            "billing": [],
            "importantDates": [],
            "citations": [],
            "confidence": {},
        }
    if mode == DocumentMode.LEGAL_CONTRACT_REVIEW:
        return {
            "obligations": [],
            "fees": [],
            "penalties": [],
            "termination": [],
            "renewal": [],
            "riskyClauses": [],
            "citations": [],
            "confidence": {},
        }
    return {
        "cancellation": [],
        "refunds": [],
        "autoRenewal": [],
        "dataUse": [],
        "liability": [],
        "citations": [],
        "confidence": {},
    }
