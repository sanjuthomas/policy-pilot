"""Kafka consumer lag and per-partition offset metadata for ops UI."""

from __future__ import annotations

import logging
from typing import Any

from aiokafka import AIOKafkaConsumer

from etl.dlq.pause import pause_registry

logger = logging.getLogger(__name__)


async def estimated_lag(consumer: AIOKafkaConsumer | None) -> int:
    snapshot = await partition_offset_details(consumer)
    return int(snapshot.get("lag_total") or 0)


async def partition_offset_details(consumer: AIOKafkaConsumer | None) -> dict[str, Any]:
    """Return per-partition committed / position / latest offsets for an assigned consumer."""
    if consumer is None:
        return {"partitions": [], "lag_total": 0, "assigned": False}

    try:
        partitions = sorted(
            consumer.assignment(),
            key=lambda tp: (tp.topic, tp.partition),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("kafka assignment unavailable: %s", exc)
        return {"partitions": [], "lag_total": 0, "assigned": False, "error": str(exc)}

    if not partitions:
        return {"partitions": [], "lag_total": 0, "assigned": False}

    try:
        end_offsets = await consumer.end_offsets(list(partitions))
    except Exception as exc:  # noqa: BLE001
        logger.warning("kafka end_offsets unavailable: %s", exc)
        return {
            "partitions": [],
            "lag_total": 0,
            "assigned": True,
            "error": str(exc),
        }

    rows: list[dict[str, Any]] = []
    lag_total = 0
    for tp in partitions:
        latest = int(end_offsets.get(tp, 0))
        try:
            position = int(await consumer.position(tp))
        except Exception:  # noqa: BLE001
            position = None
        committed_raw = None
        try:
            committed_raw = await consumer.committed(tp)
        except Exception:  # noqa: BLE001
            committed_raw = None
        committed = _normalize_committed(committed_raw)
        lag = max(0, latest - position) if position is not None else None
        if lag is not None:
            lag_total += lag
        rows.append(
            {
                "topic": tp.topic,
                "partition": int(tp.partition),
                "committed_offset": committed,
                "position": position,
                "latest_offset": latest,
                "lag": lag,
            }
        )

    return {"partitions": rows, "lag_total": lag_total, "assigned": True}


def _normalize_committed(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    offset = getattr(value, "offset", None)
    if offset is None:
        return None
    return int(offset)


async def consumer_group_row(
    *,
    name: str,
    topic: str,
    consumer_group: str,
    consumer: AIOKafkaConsumer | None,
    task_running: bool,
) -> dict[str, Any]:
    """One consumer-group row for admin UI (plus nested partition details)."""
    pause = pause_registry.snapshot().get(name) or {}
    paused = bool(pause.get("paused"))
    details = await partition_offset_details(consumer)
    if paused:
        status = "paused"
    elif consumer is None:
        status = "disabled"
    elif not task_running:
        status = "stopped"
    elif not details.get("assigned"):
        status = "waiting_assignment"
    elif details.get("error"):
        status = "error"
    else:
        status = "running"

    return {
        "name": name,
        "topic": topic,
        "consumer_group": consumer_group,
        "status": status,
        "paused": paused,
        "pause_reason": pause.get("reason"),
        "lag_total": details.get("lag_total", 0),
        "assigned": details.get("assigned", False),
        "error": details.get("error"),
        "partitions": details.get("partitions") or [],
    }
