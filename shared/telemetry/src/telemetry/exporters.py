from __future__ import annotations

from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter as GrpcLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
    OTLPMetricExporter as GrpcMetricExporter,
)
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter as HttpLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter as HttpMetricExporter,
)
from opentelemetry.sdk._logs.export import LogExporter
from opentelemetry.sdk.metrics.export import MetricExporter

from telemetry.config import TelemetrySettings


def _grpc_endpoint(endpoint: str) -> str:
    return endpoint.replace("http://", "").replace("https://", "")


def build_log_exporter(settings: TelemetrySettings) -> LogExporter:
    if settings.otlp_protocol == "http/protobuf":
        return HttpLogExporter(
            endpoint=f"{settings.otlp_endpoint.rstrip('/')}/v1/logs",
            insecure=settings.otlp_insecure,
        )
    return GrpcLogExporter(
        endpoint=_grpc_endpoint(settings.otlp_endpoint),
        insecure=settings.otlp_insecure,
    )


def build_metric_exporter(settings: TelemetrySettings) -> MetricExporter:
    if settings.otlp_protocol == "http/protobuf":
        return HttpMetricExporter(
            endpoint=f"{settings.otlp_endpoint.rstrip('/')}/v1/metrics",
            insecure=settings.otlp_insecure,
        )
    return GrpcMetricExporter(
        endpoint=_grpc_endpoint(settings.otlp_endpoint),
        insecure=settings.otlp_insecure,
    )
