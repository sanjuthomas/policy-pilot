from __future__ import annotations

import asyncio
import logging

from aiokafka import AIOKafkaConsumer

from etl.config import settings
from etl.dlq.models import PipelineKind
from etl.dlq.pause import pause_registry
from etl.dlq.runtime import process_kafka_message
from etl.dlq.store import DlqStore
from etl.instruction_pipeline import InstructionPipeline
from etl.kafka_deserialize import deserialize_kafka_json
from etl.kafka_offsets import estimated_lag as _estimated_lag
from etl.mongo_cdc import normalize_instruction_message

logger = logging.getLogger(__name__)

CONSUMER_NAME = "instruction_fact"


class InstructionKafkaConsumer:
    """Consumes instruction fact CDC from the instructions topic."""

    def __init__(self, pipeline: InstructionPipeline, dlq: DlqStore) -> None:
        self.pipeline = pipeline
        self.dlq = dlq
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None
        pause_registry.register_replay(
            PipelineKind.INSTRUCTION_FACT,
            self._replay,
        )

    async def _replay(self, payload: dict) -> None:
        await self._handle_message(payload)

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

    async def estimated_lag(self) -> int:
        return await _estimated_lag(self._consumer)

    async def _run(self) -> None:
        assert self._consumer is not None
        try:
            async for message in self._consumer:
                await process_kafka_message(
                    message=message,
                    consumer=self._consumer,
                    consumer_name=CONSUMER_NAME,
                    pipeline_kind=PipelineKind.INSTRUCTION_FACT,
                    consumer_group=settings.kafka_instruction_consumer_group,
                    topic=settings.kafka_instruction_topic,
                    handler=self._handle_message,
                    dlq=self.dlq,
                )
        except asyncio.CancelledError:
            raise

    async def _handle_message(self, payload) -> None:
        if not isinstance(payload, dict):
            logger.warning("skipping invalid instruction fact payload")
            return
        fact = normalize_instruction_message(payload)
        if not isinstance(fact, dict) or "instruction_id" not in fact:
            logger.warning("skipping invalid instruction fact payload")
            return
        await self.pipeline.process_instruction_fact(fact)

    def is_task_running(self) -> bool:
        return self._task is not None and not self._task.done()
