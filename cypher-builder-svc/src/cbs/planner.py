from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from cypher_builder import (
    normalize_read_only_cypher,
    plan_graph_queries,
    validate_read_only_cypher,
)

from cbs.models import (
    PlannedQuery,
    PlanRequest,
    PlanResponse,
    ValidateRequest,
    ValidateResponse,
)


def builder_version() -> str:
    try:
        return version("cypher-builder")
    except PackageNotFoundError:
        return "unknown"


def plan(request: PlanRequest) -> PlanResponse:
    planned = plan_graph_queries(request.question, mode=request.mode)
    if not planned:
        return PlanResponse(
            matched=False,
            intent_id=None,
            strategy=None,
            planned=[],
            meta={"builder_version": builder_version()},
        )

    queries = [
        PlannedQuery(label=label, cypher=normalize_read_only_cypher(cypher))
        for label, cypher in planned
    ]
    # Parity with ssi-chat match_planned_graph_intent (heuristic plan_graph_queries path).
    return PlanResponse(
        matched=True,
        intent_id="planned_graph",
        strategy="neo4j_direct",
        planned=queries,
        meta={
            "cypher_class": "deterministic",
            "builder_version": builder_version(),
            "plan_labels": [q.label for q in queries],
        },
    )


def validate(request: ValidateRequest) -> ValidateResponse:
    try:
        validate_read_only_cypher(request.cypher)
        normalized = normalize_read_only_cypher(request.cypher)
        return ValidateResponse(ok=True, cypher=normalized, error=None)
    except ValueError as exc:
        return ValidateResponse(ok=False, cypher=None, error=str(exc))
