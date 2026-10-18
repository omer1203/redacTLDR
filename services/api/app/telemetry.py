import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_telemetry(app) -> None:
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    service_name = os.environ.get("OTEL_SERVICE_NAME", "redactldr-api")
    if not endpoint:
        return

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    try:
        from opentelemetry.instrumentation.botocore import BotocoreInstrumentor

        BotocoreInstrumentor().instrument()
    except Exception:  # noqa: BLE001
        # Presigned S3 calls still work. Spans for them need this package.
        pass
