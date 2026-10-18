"""JSON logs for production, with the trace and the document on every line.

Local dev leaves the default text formatter in place. Set LOG_JSON=true on
the ECS tasks. The redaction filter still runs first.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar

from opentelemetry import trace

from services.shared.log_redact import redact_text

_document_id: ContextVar[str] = ContextVar("log_document_id", default="")
_job_id: ContextVar[str] = ContextVar("log_job_id", default="")


def bind_ids() -> tuple[str, str]:
    return _document_id.get(), _job_id.get()


@contextmanager
def bind_log_context(*, document_id: str = "", job_id: str = ""):
    document_token = _document_id.set(document_id or "")
    job_token = _job_id.set(job_id or "")
    try:
        yield
    finally:
        _document_id.reset(document_token)
        _job_id.reset(job_token)


def current_trace_id() -> str:
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx is None or not ctx.trace_id:
        return ""
    return format(ctx.trace_id, "032x")


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        document_id, job_id = bind_ids()
        payload = {
            "level": record.levelname,
            "message": redact_text(record.getMessage()),
            "logger": record.name,
            "trace_id": current_trace_id(),
            "document_id": document_id,
            "job_id": job_id,
        }
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def install_json_logs() -> None:
    """Replace the root handler format when LOG_JSON is on. Idempotent."""
    if os.environ.get("LOG_JSON", "").lower() not in {"1", "true", "yes"}:
        return
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    for handler in root.handlers:
        handler.setFormatter(JsonLogFormatter())
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
