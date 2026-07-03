from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiokafka import AIOKafkaConsumer
from neo4j.exceptions import TransientError

from etl.config import settings
from etl.instruction_pipeline import InstructionPipeline
from etl.kafka_deserialize import deserialize_kafka_json
from etl.mongo_cdc import normalize_instruction_message

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5
_RETRY_BASE_DELAY = 0.2  # seconds


class InstructionKafkaConsumer:
    """Consumes InstructionFact events from the instructions topic."""

    def __init__(self, pipeline: InstructionPipeline) -> None:
        self.pipeline = pipeline
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if not settings.kafka_enabled:
            logger.info("Instruction Kafka consumer disabled")
            return

        self._consumer = AIOKafkaConsumer(
            settings.kafka_instruction_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_instruction_consumer_group,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=deserialize_kafka_json,
        )
        await self._consumer.start()
        self._task = asyncio.create_task(self._run())
        logger.info(
            "Instruction Kafka consumer started topic=%s group=%s",
            settings.kafka_instruction_topic,
            settings.kafka_instruction_consumer_group,
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
                                "Neo4j transient error (deadlock) offset=%s partition=%s "
                                "attempt=%s/%s — retrying in %.2fs: %s",
                                message.offset, message.partition,
                                attempt, _MAX_RETRIES, delay, exc,
                            )
                            await asyncio.sleep(delay)
                        else:
                            logger.exception(
                                "Neo4j transient error persists after %s retries "
                                "offset=%s partition=%s — skipping",
                                _MAX_RETRIES, message.offset, message.partition,
                            )
                    except Exception:
                        logger.exception(
                            "failed to process instruction fact offset=%s partition=%s — skipping",
                            message.offset,
                            message.partition,
                        )
                        break
        except asyncio.CancelledError:
            raise

    async def _handle_message(self, payload: dict[str, Any]) -> None:
        fact = normalize_instruction_message(payload)
        if not isinstance(fact, dict) or "instruction_id" not in fact:
            logger.warning("skipping invalid instruction fact payload: %s", payload)
            return
        await self.pipeline.process_instruction_fact(fact)
