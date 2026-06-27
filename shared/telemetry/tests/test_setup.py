from __future__ import annotations

import logging
import os

import pytest
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from telemetry.config import TelemetrySettings
from telemetry.metrics import get_meter, record_counter
from telemetry.setup import (
    configure_telemetry,
    instrument_app,
    is_telemetry_enabled,
    shutdown_telemetry,
)


@pytest.fixture(autouse=True)
def reset_telemetry() -> None:
    shutdown_telemetry()
    yield
    shutdown_telemetry()


def test_settings_from_env() -> None:
    os.environ["OTEL_SDK_DISABLED"] = "false"
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://collector:4317"
    settings = TelemetrySettings.from_env(service_name="test-service", service_version="1.2.3")
    assert settings.enabled is True
    assert settings.service_name == "test-service"
    assert settings.service_version == "1.2.3"
    assert settings.otlp_endpoint == "http://collector:4317"


def test_configure_disabled() -> None:
    os.environ["OTEL_SDK_DISABLED"] = "true"
    settings = configure_telemetry("disabled-service")
    assert settings.enabled is False
    assert is_telemetry_enabled() is False


def test_configure_enabled_sets_meter_provider() -> None:
    os.environ.pop("OTEL_SDK_DISABLED", None)
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4317"

    settings = configure_telemetry("enabled-service", service_version="0.0.1")
    assert settings.enabled is True
    assert is_telemetry_enabled() is True

    meter = get_meter("test.meter")
    record_counter(meter, "test.counter", attributes={"result": "ok"})


def test_instrument_app_noop_when_disabled() -> None:
    os.environ["OTEL_SDK_DISABLED"] = "true"
    configure_telemetry("noop-service")

    from fastapi import FastAPI

    app = FastAPI()
    instrument_app(app)


def test_instrument_app_when_enabled() -> None:
    os.environ.pop("OTEL_SDK_DISABLED", None)
    configure_telemetry("fastapi-service")

    from fastapi import FastAPI

    app = FastAPI()
    instrument_app(app)

    logger = logging.getLogger("telemetry.test")
    logger.info("structured log for otel bridge")
