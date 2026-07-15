from __future__ import annotations

from typing import Any

from etl.config import settings
from etl.dlq.pause import pause_registry
from etl.dlq.store import DlqStore
from etl.instruction_consumer import CONSUMER_NAME as INSTRUCTION_FACT_NAME
from etl.instruction_consumer import InstructionKafkaConsumer
from etl.instruction_security_event_consumer import (
    CONSUMER_NAME as INSTRUCTION_SE_NAME,
)
from etl.instruction_security_event_consumer import (
    InstructionSecurityEventKafkaConsumer,
)
from etl.kafka_offsets import consumer_group_row
from etl.payment_consumer import (
    PaymentFactKafkaConsumer,
    PaymentSecurityEventKafkaConsumer,
)


async def index_integrity_status(
    *,
    dlq: DlqStore,
    instruction_security_event_consumer: InstructionSecurityEventKafkaConsumer,
    instruction_consumer: InstructionKafkaConsumer,
    payment_security_event_consumer: PaymentSecurityEventKafkaConsumer,
    payment_fact_consumer: PaymentFactKafkaConsumer,
) -> dict[str, Any]:
    """Public honesty signal for chat banner + ops."""
    consumer_groups = await kafka_consumer_groups_status(
        instruction_security_event_consumer=instruction_security_event_consumer,
        instruction_consumer=instruction_consumer,
        payment_security_event_consumer=payment_security_event_consumer,
        payment_fact_consumer=payment_fact_consumer,
    )
    lags = {row["name"]: int(row.get("lag_total") or 0) for row in consumer_groups}
    total_lag = sum(lags.values())
    dlq_stats = await dlq.stats()
    consumers = pause_registry.snapshot()
    any_paused = pause_registry.any_paused()
    threshold = settings.index_lag_banner_threshold
    show_banner = any_paused or total_lag > threshold or int(dlq_stats.get("depth") or 0) > 0
    message = None
    if show_banner:
        if any_paused:
            message = (
                "Investigation indexing is paused because the dead-letter store is "
                "unavailable. Security-event answers may be incomplete until indexing resumes."
            )
        elif total_lag > threshold:
            message = (
                f"Investigation index is behind (Kafka lag {total_lag} > {threshold}). "
                "Counts and timelines may under-report until the indexer catches up."
            )
        else:
            message = (
                f"Investigation dead-letter queue has {dlq_stats.get('depth')} "
                "unresolved item(s). Some events may not yet appear in search results."
            )
    return {
        "kafka_lag_total": total_lag,
        "kafka_lag_by_consumer": lags,
        "lag_banner_threshold": threshold,
        "consumer_paused": any_paused,
        "consumers": consumers,
        "consumer_groups": consumer_groups,
        "dlq": {
            "depth": dlq_stats.get("depth", 0),
            "by_status": dlq_stats.get("by_status", {}),
            "oldest_pending_age_seconds": dlq_stats.get("oldest_pending_age_seconds"),
            "connected": dlq_stats.get("connected", False),
            "enabled": dlq_stats.get("enabled", False),
        },
        "show_banner": show_banner,
        "banner_message": message,
    }


async def kafka_consumer_groups_status(
    *,
    instruction_security_event_consumer: InstructionSecurityEventKafkaConsumer,
    instruction_consumer: InstructionKafkaConsumer,
    payment_security_event_consumer: PaymentSecurityEventKafkaConsumer,
    payment_fact_consumer: PaymentFactKafkaConsumer,
) -> list[dict[str, Any]]:
    """Topic / group / per-partition offset metadata for all indexer consumers."""
    if not settings.kafka_enabled:
        return []

    specs = [
        (
            INSTRUCTION_SE_NAME,
            settings.kafka_instruction_security_events_topic,
            settings.kafka_instruction_security_events_consumer_group,
            instruction_security_event_consumer,
        ),
        (
            INSTRUCTION_FACT_NAME,
            settings.kafka_instruction_topic,
            settings.kafka_instruction_consumer_group,
            instruction_consumer,
        ),
        (
            "payment_security_event",
            settings.kafka_payment_security_events_topic,
            settings.kafka_payment_security_events_consumer_group,
            payment_security_event_consumer,
        ),
        (
            "payment_fact",
            settings.kafka_payments_topic,
            settings.kafka_payments_consumer_group,
            payment_fact_consumer,
        ),
    ]
    rows: list[dict[str, Any]] = []
    for name, topic, group, consumer_obj in specs:
        rows.append(
            await consumer_group_row(
                name=name,
                topic=topic,
                consumer_group=group,
                consumer=getattr(consumer_obj, "_consumer", None),
                task_running=bool(consumer_obj.is_task_running()),
            )
        )
    return rows
