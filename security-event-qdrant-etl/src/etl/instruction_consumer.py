from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from aiokafka import AIOKafkaConsumer

from etl.config import settings
from etl.instruction_pipeline import InstructionPipeline

logger = logging.getLogger(__name__)


class InstructionKafkaConsumer:
    """Consumes InstructionFact events from the ssi-instructions topic."""

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
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
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
                try:
                    await self._handle_message(message.value)
                    await self._consumer.commit()
                except Exception:
                    logger.exception(
                        "failed to process instruction fact offset=%s partition=%s — skipping",
                        message.offset,
                        message.partition,
                    )
        except asyncio.CancelledError:
            raise

    async def _handle_message(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict) or "instruction_id" not in payload:
            logger.warning("skipping invalid instruction fact payload: %s", payload)
            return
        await self.pipeline.process_instruction_fact(payload)
