from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from cypher_builder import (
    normalize_read_only_cypher,
    plan_graph_queries,
    retrieval_lob_scope,
    validate_read_only_cypher,
)

from cbs.entity_plan import plan_entity_detail
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
    options = request.options
    if options is not None and options.lob_scoped:
        allowed = frozenset(
            lob.strip().upper()
            for lob in options.allowed_lobs
            if isinstance(lob, str) and lob.strip()
        )
        with retrieval_lob_scope(allowed):
            return _plan_unscoped(request)
    return _plan_unscoped(request)


def _plan_unscoped(request: PlanRequest) -> PlanResponse:
    planned = plan_graph_queries(request.question, mode=request.mode)
    if planned:
        queries = [
            PlannedQuery(label=label, cypher=normalize_read_only_cypher(cypher))
            for label, cypher in planned
        ]
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

    entity = plan_entity_detail(request)
    if entity is not None:
        return entity

    return PlanResponse(
        matched=False,
        intent_id=None,
        strategy=None,
        planned=[],
        meta={"builder_version": builder_version()},
    )


def validate(request: ValidateRequest) -> ValidateResponse:
    try:
        validate_read_only_cypher(request.cypher)
        normalized = normalize_read_only_cypher(request.cypher)
        return ValidateResponse(ok=True, cypher=normalized, error=None)
    except ValueError as exc:
        return ValidateResponse(ok=False, cypher=None, error=str(exc))
