from __future__ import annotations

import io
import logging
import os
import sys

from telemetry.logging_filter import RedactingLogFilter, install_redacting_log_filters
from telemetry.setup import configure_telemetry, shutdown_telemetry


def test_redacting_log_filter_scrubs_record_message() -> None:
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=(
            "HTTP Request: GET http://zitadel-proxy/v2/sessions/123"
            "?sessionToken=secret-value"
        ),
        args=(),
        exc_info=None,
    )
    assert RedactingLogFilter().filter(record) is True
    assert "secret-value" not in record.msg
    assert "sessionToken=[REDACTED]" in record.msg


def test_install_redacting_log_filters_scrubs_httpx_propagation() -> None:
    os.environ.pop("OTEL_SDK_DISABLED", None)
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4317"
    os.environ["OTEL_LOG_CONSOLE"] = "true"

    configure_telemetry("httpx-redaction-test")
    root = logging.getLogger()
    stream = io.StringIO()
    for handler in root.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.stream = stream

    secret = "YzyFnENFkW6EAcFZjzNdQqB_CS9dvaONbyUA3gftt05t9ZDIlMxpt4OUhznLHrPj118A21fTG5SqnA"
    logging.getLogger("httpx").info(
        "HTTP Request: GET http://zitadel-proxy/v2/sessions/380233132256788490"
        f"?sessionToken={secret} \"HTTP/1.1 200 OK\""
    )

    output = stream.getvalue()
    assert secret not in output
    assert "380233132256788490" not in output
    assert "sessionToken=[REDACTED]" in output
    assert "/v2/sessions/[REDACTED]" in output
    shutdown_telemetry()
