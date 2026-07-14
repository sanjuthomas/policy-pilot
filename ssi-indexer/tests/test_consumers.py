"""Tests for Kafka consumer helpers."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from etl.instruction_consumer import InstructionKafkaConsumer
from etl.instruction_security_event_consumer import (
    InstructionSecurityEventKafkaConsumer,
)
from etl.payment_consumer import (
    PaymentFactKafkaConsumer,
    PaymentSecurityEventKafkaConsumer,
)
from neo4j.exceptions import TransientError


def _one_message_consumer(consumer, message):
    async def one_message():
        yield message

    consumer._consumer = AsyncMock()
    consumer._consumer.__aiter__ = lambda self: one_message()
    consumer._consumer.commit = AsyncMock()
    return consumer


async def test_instruction_consumer_kafka_disabled():
    pipeline = MagicMock()
    consumer = InstructionKafkaConsumer(pipeline)
    with patch("etl.instruction_consumer.settings") as mock_settings:
        mock_settings.kafka_enabled = False
        await consumer.start()
    assert consumer._consumer is None


async def _pending_task() -> None:
    await asyncio.Event().wait()


async def test_instruction_consumer_start_and_close():
    pipeline = MagicMock()
    consumer = InstructionKafkaConsumer(pipeline)
    mock_kafka = AsyncMock()
    mock_kafka.start = AsyncMock()
    mock_kafka.stop = AsyncMock()

    with (
        patch("etl.instruction_consumer.settings") as mock_settings,
        patch("etl.instruction_consumer.AIOKafkaConsumer", return_value=mock_kafka),
        patch("etl.instruction_consumer.asyncio.create_task") as mock_create_task,
    ):
        mock_settings.kafka_enabled = True
        mock_settings.kafka_instruction_topic = "instructions"
        mock_settings.kafka_bootstrap_servers = "kafka:9092"
        mock_settings.kafka_instruction_consumer_group = "grp"
        mock_create_task.return_value = AsyncMock()
        await consumer.start()

    assert consumer._consumer is mock_kafka
    mock_kafka.start.assert_awaited_once()
    mock_create_task.assert_called_once()

    consumer._task = asyncio.create_task(_pending_task())
    await consumer.close()
    mock_kafka.stop.assert_awaited_once()
    assert consumer._consumer is None


async def test_instruction_consumer_handle_invalid_payload():
    pipeline = AsyncMock()
    consumer = InstructionKafkaConsumer(pipeline)
    await consumer._handle_message("not-a-dict")
    await consumer._handle_message({"missing": "instruction_id"})
    pipeline.process_instruction_fact.assert_not_called()


async def test_instruction_consumer_handle_versioned_mongo_payload():
    pipeline = AsyncMock()
    consumer = InstructionKafkaConsumer(pipeline)
    mongo_doc = {
        "_id": "instr-1|2",
        "version_number": 2,
        "in": "2026-07-01T12:00:00Z",
        "status": "PENDING",
        "payload": {
            "instruction_type": "WIRE",
            "created_by": {"user_id": "c1"},
            "lifecycle_events": [{"action": "SUBMIT", "actor_user_id": "c1"}],
        },
    }
    await consumer._handle_message(mongo_doc)
    pipeline.process_instruction_fact.assert_awaited_once()
    fact = pipeline.process_instruction_fact.await_args.args[0]
    assert fact["instruction_id"] == "instr-1"
    assert fact["action"] == "SUBMIT"


async def test_instruction_consumer_handle_valid_payload():
    pipeline = AsyncMock()
    consumer = InstructionKafkaConsumer(pipeline)
    fact = {"instruction_id": "i1"}
    await consumer._handle_message(fact)
    pipeline.process_instruction_fact.assert_awaited_once_with(fact)


async def test_instruction_security_event_consumer_handle():
    pipeline = AsyncMock()
    consumer = InstructionSecurityEventKafkaConsumer(pipeline)
    await consumer._handle_message({})
    pipeline.process_instruction_security_event.assert_not_called()

    event = {"event_id": "e1"}
    await consumer._handle_message(event)
    pipeline.process_instruction_security_event.assert_awaited_once_with(event)

    pipeline.reset_mock()
    mongo_event = {"_id": "e2", "severity": "INFO"}
    await consumer._handle_message(mongo_event)
    pipeline.process_instruction_security_event.assert_awaited_once_with(
        {"_id": "e2", "severity": "INFO", "event_id": "e2"}
    )


async def test_instruction_security_event_consumer_start_and_run():
    pipeline = AsyncMock()
    consumer = InstructionSecurityEventKafkaConsumer(pipeline)
    mock_kafka = AsyncMock()
    mock_kafka.start = AsyncMock()
    mock_kafka.stop = AsyncMock()

    with (
        patch("etl.instruction_security_event_consumer.settings") as mock_settings,
        patch(
            "etl.instruction_security_event_consumer.AIOKafkaConsumer",
            return_value=mock_kafka,
        ),
        patch("etl.instruction_security_event_consumer.asyncio.create_task") as mock_create_task,
    ):
        mock_settings.kafka_enabled = True
        mock_settings.kafka_instruction_security_events_topic = "instruction_security_events"
        mock_settings.kafka_bootstrap_servers = "kafka:9092"
        mock_settings.kafka_instruction_security_events_consumer_group = "grp"
        mock_create_task.return_value = AsyncMock()
        await consumer.start()

    message = MagicMock()
    message.value = {"event_id": "evt-1"}
    message.offset = 1
    message.partition = 0
    _one_message_consumer(consumer, message)
    await consumer._run()
    pipeline.process_instruction_security_event.assert_awaited_once()


async def test_instruction_security_event_consumer_close_stops_task_and_consumer():
    consumer = InstructionSecurityEventKafkaConsumer(AsyncMock())
    kafka = AsyncMock()
    consumer._consumer = kafka
    consumer._task = asyncio.create_task(_pending_task())

    await consumer.close()

    assert consumer._task is None
    assert consumer._consumer is None
    kafka.stop.assert_awaited_once()


async def test_instruction_security_event_consumer_run_retries_transient_error():
    pipeline = AsyncMock()
    pipeline.process_instruction_security_event.side_effect = [
        TransientError("deadlock"),
        None,
    ]
    consumer = InstructionSecurityEventKafkaConsumer(pipeline)
    message = MagicMock(value={"event_id": "evt-1"}, offset=0, partition=0)
    _one_message_consumer(consumer, message)

    with patch("etl.instruction_security_event_consumer.asyncio.sleep", AsyncMock()):
        await consumer._run()

    assert pipeline.process_instruction_security_event.await_count == 2
    consumer._consumer.commit.assert_awaited_once()


async def test_instruction_security_event_consumer_run_skips_generic_error():
    pipeline = AsyncMock()
    pipeline.process_instruction_security_event.side_effect = RuntimeError("bad event")
    consumer = InstructionSecurityEventKafkaConsumer(pipeline)
    message = MagicMock(value={"event_id": "evt-1"}, offset=0, partition=0)
    _one_message_consumer(consumer, message)

    await consumer._run()

    consumer._consumer.commit.assert_not_awaited()


async def test_payment_security_event_consumer_handle():
    pipeline = AsyncMock()
    consumer = PaymentSecurityEventKafkaConsumer(pipeline)
    await consumer._handle_message("bad")
    pipeline.process.assert_not_called()

    event = {"event_id": "pe1"}
    await consumer._handle_message(event)
    pipeline.process.assert_awaited_once_with(event)


async def test_payment_security_event_consumer_start_close_and_run():
    pipeline = AsyncMock()
    consumer = PaymentSecurityEventKafkaConsumer(pipeline)
    mock_kafka = AsyncMock()
    mock_kafka.start = AsyncMock()
    mock_kafka.stop = AsyncMock()

    with (
        patch("etl.payment_consumer.settings") as mock_settings,
        patch("etl.payment_consumer.AIOKafkaConsumer", return_value=mock_kafka),
        patch("etl.payment_consumer.asyncio.create_task") as mock_create_task,
    ):
        mock_settings.kafka_enabled = True
        mock_settings.kafka_payment_security_events_topic = "payment_security_events"
        mock_settings.kafka_bootstrap_servers = "kafka:9092"
        mock_settings.kafka_payment_security_events_consumer_group = "grp"
        mock_create_task.return_value = AsyncMock()
        await consumer.start()

    assert consumer._consumer is not None
    consumer._task = asyncio.create_task(_pending_task())
    await consumer.close()

    message = MagicMock()
    message.value = {"_id": "pse-1", "severity": "ALERT"}
    message.offset = 2
    message.partition = 1
    _one_message_consumer(consumer, message)
    await consumer._run()
    pipeline.process.assert_awaited_once()


async def test_payment_fact_consumer_handle():
    pipeline = AsyncMock()
    consumer = PaymentFactKafkaConsumer(pipeline)
    await consumer._handle_message({})
    pipeline.process.assert_not_called()

    fact = {"payment_id": "p1"}
    await consumer._handle_message(fact)
    pipeline.process.assert_awaited_once_with(fact)


async def test_payment_fact_consumer_versioned_mongo_payload():
    pipeline = AsyncMock()
    consumer = PaymentFactKafkaConsumer(pipeline)
    mongo_doc = {
        "_id": "pay-1|2",
        "version_number": 2,
        "instruction_id": "instr-1",
        "status": "SUBMITTED",
        "payload": {"amount": 100.0, "currency": "USD", "created_by": {"user_id": "u1"}},
    }
    await consumer._handle_message(mongo_doc)
    pipeline.process.assert_awaited_once()
    fact = pipeline.process.await_args.args[0]
    assert fact["payment_id"] == "pay-1"


async def test_payment_fact_consumer_start_and_run():
    pipeline = AsyncMock()
    consumer = PaymentFactKafkaConsumer(pipeline)
    mock_kafka = AsyncMock()
    mock_kafka.start = AsyncMock()
    mock_kafka.stop = AsyncMock()

    with (
        patch("etl.payment_consumer.settings") as mock_settings,
        patch("etl.payment_consumer.AIOKafkaConsumer", return_value=mock_kafka),
        patch("etl.payment_consumer.asyncio.create_task") as mock_create_task,
    ):
        mock_settings.kafka_enabled = True
        mock_settings.kafka_payments_topic = "payments"
        mock_settings.kafka_bootstrap_servers = "kafka:9092"
        mock_settings.kafka_payments_consumer_group = "grp"
        mock_create_task.return_value = AsyncMock()
        await consumer.start()

    message = MagicMock()
    message.value = {"payment_id": "pay-9"}
    message.offset = 0
    message.partition = 0
    _one_message_consumer(consumer, message)
    await consumer._run()
    pipeline.process.assert_awaited_once()


async def test_instruction_consumer_close_without_start():
    consumer = InstructionKafkaConsumer(MagicMock())
    await consumer.close()
    assert consumer._consumer is None


async def test_instruction_security_event_consumer_kafka_disabled():
    consumer = InstructionSecurityEventKafkaConsumer(AsyncMock())
    with patch("etl.instruction_security_event_consumer.settings") as mock_settings:
        mock_settings.kafka_enabled = False
        await consumer.start()
    assert consumer._consumer is None


async def test_payment_security_event_consumer_kafka_disabled():
    consumer = PaymentSecurityEventKafkaConsumer(AsyncMock())
    with patch("etl.payment_consumer.settings") as mock_settings:
        mock_settings.kafka_enabled = False
        await consumer.start()
    assert consumer._consumer is None


async def test_payment_fact_consumer_kafka_disabled():
    consumer = PaymentFactKafkaConsumer(AsyncMock())
    with patch("etl.payment_consumer.settings") as mock_settings:
        mock_settings.kafka_enabled = False
        await consumer.start()
    assert consumer._consumer is None


async def test_instruction_consumer_run_retries_transient_error():
    pipeline = AsyncMock()
    pipeline.process_instruction_fact.side_effect = [
        TransientError("deadlock"),
        None,
    ]
    consumer = InstructionKafkaConsumer(pipeline)
    message = MagicMock()
    message.value = {"instruction_id": "i1"}
    message.offset = 0
    message.partition = 0
    _one_message_consumer(consumer, message)

    with patch("etl.instruction_consumer.asyncio.sleep", AsyncMock()):
        await consumer._run()

    assert pipeline.process_instruction_fact.await_count == 2
    consumer._consumer.commit.assert_awaited_once()


async def test_instruction_consumer_run_skips_after_generic_error():
    pipeline = AsyncMock()
    pipeline.process_instruction_fact.side_effect = RuntimeError("boom")
    consumer = InstructionKafkaConsumer(pipeline)
    message = MagicMock()
    message.value = {"instruction_id": "i1"}
    message.offset = 0
    message.partition = 0
    _one_message_consumer(consumer, message)
    await consumer._run()
    pipeline.process_instruction_fact.assert_awaited_once()
    consumer._consumer.commit.assert_not_awaited()


async def test_payment_fact_consumer_run_exhausts_transient_retries():
    pipeline = AsyncMock()
    pipeline.process.side_effect = TransientError("deadlock")
    consumer = PaymentFactKafkaConsumer(pipeline)
    message = MagicMock()
    message.value = {"payment_id": "p1"}
    message.offset = 0
    message.partition = 0
    _one_message_consumer(consumer, message)

    with patch("etl.payment_consumer.asyncio.sleep", AsyncMock()):
        await consumer._run()

    assert pipeline.process.await_count == 5
    consumer._consumer.commit.assert_not_awaited()


async def test_payment_security_event_consumer_run_generic_error():
    pipeline = AsyncMock()
    pipeline.process.side_effect = ValueError("bad event")
    consumer = PaymentSecurityEventKafkaConsumer(pipeline)
    message = MagicMock()
    message.value = {"event_id": "e1"}
    message.offset = 0
    message.partition = 0
    _one_message_consumer(consumer, message)
    await consumer._run()
    consumer._consumer.commit.assert_not_awaited()


async def test_instruction_security_event_consumer_invalid_payload_type():
    pipeline = AsyncMock()
    consumer = InstructionSecurityEventKafkaConsumer(pipeline)
    await consumer._handle_message("not-json")
    pipeline.process_instruction_security_event.assert_not_called()
