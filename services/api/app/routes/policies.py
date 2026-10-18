"""Redaction policy contract for the UI (R3).

The payload comes from `services.shared.policy`, the same tables the worker
applies, so the labels and defaults shown match what detection stored.
Like `/v1/documents/modes/schema`, this is static product config with no
user data, so it does not require auth.
"""

from typing import Any

from fastapi import APIRouter

from services.shared.policy import policies_payload

router = APIRouter(prefix="/v1/policies", tags=["policies"])


@router.get("/modes")
def list_mode_policies() -> dict[str, Any]:
    return policies_payload()
