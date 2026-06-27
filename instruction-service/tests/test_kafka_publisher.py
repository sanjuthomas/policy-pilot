from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ilm.kafka_publisher import SecurityEventKafkaPublisher


@pytest.mark.asyncio
async def test_start_disabled(monkeypatch) -> None:
    monkeypatch.setattr("ilm.kafka_publisher.settings.kafka_enabled", False)
    publisher = SecurityEventKafkaPublisher()
    await publisher.start()
    assert publisher._producer is None


@pytest.mark.asyncio
async def test_start_and_close(monkeypatch) -> None:
    monkeypatch.setattr("ilm.kafka_publisher.settings.kafka_enabled", True)
    publisher = SecurityEventKafkaPublisher()
    mock_producer = MagicMock()
    mock_producer.start = AsyncMock()
    mock_producer.stop = AsyncMock()

    with patch("ilm.kafka_publisher.AIOKafkaProducer", return_value=mock_producer):
        await publisher.start()
        assert publisher._producer is mock_producer
        await publisher.close()
        mock_producer.stop.assert_awaited_once()
        assert publisher._producer is None


@pytest.mark.asyncio
async def test_publish_noop_when_not_started() -> None:
    publisher = SecurityEventKafkaPublisher()
    await publisher.publish({"event_id": "e1"})


@pytest.mark.asyncio
async def test_publish_instruction_fact(monkeypatch) -> None:
    publisher = SecurityEventKafkaPublisher()
    mock_producer = MagicMock()
    mock_producer.send_and_wait = AsyncMock()
    publisher._producer = mock_producer
    await publisher.publish_instruction_fact({"actor_user_id": "u1", "instruction_id": "i1"})
    mock_producer.send_and_wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_logs_exception(monkeypatch) -> None:
    publisher = SecurityEventKafkaPublisher()
    mock_producer = MagicMock()
    mock_producer.send_and_wait = AsyncMock(side_effect=RuntimeError("kafka down"))
    publisher._producer = mock_producer
    await publisher.publish({"event_id": "e1"})
