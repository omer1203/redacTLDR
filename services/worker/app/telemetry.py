import os

from celery.signals import task_prerun, task_postrun
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_tracer = trace.get_tracer("redactldr-worker")


def setup_worker_telemetry() -> None:
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    service_name = os.environ.get("OTEL_SERVICE_NAME", "redactldr-worker")
    if not endpoint:
        return

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)


@task_prerun.connect
def _task_prerun_handler(task_id=None, task=None, **kwargs):  # noqa: ANN001
    span = _tracer.start_span(name=f"celery.{task.name}")
    span.set_attribute("celery.task_id", task_id)
    kwargs["_otel_span"] = span


@task_postrun.connect
def _task_postrun_handler(task=None, retval=None, state=None, **kwargs):  # noqa: ANN001
    span = kwargs.get("_otel_span")
    if not span:
        return
    span.set_attribute("celery.state", str(state))
    span.end()
