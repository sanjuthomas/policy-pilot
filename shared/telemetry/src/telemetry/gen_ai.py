from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from opentelemetry.trace import Status, StatusCode

from telemetry.metrics import get_meter, record_counter, record_histogram
from telemetry.redaction import redact_string
from telemetry.setup import get_tracer, is_telemetry_enabled

logger = logging.getLogger(__name__)

_METER = None


def _get_gen_ai_meter():
    global _METER
    if _METER is None:
        _METER = get_meter("telemetry.gen_ai", version="0.1.0")
    return _METER


@dataclass
class GenAiCallResult:
    response_text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    attributes: dict[str, str] = field(default_factory=dict)


@contextmanager
def gen_ai_operation(
    *,
    operation: str,
    model: str,
    request_summary: str,
    operation_id: str | None = None,
) -> Iterator[GenAiCallResult]:
    """Trace, metric, and log a Vertex / Gemini call with redacted payloads."""
    result = GenAiCallResult()
    if not is_telemetry_enabled():
        yield result
        return

    span_name = f"gen_ai.{operation}"
    attributes: dict[str, Any] = {
        "gen_ai.system": "vertex_ai",
        "gen_ai.request.model": model,
        "gen_ai.operation.name": operation,
    }
    if operation_id:
        attributes["gen_ai.operation.id"] = operation_id

    tracer = get_tracer("telemetry.gen_ai")
    start = time.perf_counter()
    with tracer.start_as_current_span(span_name, attributes=attributes) as span:
        logger.info(
            "gen_ai_request operation=%s model=%s payload=%s",
            operation,
            model,
            redact_string(request_summary),
        )
        try:
            yield result
            duration_ms = (time.perf_counter() - start) * 1000.0
            metric_attrs = {
                "gen_ai.system": "vertex_ai",
                "gen_ai.request.model": model,
                "gen_ai.operation.name": operation,
            }
            record_histogram(
                _get_gen_ai_meter(),
                "gen_ai.client.operation.duration",
                duration_ms,
                unit="ms",
                attributes=metric_attrs,
            )
            record_counter(
                _get_gen_ai_meter(),
                "gen_ai.client.operation.count",
                attributes={**metric_attrs, "gen_ai.response.status": "success"},
            )
            if result.input_tokens is not None:
                record_counter(
                    _METER,
                    "gen_ai.client.token.usage",
                    amount=result.input_tokens,
                    attributes={**metric_attrs, "gen_ai.token.type": "input"},
                )
                span.set_attribute("gen_ai.usage.input_tokens", result.input_tokens)
            if result.output_tokens is not None:
                record_counter(
                    _METER,
                    "gen_ai.client.token.usage",
                    amount=result.output_tokens,
                    attributes={**metric_attrs, "gen_ai.token.type": "output"},
                )
                span.set_attribute("gen_ai.usage.output_tokens", result.output_tokens)
            for key, value in result.attributes.items():
                span.set_attribute(key, value)
            if result.response_text is not None:
                logger.info(
                    "gen_ai_response operation=%s model=%s payload=%s duration_ms=%.1f",
                    operation,
                    model,
                    redact_string(result.response_text),
                    duration_ms,
                )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000.0
            metric_attrs = {
                "gen_ai.system": "vertex_ai",
                "gen_ai.request.model": model,
                "gen_ai.operation.name": operation,
            }
            record_histogram(
                _get_gen_ai_meter(),
                "gen_ai.client.operation.duration",
                duration_ms,
                unit="ms",
                attributes=metric_attrs,
            )
            record_counter(
                _get_gen_ai_meter(),
                "gen_ai.client.operation.count",
                attributes={**metric_attrs, "gen_ai.response.status": "error"},
            )
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            logger.warning(
                "gen_ai_error operation=%s model=%s duration_ms=%.1f error=%s",
                operation,
                model,
                duration_ms,
                exc,
            )
            raise


def summarize_embedding_request(text: str) -> str:
    return f"text_chars={len(text)}"


def summarize_generation_request(
    *,
    system: str,
    user: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    history_len = len(history or [])
    return (
        f"system_chars={len(system)} user_chars={len(user)} "
        f"history_messages={history_len}"
    )
