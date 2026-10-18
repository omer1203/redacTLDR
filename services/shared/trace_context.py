"""Carry one trace from the API request into the Celery task that finishes it."""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.trace import SpanKind

_tracer = trace.get_tracer("redactldr.trace")


def inject_trace_headers() -> dict[str, str]:
    """W3C `traceparent` (and baggage) for the current span, if one is recording."""
    carrier: dict[str, str] = {}
    inject(carrier)
    return carrier


def start_consumer_span(name: str, headers: dict | None):
    """Child span of whatever trace the producer put on the task headers.

    Returns `(span, context_token)`. The caller ends the span and detaches the
    token. Headers without a traceparent start a new trace.
    """
    from opentelemetry import context

    parent = extract(headers or {})
    span = _tracer.start_span(name, context=parent, kind=SpanKind.CONSUMER)
    token = context.attach(trace.set_span_in_context(span))
    return span, token
