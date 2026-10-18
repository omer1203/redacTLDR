"""One Pydantic model per document mode. Field names match `services.shared.summary_contract`.

Every concrete claim is a `CitedItem`: the text plus the page and a short quote copied
from that page. Quotes come from the prompt, so in safe mode they contain tokens
like ``[EMAIL]`` rather than the value.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from services.shared.summary_contract import MODE_SUMMARY_FIELDS


class Citation(BaseModel):
    page: int = Field(ge=1)
    quoteSnippet: str = ""


class CitedItem(BaseModel):
    text: str = ""
    citations: list[Citation] = []


class ResumeSummary(BaseModel):
    skills: list[str] = []
    experienceSummary: str = ""
    yearsExperience: str | None = None
    roles: list[CitedItem] = []
    education: list[CitedItem] = []
    highlights: list[CitedItem] = []
    citations: list[Citation] = []
    confidence: float = Field(default=0, ge=0, le=1)


class EmploymentSummary(BaseModel):
    compensation: list[CitedItem] = []
    startDate: str | None = None
    deadlines: list[CitedItem] = []
    benefits: list[CitedItem] = []
    obligations: list[CitedItem] = []
    restrictions: list[CitedItem] = []
    risks: list[CitedItem] = []
    citations: list[Citation] = []
    confidence: float = Field(default=0, ge=0, le=1)


class MedicalSummary(BaseModel):
    visitSummary: str = ""
    instructions: list[CitedItem] = []
    medications: list[CitedItem] = []
    followUps: list[CitedItem] = []
    whatToShare: list[CitedItem] = []
    billing: list[CitedItem] = []
    importantDates: list[CitedItem] = []
    citations: list[Citation] = []
    confidence: float = Field(default=0, ge=0, le=1)


class LegalSummary(BaseModel):
    parties: list[str] = []
    term: str | None = None
    payment: str | None = None
    obligations: list[CitedItem] = []
    fees: list[CitedItem] = []
    penalties: list[CitedItem] = []
    termination: list[CitedItem] = []
    renewal: list[CitedItem] = []
    liabilities: list[CitedItem] = []
    riskyClauses: list[CitedItem] = []
    citations: list[Citation] = []
    confidence: float = Field(default=0, ge=0, le=1)


class TermsSummary(BaseModel):
    dataCollected: list[CitedItem] = []
    dataSharing: list[CitedItem] = []
    cancellation: list[CitedItem] = []
    refunds: list[CitedItem] = []
    autoRenewal: list[CitedItem] = []
    dataUse: list[CitedItem] = []
    liability: list[CitedItem] = []
    gotchas: list[CitedItem] = []
    citations: list[Citation] = []
    confidence: float = Field(default=0, ge=0, le=1)


MODELS: dict[str, type[BaseModel]] = {
    "resume_anonymization": ResumeSummary,
    "employment_paperwork_review": EmploymentSummary,
    "medical_paperwork_safe_sharing": MedicalSummary,
    "legal_contract_review": LegalSummary,
    "terms_and_conditions_summarization": TermsSummary,
}


def assert_models_match_contract() -> None:
    """The shared field list and these models are the same contract. Called by tests."""
    for mode, model in MODELS.items():
        if tuple(model.model_fields) != MODE_SUMMARY_FIELDS[mode]:
            raise AssertionError(f"{mode} fields drifted from the shared contract")
