from enum import StrEnum


class DocumentMode(StrEnum):
    RESUME_ANONYMIZATION = "resume_anonymization"
    EMPLOYMENT_PAPERWORK_REVIEW = "employment_paperwork_review"
    MEDICAL_PAPERWORK_SAFE_SHARING = "medical_paperwork_safe_sharing"
    LEGAL_CONTRACT_REVIEW = "legal_contract_review"
    TERMS_AND_CONDITIONS_SUMMARIZATION = "terms_and_conditions_summarization"


class DocumentStatus(StrEnum):
    CREATED = "CREATED"
    UPLOADED = "UPLOADED"
    DETECT_QUEUED = "DETECT_QUEUED"
    DETECTED = "DETECTED"
    EXPORT_QUEUED = "EXPORT_QUEUED"
    EXPORTED = "EXPORTED"
    SUMMARY_QUEUED = "SUMMARY_QUEUED"
    SUMMARIZED = "SUMMARIZED"
    FAILED = "FAILED"
