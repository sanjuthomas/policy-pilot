from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from telemetry.mongo import (
    _collection_from_command,
    mongo_event_listeners,
)


def test_collection_from_find_command() -> None:
    assert _collection_from_command("find", {"find": "payments"}) == "payments"


def test_collection_from_unknown() -> None:
    assert _collection_from_command("ping", {"ping": 1}) == "unknown"


def test_mongo_event_listeners_records_success() -> None:
    listeners = mongo_event_listeners()
    assert len(listeners) == 1
    listener = listeners[0]

    started = SimpleNamespace(
        request_id=42,
        command_name="find",
        command={"find": "instructions"},
    )
    succeeded = SimpleNamespace(
        request_id=42,
        command_name="find",
        duration_micros=1500,
    )

    with (
        patch("telemetry.mongo.is_telemetry_enabled", return_value=True),
        patch("telemetry.mongo.record_histogram") as hist,
        patch("telemetry.mongo.record_counter") as counter,
    ):
        listener.started(started)
        listener.succeeded(succeeded)

    hist.assert_called_once()
    assert hist.call_args.args[1] == "db.client.operation.duration"
    assert hist.call_args.args[2] == 1.5
    assert hist.call_args.kwargs["attributes"]["db.collection"] == "instructions"
    counter.assert_called_once()
    assert counter.call_args.kwargs["attributes"]["db.response.status"] == "success"


def test_mongo_event_listeners_records_error() -> None:
    listeners = mongo_event_listeners()
    listener = listeners[0]
    started = SimpleNamespace(
        request_id=7,
        command_name="insert",
        command={"insert": "payments"},
    )
    failed = SimpleNamespace(
        request_id=7,
        command_name="insert",
        duration_micros=800,
    )

    with (
        patch("telemetry.mongo.is_telemetry_enabled", return_value=True),
        patch("telemetry.mongo.record_histogram") as hist,
        patch("telemetry.mongo.record_counter") as counter,
    ):
        listener.started(started)
        listener.failed(failed)

    assert hist.call_args.args[2] == 0.8
    assert counter.call_args.kwargs["attributes"]["db.response.status"] == "error"


def test_mongo_event_listeners_noop_when_disabled() -> None:
    listeners = mongo_event_listeners()
    listener = listeners[0]
    with (
        patch("telemetry.mongo.is_telemetry_enabled", return_value=False),
        patch("telemetry.mongo.record_histogram") as hist,
    ):
        listener.started(
            SimpleNamespace(request_id=1, command_name="find", command={"find": "x"})
        )
        listener.succeeded(
            SimpleNamespace(request_id=1, command_name="find", duration_micros=10)
        )
    hist.assert_not_called()


def test_mongo_event_listeners_cached() -> None:
    a = mongo_event_listeners()
    b = mongo_event_listeners()
    assert len(a) == 1
    assert a[0] is b[0]
