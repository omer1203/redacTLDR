import json
import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from services.shared.log_json import JsonLogFormatter, bind_log_context
from services.worker.app.metrics import publish_queue_depth, stage_timer
from services.shared.trace_context import inject_trace_headers, start_consumer_span


def test_task_headers_continue_the_api_trace():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    previous = trace.get_tracer_provider()
    trace.set_tracer_provider(provider)
    try:
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("api.request"):
            headers = inject_trace_headers()
        assert "traceparent" in headers

        span, token = start_consumer_span("celery.process_document", headers)
        span.end()
        from opentelemetry import context

        context.detach(token)
        finished = exporter.get_finished_spans()
        worker = next(item for item in finished if item.name == "celery.process_document")
        parent = next(item for item in finished if item.name == "api.request")
        assert worker.context.trace_id == parent.context.trace_id
        assert worker.parent.span_id == parent.context.span_id
    finally:
        trace.set_tracer_provider(previous)


def test_json_log_carries_trace_document_and_job():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    previous = trace.get_tracer_provider()
    trace.set_tracer_provider(provider)
    try:
        record = logging.LogRecord("redactldr", logging.INFO, __file__, 1, "stored document_id=%s", ("doc-1",), None)
        with bind_log_context(document_id="doc-1", job_id="job-9"):
            with trace.get_tracer("test").start_as_current_span("work"):
                line = JsonLogFormatter().format(record)
        payload = json.loads(line)
        assert payload["document_id"] == "doc-1"
        assert payload["job_id"] == "job-9"
        assert len(payload["trace_id"]) == 32
        assert payload["message"] == "stored document_id=doc-1"
    finally:
        trace.set_tracer_provider(previous)


def test_queue_metric_is_skipped_without_a_namespace(monkeypatch):
    monkeypatch.delenv("CLOUDWATCH_METRICS_NAMESPACE", raising=False)
    assert publish_queue_depth() == {"ok": True, "skipped": True}


def test_stage_timer_does_not_call_cloudwatch_without_a_namespace(monkeypatch):
    monkeypatch.delenv("CLOUDWATCH_METRICS_NAMESPACE", raising=False)
    with stage_timer("ocr"):
        pass
