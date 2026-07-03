"""Tests for Kafka consumer helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from neo4j.exceptions import TransientError

from etl.instruction_consumer import InstructionKafkaConsumer
from etl.instruction_security_event_consumer import (
    InstructionSecurityEventKafkaConsumer,
)
from etl.payment_consumer import (
    PaymentFactKafkaConsumer,
    PaymentSecurityEventKafkaConsumer,
)


async def test_instruction_consumer_kafka_disabled():
    pipeline = MagicMock()
    consumer = InstructionKafkaConsumer(pipeline)
    with patch("etl.instruction_consumer.settings") as mock_settings:
        mock_settings.kafka_enabled = False
        await consumer.start()
    assert consumer._consumer is None


async def test_instruction_consumer_handle_invalid_payload():
    pipeline = AsyncMock()
    consumer = InstructionKafkaConsumer(pipeline)
    await consumer._handle_message("not-a-dict")
    await consumer._handle_message({"missing": "instruction_id"})
    pipeline.process_instruction_fact.assert_not_called()


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


async def test_payment_security_event_consumer_handle():
    pipeline = AsyncMock()
    consumer = PaymentSecurityEventKafkaConsumer(pipeline)
    await consumer._handle_message("bad")
    pipeline.process.assert_not_called()

    event = {"event_id": "pe1"}
    await consumer._handle_message(event)
    pipeline.process.assert_awaited_once_with(event)


async def test_payment_fact_consumer_handle():
    pipeline = AsyncMock()
    consumer = PaymentFactKafkaConsumer(pipeline)
    await consumer._handle_message({})
    pipeline.process.assert_not_called()

    fact = {"payment_id": "p1"}
    await consumer._handle_message(fact)
    pipeline.process.assert_awaited_once_with(fact)


async def test_payment_security_event_consumer_running_property():
    consumer = PaymentSecurityEventKafkaConsumer(MagicMock())
    assert consumer.running is False
    consumer._consumer = MagicMock()
    assert consumer.running is True


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
    consumer._consumer = AsyncMock()

    message = MagicMock()
    message.value = {"instruction_id": "i1"}
    message.offset = 0
    message.partition = 0

    async def one_message():
        yield message

    consumer._consumer.__aiter__ = lambda self: one_message()
    consumer._consumer.commit = AsyncMock()

    with patch("etl.instruction_consumer.asyncio.sleep", AsyncMock()):
        task = __import__("asyncio").create_task(consumer._run())
        await task

    assert pipeline.process_instruction_fact.await_count == 2
    consumer._consumer.commit.assert_awaited_once()
