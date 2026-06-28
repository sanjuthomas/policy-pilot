from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class TelemetrySettings:
    enabled: bool
    service_name: str
    service_version: str
    environment: str
    log_level: str
    log_console: bool
    otlp_endpoint: str
    otlp_protocol: str
    otlp_insecure: bool
    metrics_export_interval_ms: int
    excluded_urls: str

    @classmethod
    def from_env(
        cls,
        *,
        service_name: str,
        service_version: str = "0.1.0",
    ) -> TelemetrySettings:
        disabled = _env_bool("OTEL_SDK_DISABLED", default=False)
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317").strip()
        protocol = os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc").strip().lower()
        if protocol in {"http", "http/protobuf", "http_protobuf"}:
            protocol = "http/protobuf"

        return cls(
            enabled=not disabled,
            service_name=service_name,
            service_version=service_version,
            environment=os.environ.get("OTEL_DEPLOYMENT_ENVIRONMENT", "development"),
            log_level=os.environ.get("OTEL_LOG_LEVEL", "INFO").upper(),
            log_console=_env_bool("OTEL_LOG_CONSOLE", default=True),
            otlp_endpoint=endpoint,
            otlp_protocol=protocol,
            otlp_insecure=_env_bool("OTEL_EXPORTER_OTLP_INSECURE", default=True),
            metrics_export_interval_ms=_env_int("OTEL_METRIC_EXPORT_INTERVAL", 15000),
            excluded_urls=os.environ.get(
                "OTEL_PYTHON_FASTAPI_EXCLUDED_URLS",
                "/health,/metrics",
            ),
        )
