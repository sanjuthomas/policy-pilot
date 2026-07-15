from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiokafka import AIOKafkaConsumer
from telemetry.redaction import redact_value

from etl.config import settings
from etl.dlq.models import PipelineKind
from etl.dlq.pause import pause_registry
from etl.dlq.runtime import process_kafka_message
from etl.dlq.store import DlqStore
from etl.instruction_consumer import _estimated_lag
from etl.instruction_security_event_pipeline import InstructionSecurityEventPipeline
from etl.kafka_deserialize import deserialize_kafka_json
from etl.mongo_cdc import normalize_security_event

logger = logging.getLogger(__name__)

CONSUMER_NAME = "instruction_security_event"


class InstructionSecurityEventKafkaConsumer:
    """Consumes instruction security events from the instruction_security_events topic."""

    def __init__(
        self,
        pipeline: InstructionSecurityEventPipeline,
        dlq: DlqStore,
    ) -> None:
        self.pipeline = pipeline
        self.dlq = dlq
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None
        pause_registry.register_replay(
            PipelineKind.INSTRUCTION_SECURITY_EVENT,
            self._replay,
        )

    async def _replay(self, payload: dict[str, Any]) -> None:
        await self._handle_message(payload)

    async def start(self) -> None:
        if not settings.kafka_enabled:
            logger.info("Instruction security event Kafka consumer disabled")
            return

        self._consumer = AIOKafkaConsumer(
            settings.kafka_instruction_security_events_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_instruction_security_events_consumer_group,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=deserialize_kafka_json,
        )
        await self._consumer.start()
        self._task = asyncio.create_task(self._run())
        logger.info(
            "Instruction security event Kafka consumer started topic=%s group=%s",
            settings.kafka_instruction_security_events_topic,
            settings.kafka_instruction_security_events_consumer_group,
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
                    pipeline_kind=PipelineKind.INSTRUCTION_SECURITY_EVENT,
                    consumer_group=settings.kafka_instruction_security_events_consumer_group,
                    topic=settings.kafka_instruction_security_events_topic,
                    handler=self._handle_message,
                    dlq=self.dlq,
                )
        except asyncio.CancelledError:
            raise

    async def _handle_message(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            logger.warning("skipping invalid Kafka payload: %s", redact_value(payload))
            return
        event = normalize_security_event(payload)
        if "event_id" not in event:
            logger.warning("skipping invalid Kafka payload: %s", redact_value(payload))
            return
        await self.pipeline.process_instruction_security_event(event)
