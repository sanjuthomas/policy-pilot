from __future__ import annotations

import logging

from telemetry.redaction import redact_string

_HTTP_CLIENT_LOGGERS = ("httpx", "httpcore")


class RedactingLogFilter(logging.Filter):
    """Scrub sensitive values from every log record before export or console output."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            record.msg = record.getMessage()
            record.args = None
        record.msg = redact_string(str(record.msg))
        return True


def install_redacting_log_filters(*, root: logging.Logger | None = None) -> RedactingLogFilter:
    """Attach redaction to root, HTTP client loggers, and all root handlers.

    Python 3.12+ propagates child logger records to parent handlers without
    running parent logger filters, so httpx request lines need filters on the
    handlers (and httpx itself) rather than only on the root logger.
    """
    redacting = RedactingLogFilter()
    root_logger = root or logging.getLogger()

    if redacting not in root_logger.filters:
        root_logger.addFilter(redacting)

    for name in _HTTP_CLIENT_LOGGERS:
        client_logger = logging.getLogger(name)
        if redacting not in client_logger.filters:
            client_logger.addFilter(redacting)

    for handler in root_logger.handlers:
        if redacting not in handler.filters:
            handler.addFilter(redacting)

    return redacting
