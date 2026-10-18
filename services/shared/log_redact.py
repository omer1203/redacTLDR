"""Drop emails, phone numbers, and SSNs from log lines before they are written."""

from __future__ import annotations

import logging
import re

_EMAIL = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE = re.compile(r"\b(?:\+?1[\s.\-]?)?(?:\(\d{3}\)|\d{3})[\s.\-]?\d{3}[\s.\-]?\d{4}\b")


def redact_text(value: str) -> str:
    value = _EMAIL.sub("[email]", value)
    value = _SSN.sub("[ssn]", value)
    return _PHONE.sub("[phone]", value)


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            record.args = tuple(redact_text(arg) if isinstance(arg, str) else arg for arg in record.args)
        return True


def install_redacting_logs() -> None:
    """Attach the filter once to the root logger."""
    root = logging.getLogger()
    if any(isinstance(item, RedactFilter) for item in root.filters):
        return
    root.addFilter(RedactFilter())
