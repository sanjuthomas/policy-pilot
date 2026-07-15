from __future__ import annotations

from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

from etl.dlq.models import FailureClass


def classify_exception(exc: BaseException) -> FailureClass:
    if isinstance(exc, (TransientError, ServiceUnavailable, SessionExpired)):
        return FailureClass.TRANSIENT
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if any(
        token in name or token in message
        for token in (
            "timeout",
            "temporarily",
            "unavailable",
            "connection reset",
            "connection refused",
            "deadline",
            "429",
            "rate limit",
            "resource exhausted",
            "503",
            "502",
            "504",
        )
    ):
        return FailureClass.TRANSIENT
    if any(token in message for token in ("invalid", "schema", "not a dict", "missing")):
        return FailureClass.POISON
    return FailureClass.PERMANENT


def is_retryable(exc: BaseException) -> bool:
    return classify_exception(exc) == FailureClass.TRANSIENT
