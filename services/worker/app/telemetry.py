import os

from celery.signals import task_postrun, task_prerun
from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from services.shared.trace_context import start_consumer_span

# task id -> (span, context token). Celery does not pass prerun kwargs to postrun.
_inflight: dict[str, tuple] = {}


def setup_worker_telemetry() -> None:
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    service_name = os.environ.get("OTEL_SERVICE_NAME", "redactldr-worker")
    if not endpoint:
        return

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)
    try:
        from opentelemetry.instrumentation.botocore import BotocoreInstrumentor

        BotocoreInstrumentor().instrument()
    except Exception:  # noqa: BLE001
        # AWS spans are optional. A missing package must not stop the worker.
        pass


def _task_headers(task) -> dict:
    request = getattr(task, "request", None)
    headers = getattr(request, "headers", None) if request is not None else None
    return dict(headers or {})


@task_prerun.connect
def _task_prerun_handler(task_id=None, task=None, **kwargs):  # noqa: ANN001
    span, token = start_consumer_span(f"celery.{task.name}", _task_headers(task))
    span.set_attribute("celery.task_id", task_id or "")
    _inflight[task_id] = (span, token)


@task_postrun.connect
def _task_postrun_handler(task_id=None, state=None, **kwargs):  # noqa: ANN001
    pair = _inflight.pop(task_id, None)
    if not pair:
        return
    span, token = pair
    span.set_attribute("celery.state", str(state))
    span.end()
    otel_context.detach(token)
