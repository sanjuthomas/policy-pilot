from __future__ import annotations

import asyncio
import logging
from typing import Any

from vertex_client import VertexEmbeddingClient

from etl.config import settings
from etl.instruction_security_event_consumer import (
    InstructionSecurityEventKafkaConsumer,
)
from etl.multimodal_store import MultimodalNeo4jStore
from etl.neo4j_client import Neo4jGraphWriter

logger = logging.getLogger(__name__)

ComponentStatus = dict[str, Any]


def _status(ok: bool, status: str, **extra: Any) -> ComponentStatus:
    return {"ok": ok, "status": status, **extra}


async def check_kafka(
    instruction_security_event_consumer: InstructionSecurityEventKafkaConsumer,
) -> ComponentStatus:
    base = {
        "bootstrap_servers": settings.kafka_bootstrap_servers,
        "topic": settings.kafka_instruction_security_events_topic,
        "consumer_group": settings.kafka_instruction_security_events_consumer_group,
    }
    if not settings.kafka_enabled:
        return _status(True, "disabled", detail="Kafka consumer disabled", **base)

    if (
        instruction_security_event_consumer._consumer is None
        or instruction_security_event_consumer._task is None
    ):
        return _status(False, "down", detail="consumer not started", **base)

    if instruction_security_event_consumer._task.done():
        exc = instruction_security_event_consumer._task.exception()
        return _status(
            False,
            "down",
            detail=str(exc) if exc else "consumer task stopped",
            **base,
        )

    try:
        cluster = instruction_security_event_consumer._consumer._client.cluster
        broker_count = len(cluster.brokers()) if cluster else 0
    except Exception as exc:
        logger.warning("kafka cluster metadata unavailable: %s", exc)
        broker_count = None

    return _status(
        True,
        "up",
        consumer="running",
        brokers=broker_count,
        **base,
    )


async def _index_exists(neo4j_writer: Neo4jGraphWriter, name: str) -> bool:
    if neo4j_writer._driver is None:
        return False
    async with neo4j_writer._driver.session() as session:
        result = await session.run(
            "SHOW INDEXES YIELD name WHERE name = $name RETURN name",
            name=name,
        )
        record = await result.single()
    return record is not None


async def check_multimodal_vector(
    multimodal_store: MultimodalNeo4jStore,
) -> ComponentStatus:
    base = {
        "store": "neo4j_multimodal",
        "vector_index": settings.multimodal_vector_index,
    }
    try:
        exists = await _index_exists(multimodal_store._writer, settings.multimodal_vector_index)
        count = await multimodal_store.document_count()
        if not exists:
            return _status(
                False,
                "empty",
                detail="vector index not created yet",
                documents_count=count,
                **base,
            )
        return _status(True, "up", documents_count=count, **base)
    except Exception as exc:
        logger.warning("multimodal vector health check failed: %s", exc)
        return _status(False, "down", detail=str(exc), **base)


async def check_multimodal_fulltext(
    multimodal_store: MultimodalNeo4jStore,
) -> ComponentStatus:
    base = {
        "store": "neo4j_multimodal",
        "fulltext_index": settings.multimodal_fulltext_index,
    }
    try:
        exists = await _index_exists(multimodal_store._writer, settings.multimodal_fulltext_index)
        count = await multimodal_store.document_count()
        if not exists:
            return _status(
                False,
                "empty",
                detail="fulltext index not created yet",
                documents_count=count,
                **base,
            )
        return _status(True, "up", documents_count=count, **base)
    except Exception as exc:
        logger.warning("multimodal fulltext health check failed: %s", exc)
        return _status(False, "down", detail=str(exc), **base)


async def check_vertex_embeddings(
    embedding_client: VertexEmbeddingClient,
) -> ComponentStatus:
    base = {
        "project": settings.gcp_project_id,
        "region": settings.gcp_region,
        "model": settings.vertex_embedding_model,
    }
    try:
        dimension = embedding_client._dimension
        extra: dict[str, Any] = {}
        if embedding_client._ready and dimension is not None:
            extra["dimension"] = dimension
            extra["embeddings"] = "ready"
            return _status(True, "up", **base, **extra)
        return _status(
            False,
            "down",
            detail="embeddings not warmed up yet",
            **base,
        )
    except Exception as exc:
        logger.warning("vertex embedding health check failed: %s", exc)
        return _status(False, "down", detail=str(exc), **base)


async def check_neo4j(neo4j_writer: Neo4jGraphWriter) -> ComponentStatus:
    base = {"uri": settings.neo4j_uri}
    if neo4j_writer._driver is None:
        return _status(False, "down", detail="driver not connected", **base)

    try:
        await neo4j_writer._driver.verify_connectivity()
        async with neo4j_writer._driver.session() as session:
            result = await session.run("RETURN 1 AS ok")
            await result.single()

        stats = await neo4j_writer.graph_stats()
        total_nodes = sum(stats.values())
        return _status(
            True,
            "up",
            total_nodes=total_nodes,
            labels=stats,
            **base,
        )
    except Exception as exc:
        logger.warning("neo4j health check failed: %s", exc)
        return _status(False, "down", detail=str(exc), **base)


async def component_status(
    *,
    instruction_security_event_consumer: InstructionSecurityEventKafkaConsumer,
    multimodal_store: MultimodalNeo4jStore,
    neo4j_writer: Neo4jGraphWriter,
    embedding_client: VertexEmbeddingClient,
) -> dict[str, ComponentStatus]:
    (
        kafka_status,
        neo4j_status,
        vertex_status,
        vector_status,
        fulltext_status,
    ) = await asyncio.gather(
        check_kafka(instruction_security_event_consumer),
        check_neo4j(neo4j_writer),
        check_vertex_embeddings(embedding_client),
        check_multimodal_vector(multimodal_store),
        check_multimodal_fulltext(multimodal_store),
    )
    return {
        "kafka": kafka_status,
        "vertex_embeddings": vertex_status,
        "multimodal_vector": vector_status,
        "multimodal_fulltext": fulltext_status,
        "neo4j": neo4j_status,
    }
