from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from telemetry.gen_ai import gen_ai_operation, summarize_embedding_request
from telemetry.setup import configure_telemetry, shutdown_telemetry


@pytest.fixture(autouse=True)
def reset_telemetry() -> None:
    shutdown_telemetry()
    yield
    shutdown_telemetry()


def test_summarize_embedding_request() -> None:
    summary = summarize_embedding_request("find FICC alerts")
    assert summary == "text_chars=16"


def test_gen_ai_operation_records_success() -> None:
    os.environ.pop("OTEL_SDK_DISABLED", None)
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4317"
    configure_telemetry("gen-ai-test")

    with patch("telemetry.gen_ai.record_histogram") as mock_histogram, patch(
        "telemetry.gen_ai.record_counter"
    ) as mock_counter:
        with gen_ai_operation(
            operation="embeddings",
            model="text-embedding-004",
            request_summary="text_chars=5",
        ) as result:
            result.response_text = "vector_dim=768"
            result.input_tokens = 12
            result.output_tokens = 0

    mock_histogram.assert_called_once()
    assert mock_counter.call_count >= 2


def test_gen_ai_operation_records_error() -> None:
    os.environ.pop("OTEL_SDK_DISABLED", None)
    configure_telemetry("gen-ai-error-test")

    with patch("telemetry.gen_ai.record_histogram") as mock_histogram, patch(
        "telemetry.gen_ai.record_counter"
    ) as mock_counter:
        with pytest.raises(RuntimeError, match="boom"):
            with gen_ai_operation(
                operation="chat",
                model="gemini-2.5-flash",
                request_summary="user_chars=4",
            ):
                raise RuntimeError("boom")

    mock_histogram.assert_called_once()
    mock_counter.assert_called_once()
    assert mock_counter.call_args.kwargs["attributes"]["gen_ai.response.status"] == "error"


def test_gen_ai_operation_noop_when_disabled() -> None:
    os.environ["OTEL_SDK_DISABLED"] = "true"
    configure_telemetry("disabled-gen-ai")

    with gen_ai_operation(
        operation="chat",
        model="gemini-2.5-flash",
        request_summary="ignored",
    ) as result:
        result.response_text = "ok"

    assert result.response_text == "ok"
