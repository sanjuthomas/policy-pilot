from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from chat_application.models import SearchMode
from chat_application.pipeline.models import ExecutionStrategy
from chat_application.vector.reranker import RankedHit, graph_rows_to_hits


@dataclass
class SelectiveRetrievalResult:
    vector_hits: list[dict[str, Any]]
    graph_result: dict[str, Any]
    exact_hits: list[dict[str, Any]]
    graph_rows: list[dict[str, Any]]
    merged: list[RankedHit]


def _empty_graph_result() -> dict[str, Any]:
    return {
        "cypher": None,
        "rows": [],
        "cypher_provenance": "none",
        "graph_unavailable": False,
        "planned": None,
    }


async def execute_selective_retrieval(
    service: Any,
    *,
    message: str,
    mode: SearchMode,
    strategy: ExecutionStrategy,
    limit: int,
    search_source: str | None,
    event_ids: list[str],
    entity_ids: list[str],
) -> SelectiveRetrievalResult:
    """Run only the retrieval backends required for the chosen strategy."""
    run_vector = strategy in ("vector", "hybrid")
    run_graph = strategy in ("graph", "hybrid")

    vector_task = (
        asyncio.create_task(service._search_vector(message, limit, source=search_source))
        if run_vector
        else None
    )
    cypher_task = (
        asyncio.create_task(service._search_graph(message, mode=mode))
        if run_graph
        else None
    )

    exact_task = None
    instruction_exact_task = None
    payment_exact_task = None
    if run_graph:
        from chat_application.rag import _should_lookup_payment_ids

        exact_task = (
            asyncio.create_task(service._lookup_exact_event_ids(event_ids))
            if event_ids and mode != "instructions"
            else None
        )
        instruction_exact_task = (
            asyncio.create_task(service._lookup_exact_instruction_ids(entity_ids, message))
            if entity_ids and mode == "instructions"
            else None
        )
        payment_exact_task = (
            asyncio.create_task(service._lookup_exact_payment_ids(entity_ids, message))
            if entity_ids and _should_lookup_payment_ids(message, entity_ids, mode)
            else None
        )

    vector_hits: list[dict[str, Any]] = []
    graph_result = _empty_graph_result()

    if vector_task is not None:
        vector_hits = await vector_task
    if cypher_task is not None:
        graph_result = await cypher_task

    exact_hits: list[dict[str, Any]] = []
    exact_graph_rows: list[dict[str, Any]] = []
    if exact_task is not None:
        exact_hits, exact_graph_rows = await exact_task
    if instruction_exact_task is not None:
        exact_hits.extend(await instruction_exact_task)
    if payment_exact_task is not None:
        exact_hits.extend(await payment_exact_task)

    graph_rows = list(exact_graph_rows)
    seen_graph = {json.dumps(row, sort_keys=True, default=str) for row in graph_rows}
    for row in graph_result["rows"]:
        key = json.dumps(row, sort_keys=True, default=str)
        if key not in seen_graph:
            graph_rows.append(row)
            seen_graph.add(key)
    graph_result = {**graph_result, "rows": graph_rows}

    if run_graph:
        graph_hits = graph_rows_to_hits(graph_result["rows"])
        merged = service._merge_with_exact(exact_hits, vector_hits, graph_hits)
    elif run_vector:
        merged = service._merge_with_exact(exact_hits, vector_hits, [])
    else:
        merged = []

    return SelectiveRetrievalResult(
        vector_hits=vector_hits,
        graph_result=graph_result,
        exact_hits=exact_hits,
        graph_rows=graph_rows,
        merged=merged,
    )
