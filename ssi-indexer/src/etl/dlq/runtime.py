from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from etl.config import settings
from etl.dlq.classify import classify_exception, is_retryable
from etl.dlq.metrics import record_dlq_event
from etl.dlq.models import DlqStatus, FailureClass, PipelineKind
from etl.dlq.pause import pause_registry
from etl.dlq.store import DlqStore

logger = logging.getLogger(__name__)

Handler = Callable[[Any], Awaitable[None]]


def extract_ids(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    event_id = payload.get("event_id") or payload.get("_id")
    if event_id is not None:
        event_id = str(event_id)
    entity_id = (
        payload.get("instruction_id")
        or payload.get("payment_id")
        or payload.get("entity_id")
    )
    if entity_id is not None:
        entity_id = str(entity_id)
    return event_id, entity_id


async def process_kafka_message(
    *,
    message: Any,
    consumer: Any,
    consumer_name: str,
    pipeline_kind: PipelineKind,
    consumer_group: str,
    topic: str,
    handler: Handler,
    dlq: DlqStore,
) -> None:
    """Process one Kafka message with retry, DLQ quarantine, and pause-on-DLQ-fail."""
    payload = message.value if isinstance(message.value, dict) else {"raw": message.value}
    event_id, entity_id = extract_ids(payload) if isinstance(payload, dict) else (None, None)
    max_attempts = max(1, settings.kafka_retry_max_attempts)
    base_delay = settings.kafka_retry_base_delay_seconds

    while True:
        while pause_registry.is_paused(consumer_name):
            await asyncio.sleep(settings.dlq_pause_poll_seconds)
            if dlq.enabled and await dlq.ping():
                pause_registry.clear_paused(consumer_name)
                logger.info("consumer resumed after DLQ recovered name=%s", consumer_name)
                record_dlq_event("etl.consumer.resume", consumer=consumer_name)

        last_exc: BaseException | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                await handler(message.value)
                await consumer.commit()
                record_dlq_event(
                    "etl.consumer.processed",
                    consumer=consumer_name,
                    pipeline=str(pipeline_kind),
                )
                return
            except Exception as exc:  # noqa: BLE001 — quarantine boundary
                last_exc = exc
                failure_class = classify_exception(exc)
                if is_retryable(exc) and attempt < max_attempts:
                    delay = min(
                        base_delay * (2 ** (attempt - 1)),
                        settings.kafka_retry_max_delay_seconds,
                    )
                    logger.warning(
                        "retryable failure consumer=%s offset=%s attempt=%s/%s "
                        "delay=%.2fs error=%s",
                        consumer_name,
                        message.offset,
                        attempt,
                        max_attempts,
                        delay,
                        exc,
                    )
                    record_dlq_event(
                        "etl.consumer.retry",
                        consumer=consumer_name,
                        pipeline=str(pipeline_kind),
                        failure_class=str(failure_class),
                    )
                    await asyncio.sleep(delay)
                    continue
                break

        assert last_exc is not None
        failure_class = classify_exception(last_exc)

        logger.exception(
            "processing failed consumer=%s topic=%s partition=%s offset=%s "
            "failure_class=%s — quarantining",
            consumer_name,
            topic,
            message.partition,
            message.offset,
            failure_class,
        )
        record_dlq_event(
            "etl.consumer.failed",
            consumer=consumer_name,
            pipeline=str(pipeline_kind),
            failure_class=str(failure_class),
        )

        if not dlq.enabled or dlq._col is None:
            pause_registry.set_paused(consumer_name, reason="dlq_unavailable")
            record_dlq_event("etl.consumer.paused", consumer=consumer_name, reason="dlq_unavailable")
            logger.error(
                "DLQ unavailable — pausing consumer=%s (will not advance offset)",
                consumer_name,
            )
            continue

        try:
            await dlq.insert_failure(
                pipeline_kind=pipeline_kind,
                consumer_name=consumer_name,
                topic=topic,
                partition=int(message.partition),
                offset=int(message.offset),
                consumer_group=consumer_group,
                payload=payload if isinstance(payload, dict) else {"raw": payload},
                event_id=event_id,
                entity_id=entity_id,
                failure_class=failure_class,
                error_message=str(last_exc),
                stage="process",
                realtime_attempts=max_attempts,
                status=(
                    DlqStatus.POISON
                    if failure_class == FailureClass.POISON
                    else DlqStatus.PENDING
                ),
            )
            await consumer.commit()
            record_dlq_event(
                "etl.dlq.quarantined",
                consumer=consumer_name,
                pipeline=str(pipeline_kind),
                failure_class=str(failure_class),
            )
            return
        except Exception as dlq_exc:  # noqa: BLE001
            pause_registry.set_paused(consumer_name, reason="dlq_write_failed")
            record_dlq_event(
                "etl.consumer.paused",
                consumer=consumer_name,
                reason="dlq_write_failed",
            )
            logger.exception(
                "DLQ write failed — pausing consumer=%s error=%s",
                consumer_name,
                dlq_exc,
            )
