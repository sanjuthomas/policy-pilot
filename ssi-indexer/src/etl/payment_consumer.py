from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiokafka import AIOKafkaConsumer
from neo4j.exceptions import TransientError

from etl.config import settings
from etl.kafka_deserialize import deserialize_kafka_json
from etl.mongo_cdc import normalize_payment_message, normalize_security_event
from etl.payment_pipeline import PaymentFactPipeline, PaymentSecurityEventPipeline

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5
_RETRY_BASE_DELAY = 0.2


class PaymentSecurityEventKafkaConsumer:
    """Consumes PaymentSecurityEvent messages from the payment_security_events topic."""

    def __init__(self, pipeline: PaymentSecurityEventPipeline) -> None:
        self.pipeline = pipeline
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if not settings.kafka_enabled:
            logger.info("Payment security event Kafka consumer disabled")
            return

        self._consumer = AIOKafkaConsumer(
            settings.kafka_payment_security_events_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_payment_security_events_consumer_group,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=deserialize_kafka_json,
        )
        await self._consumer.start()
        self._task = asyncio.create_task(self._run())
        logger.info(
            "Payment security event consumer started topic=%s group=%s",
            settings.kafka_payment_security_events_topic,
            settings.kafka_payment_security_events_consumer_group,
        )

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None

    @property
    def running(self) -> bool:
        return self._consumer is not None

    async def _run(self) -> None:
        assert self._consumer is not None
        try:
            async for message in self._consumer:
                for attempt in range(1, _MAX_RETRIES + 1):
                    try:
                        await self._handle_message(message.value)
                        await self._consumer.commit()
                        break
                    except TransientError as exc:
                        if attempt < _MAX_RETRIES:
                            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                            logger.warning(
                                "Neo4j transient error offset=%s attempt=%s/%s — retrying in %.2fs: %s",
                                message.offset, attempt, _MAX_RETRIES, delay, exc,
                            )
                            await asyncio.sleep(delay)
                        else:
                            logger.exception(
                                "Neo4j transient error persists offset=%s — skipping",
                                message.offset,
                            )
                    except Exception:
                        logger.exception(
                            "failed to process payment security event offset=%s — skipping",
                            message.offset,
                        )
                        break
        except asyncio.CancelledError:
            raise

    async def _handle_message(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            logger.warning("skipping invalid payment security event payload: %s", payload)
            return
        event = normalize_security_event(payload)
        if "event_id" not in event:
            logger.warning("skipping invalid payment security event payload: %s", payload)
            return
        await self.pipeline.process(event)


class PaymentFactKafkaConsumer:
    """Consumes payment fact snapshots from the payments topic."""

    def __init__(self, pipeline: PaymentFactPipeline) -> None:
        self.pipeline = pipeline
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if not settings.kafka_enabled:
            logger.info("Payment fact Kafka consumer disabled")
            return

        self._consumer = AIOKafkaConsumer(
            settings.kafka_payments_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_payments_consumer_group,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=deserialize_kafka_json,
        )
        await self._consumer.start()
        self._task = asyncio.create_task(self._run())
        logger.info(
            "Payment fact consumer started topic=%s group=%s",
            settings.kafka_payments_topic,
            settings.kafka_payments_consumer_group,
        )

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None

    @property
    def running(self) -> bool:
        return self._consumer is not None

    async def _run(self) -> None:
        assert self._consumer is not None
        try:
            async for message in self._consumer:
                for attempt in range(1, _MAX_RETRIES + 1):
                    try:
                        await self._handle_message(message.value)
                        await self._consumer.commit()
                        break
                    except TransientError as exc:
                        if attempt < _MAX_RETRIES:
                            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                            logger.warning(
                                "Neo4j transient error offset=%s attempt=%s/%s — retrying in %.2fs: %s",
                                message.offset, attempt, _MAX_RETRIES, delay, exc,
                            )
                            await asyncio.sleep(delay)
                        else:
                            logger.exception(
                                "Neo4j transient error persists offset=%s — skipping",
                                message.offset,
                            )
                    except Exception:
                        logger.exception(
                            "failed to process payment fact offset=%s — skipping",
                            message.offset,
                        )
                        break
        except asyncio.CancelledError:
            raise

    async def _handle_message(self, payload: dict[str, Any]) -> None:
        fact = normalize_payment_message(payload)
        if not isinstance(fact, dict) or "payment_id" not in fact:
            logger.warning("skipping invalid payment fact payload: %s", payload)
            return
        await self.pipeline.process(fact)
