from typing import Any

from services.api.app.enums import DocumentMode
from services.shared.summary_contract import empty_summary


def mode_summary_template(mode: DocumentMode) -> dict[str, Any]:
    """Empty summary body for `mode`. Keys are the contract in `services.shared.summary_contract`."""
    return empty_summary(mode.value)
