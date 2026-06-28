from __future__ import annotations

import logging
from typing import Any

from opentelemetry._logs import set_logger_provider
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

from telemetry.config import TelemetrySettings
from telemetry.exporters import build_log_exporter, build_metric_exporter

_logger_provider: LoggerProvider | None = None
_meter_provider: MeterProvider | None = None
_logging_handler: LoggingHandler | None = None
_console_handler: logging.Handler | None = None
_settings: TelemetrySettings | None = None
_configured = False


def is_telemetry_enabled() -> bool:
    return _configured and _settings is not None and _settings.enabled


def _resource(settings: TelemetrySettings) -> Resource:
    return Resource.create(
        {
            ResourceAttributes.SERVICE_NAME: settings.service_name,
            ResourceAttributes.SERVICE_VERSION: settings.service_version,
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: settings.environment,
        }
    )


def configure_telemetry(
    service_name: str,
    *,
    service_version: str = "0.1.0",
) -> TelemetrySettings:
    global _logger_provider, _meter_provider, _logging_handler, _console_handler, _settings, _configured

    settings = TelemetrySettings.from_env(
        service_name=service_name,
        service_version=service_version,
    )
    _settings = settings

    if not settings.enabled:
        logging.basicConfig(
            level=getattr(logging, settings.log_level, logging.INFO),
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
        _configured = True
        logging.getLogger(__name__).info(
            "OpenTelemetry disabled (OTEL_SDK_DISABLED); using plain logging"
        )
        return settings

    resource = _resource(settings)
    log_exporter = build_log_exporter(settings)
    metric_exporter = build_metric_exporter(settings)

    _logger_provider = LoggerProvider(resource=resource)
    _logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(_logger_provider)

    metric_reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=settings.metrics_export_interval_ms,
    )
    _meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])

    from opentelemetry import metrics

    metrics.set_meter_provider(_meter_provider)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, settings.log_level, logging.INFO))

    _logging_handler = LoggingHandler(
        level=logging.NOTSET,
        logger_provider=_logger_provider,
    )
    root.addHandler(_logging_handler)

    if settings.log_console:
        _console_handler = logging.StreamHandler()
        _console_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        root.addHandler(_console_handler)

    LoggingInstrumentor().instrument(set_logging_format=True)

    _configured = True
    logging.getLogger(__name__).info(
        "OpenTelemetry configured service=%s endpoint=%s protocol=%s",
        settings.service_name,
        settings.otlp_endpoint,
        settings.otlp_protocol,
    )
    return settings


def instrument_app(app: Any) -> None:
    if not is_telemetry_enabled() or _settings is None:
        return

    FastAPIInstrumentor.instrument_app(app, excluded_urls=_settings.excluded_urls)
    HTTPXClientInstrumentor().instrument()
    logging.getLogger(__name__).info(
        "FastAPI and HTTPX instrumentation enabled (excluded_urls=%s)",
        _settings.excluded_urls,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def shutdown_telemetry() -> None:
    global _logger_provider, _meter_provider, _logging_handler, _console_handler, _configured

    if _logger_provider is not None:
        _logger_provider.shutdown()
        _logger_provider = None

    if _meter_provider is not None:
        _meter_provider.shutdown()
        _meter_provider = None

    if _logging_handler is not None:
        logging.getLogger().removeHandler(_logging_handler)
        _logging_handler = None

    if _console_handler is not None:
        logging.getLogger().removeHandler(_console_handler)
        _console_handler = None

    _configured = False
