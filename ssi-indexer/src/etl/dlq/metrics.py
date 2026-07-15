from __future__ import annotations

from typing import Any

from telemetry import get_meter, record_counter

_meter = None


def _get_meter():
    global _meter
    if _meter is None:
        _meter = get_meter("etl.dlq", version="0.1.0")
    return _meter


def record_dlq_event(name: str, **attrs: Any) -> None:
    clean = {k: str(v) for k, v in attrs.items() if v is not None}
    record_counter(_get_meter(), name, attributes=clean)
