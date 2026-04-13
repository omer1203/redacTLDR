from services.api.app.enums import DocumentMode
from services.api.app.services.summary_schema import mode_summary_template
from services.api.app.services.validation import validate_summary_json


def test_mode_templates_contain_required_keys() -> None:
    template = mode_summary_template(DocumentMode.LEGAL_CONTRACT_REVIEW)
    is_valid, missing = validate_summary_json(DocumentMode.LEGAL_CONTRACT_REVIEW, template)
    assert is_valid
    assert missing == []


def test_validation_detects_missing_keys() -> None:
    payload = {"citations": [], "confidence": {}}
    is_valid, missing = validate_summary_json(DocumentMode.RESUME_ANONYMIZATION, payload)
    assert not is_valid
    assert "skills" in missing
