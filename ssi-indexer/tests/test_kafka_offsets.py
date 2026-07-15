"""Tests for Kafka consumer offset / group metadata helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiokafka.structs import TopicPartition
from etl.kafka_offsets import (
    consumer_group_row,
    estimated_lag,
    partition_offset_details,
)


@pytest.mark.asyncio
async def test_estimated_lag_none_consumer():
    assert await estimated_lag(None) == 0


@pytest.mark.asyncio
async def test_partition_offset_details_assigned():
    tp = TopicPartition("instructions", 0)
    consumer = MagicMock()
    consumer.assignment.return_value = {tp}
    consumer.end_offsets = AsyncMock(return_value={tp: 42})
    consumer.position = AsyncMock(return_value=40)
    consumer.committed = AsyncMock(return_value=39)

    details = await partition_offset_details(consumer)
    assert details["assigned"] is True
    assert details["lag_total"] == 2
    assert details["partitions"] == [
        {
            "topic": "instructions",
            "partition": 0,
            "committed_offset": 39,
            "position": 40,
            "latest_offset": 42,
            "lag": 2,
        }
    ]


@pytest.mark.asyncio
async def test_partition_offset_details_unassigned():
    consumer = MagicMock()
    consumer.assignment.return_value = set()
    details = await partition_offset_details(consumer)
    assert details["assigned"] is False
    assert details["lag_total"] == 0


@pytest.mark.asyncio
async def test_consumer_group_row_paused():
    with patch("etl.kafka_offsets.pause_registry") as registry:
        registry.snapshot.return_value = {
            "instruction_fact": {"paused": True, "reason": "dlq_write_failed"},
        }
        row = await consumer_group_row(
            name="instruction_fact",
            topic="instructions",
            consumer_group="ssi-instruction-etl",
            consumer=None,
            task_running=True,
        )
    assert row["status"] == "paused"
    assert row["pause_reason"] == "dlq_write_failed"
    assert row["topic"] == "instructions"
    assert row["consumer_group"] == "ssi-instruction-etl"
