from __future__ import annotations

import logging
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from telemetry.setup import configure_telemetry, instrument_app, shutdown_telemetry


@pytest.fixture(autouse=True)
def reset_telemetry() -> None:
    shutdown_telemetry()
    yield
    shutdown_telemetry()


def test_http_payload_logging_redacts_json_bodies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.environ.pop("OTEL_SDK_DISABLED", None)
    configure_telemetry("http-logging-test")

    app = FastAPI()
    messages: list[str] = []
    http_logger = logging.getLogger("telemetry.http_logging")
    original_info = http_logger.info

    def capture_info(message: str, *args: object) -> None:
        messages.append(message % args if args else message)
        original_info(message, *args)

    monkeypatch.setattr(http_logger, "info", capture_info)

    @app.post("/api/example")
    async def example(payload: dict) -> dict:
        return {"echo": payload.get("name"), "amount": payload.get("amount")}

    instrument_app(app)

    client = TestClient(app)
    response = client.post(
        "/api/example",
        json={"name": "Sarah Chen", "amount": 1_000_000},
        headers={"Authorization": "Bearer secret"},
    )

    assert response.status_code == 200
    request_logs = [message for message in messages if "http_request" in message]
    response_logs = [message for message in messages if "http_response" in message]
    assert request_logs
    assert response_logs
    assert "Sarah Chen" not in request_logs[0]
    assert "secret" not in request_logs[0]
    assert "Sarah Chen" not in response_logs[0]


def test_http_payload_logging_skips_health() -> None:
    os.environ.pop("OTEL_SDK_DISABLED", None)
    configure_telemetry("http-logging-health")

    app = FastAPI()

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    instrument_app(app)
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
