from services.api.app.enums import DocumentMode
from services.api.app.services.summary_schema import mode_summary_template


def validate_summary_json(mode: DocumentMode, payload: dict) -> tuple[bool, list[str]]:
    required_keys = set(mode_summary_template(mode).keys())
    actual_keys = set(payload.keys())
    missing = sorted(required_keys - actual_keys)
    return (len(missing) == 0, missing)
