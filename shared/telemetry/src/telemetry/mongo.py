"""MongoDB command-duration metrics via PyMongo ``CommandListener``.

Requires ``pymongo`` at call sites (Motor/PyMongo services). Soft-imports so
``ssi-telemetry`` stays free of a hard pymongo dependency.
"""

from __future__ import annotations

from typing import Any

from telemetry.metrics import get_meter, record_counter, record_histogram
from telemetry.setup import is_telemetry_enabled

_meter = None
_listener: Any | None = None


def _get_meter():
    global _meter
    if _meter is None:
        _meter = get_meter("telemetry.db", version="0.1.0")
    return _meter


def _collection_from_command(command_name: str, command: Any) -> str:
    """Best-effort collection name from a wire command document."""
    if command is None:
        return "unknown"
    try:
        value = command.get(command_name)
        if isinstance(value, str) and value:
            return value
    except Exception:
        pass
    return "unknown"


def _record(command_name: str, collection: str, *, duration_ms: float, status: str) -> None:
    base = {
        "db.system": "mongodb",
        "db.operation": command_name or "unknown",
        "db.collection": collection or "unknown",
    }
    record_histogram(
        _get_meter(),
        "db.client.operation.duration",
        duration_ms,
        unit="ms",
        attributes=base,
    )
    record_counter(
        _get_meter(),
        "db.client.operation.count",
        attributes={**base, "db.response.status": status},
    )


def mongo_event_listeners() -> list[Any]:
    """Return PyMongo event listeners for ``AsyncIOMotorClient(..., event_listeners=...)``.

    Safe when telemetry is disabled (listener no-ops) or pymongo is missing
    (returns empty list).
    """
    global _listener
    try:
        from pymongo import monitoring
    except ImportError:
        return []

    if _listener is not None:
        return [_listener]

    class MongoTelemetryListener(monitoring.CommandListener):
        def __init__(self) -> None:
            self._pending: dict[int, str] = {}

        def started(self, event: monitoring.CommandStartedEvent) -> None:
            if not is_telemetry_enabled():
                return
            self._pending[event.request_id] = _collection_from_command(
                event.command_name, event.command
            )

        def succeeded(self, event: monitoring.CommandSucceededEvent) -> None:
            collection = self._pending.pop(event.request_id, "unknown")
            if not is_telemetry_enabled():
                return
            _record(
                event.command_name,
                collection,
                duration_ms=event.duration_micros / 1000.0,
                status="success",
            )

        def failed(self, event: monitoring.CommandFailedEvent) -> None:
            collection = self._pending.pop(event.request_id, "unknown")
            if not is_telemetry_enabled():
                return
            _record(
                event.command_name,
                collection,
                duration_ms=event.duration_micros / 1000.0,
                status="error",
            )

    _listener = MongoTelemetryListener()
    return [_listener]
