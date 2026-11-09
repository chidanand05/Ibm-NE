"""OpenTelemetry tracing setup."""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def init_tracing() -> None:
    """Initialize OpenTelemetry SDK with OTLP gRPC exporter (Jaeger)."""
    service_name = os.environ.get("OTEL_SERVICE_NAME", "namma-exodus-backend")
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    # Export spans to Jaeger via OTLP gRPC
    try:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except Exception:
        # If Jaeger is unreachable at startup, continue without tracing
        pass

    trace.set_tracer_provider(provider)

    # Auto-instrument SQLAlchemy queries
    SQLAlchemyInstrumentor().instrument()


def get_tracer(name: str = "namma-exodus") -> trace.Tracer:
    """Return a named tracer. Use in agent and API code."""
    return trace.get_tracer(name)
