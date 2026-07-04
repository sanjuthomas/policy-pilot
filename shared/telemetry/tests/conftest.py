from __future__ import annotations

from typing import Generator

import pytest
from opentelemetry.sdk._logs.export import ConsoleLogExporter
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture(autouse=True)
def in_memory_otel_exporters(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Avoid blocking OTLP network calls during unit tests."""
    span_exporter = InMemorySpanExporter()

    monkeypatch.setattr(
        "telemetry.exporters.build_log_exporter",
        lambda _settings: ConsoleLogExporter(),
    )
    monkeypatch.setattr(
        "telemetry.exporters.build_metric_exporter",
        lambda _settings: ConsoleMetricExporter(),
    )
    monkeypatch.setattr(
        "telemetry.exporters.build_trace_exporter",
        lambda _settings: span_exporter,
    )
    yield
