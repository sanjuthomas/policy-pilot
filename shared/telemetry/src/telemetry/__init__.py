from telemetry.config import TelemetrySettings
from telemetry.logging_filter import RedactingLogFilter, install_redacting_log_filters
from telemetry.metrics import get_meter, record_counter, record_histogram
from telemetry.redaction import (
    redact_headers,
    redact_json_body,
    redact_payload,
    redact_string,
    redact_value,
)
from telemetry.setup import (
    configure_telemetry,
    get_logger,
    get_tracer,
    instrument_app,
    is_telemetry_enabled,
    shutdown_telemetry,
)

__all__ = [
    "TelemetrySettings",
    "configure_telemetry",
    "get_logger",
    "get_meter",
    "get_tracer",
    "instrument_app",
    "is_telemetry_enabled",
    "record_counter",
    "record_histogram",
    "RedactingLogFilter",
    "install_redacting_log_filters",
    "redact_headers",
    "redact_json_body",
    "redact_payload",
    "redact_string",
    "redact_value",
    "shutdown_telemetry",
]


def __getattr__(name: str):  # noqa: ANN001
    if name == "GenAiCallResult":
        from telemetry.gen_ai import GenAiCallResult

        return GenAiCallResult
    if name == "gen_ai_operation":
        from telemetry.gen_ai import gen_ai_operation

        return gen_ai_operation
    if name == "summarize_embedding_request":
        from telemetry.gen_ai import summarize_embedding_request

        return summarize_embedding_request
    if name == "summarize_generation_request":
        from telemetry.gen_ai import summarize_generation_request

        return summarize_generation_request
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
