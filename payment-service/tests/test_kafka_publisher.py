from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from ps.kafka_publisher import PaymentKafkaPublisher


@pytest.mark.asyncio
async def test_start_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.kafka_publisher.settings.kafka_enabled", False)
    publisher = PaymentKafkaPublisher()
    await publisher.start()
    assert publisher._producer is None


@pytest.mark.asyncio
async def test_start_and_close_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.kafka_publisher.settings.kafka_enabled", True)
    publisher = PaymentKafkaPublisher()
    mock_producer = AsyncMock()

    with patch("ps.kafka_publisher.AIOKafkaProducer", return_value=mock_producer):
        await publisher.start()
        assert publisher._producer is mock_producer
        mock_producer.start.assert_awaited_once()
        await publisher.close()
        mock_producer.stop.assert_awaited_once()
        assert publisher._producer is None


@pytest.mark.asyncio
async def test_publish_payment_no_producer() -> None:
    publisher = PaymentKafkaPublisher()
    await publisher.publish_payment({"payment_id": "p1"})


@pytest.mark.asyncio
async def test_publish_payment_success() -> None:
    publisher = PaymentKafkaPublisher()
    mock_producer = AsyncMock()
    publisher._producer = mock_producer
    await publisher.publish_payment({"payment_id": "p1"})
    mock_producer.send_and_wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_payment_swallows_errors() -> None:
    publisher = PaymentKafkaPublisher()
    mock_producer = AsyncMock()
    mock_producer.send_and_wait.side_effect = RuntimeError("kafka down")
    publisher._producer = mock_producer
    await publisher.publish_payment({"payment_id": "p1"})


@pytest.mark.asyncio
async def test_publish_security_event_no_producer() -> None:
    publisher = PaymentKafkaPublisher()
    await publisher.publish_security_event({"event_id": "e1"})


@pytest.mark.asyncio
async def test_publish_security_event_success() -> None:
    publisher = PaymentKafkaPublisher()
    mock_producer = AsyncMock()
    publisher._producer = mock_producer
    await publisher.publish_security_event({"event_id": "e1"})
    mock_producer.send_and_wait.assert_awaited_once()
