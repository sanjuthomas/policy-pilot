"""YAML-parity entity detail intents (status / creator by id).

ssi-chat matches these via neo4j_direct.yaml before plan_graph_queries; the bridge
reproduces the same CypherQueryBuilder.payment_detail / instruction_detail path.

Mode is ignored when a payment/instruction id is present — parity with Python
``_intent_mode_applies`` (ID-based lookups work from Events / Policies / any UI mode).
"""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version

from cypher_builder import (
    CypherQueryBuilder,
    extract_instruction_ids,
    extract_payment_ids,
    normalize_read_only_cypher,
)

from cbs.models import PlannedQuery, PlanRequest, PlanResponse


def _builder_version() -> str:
    try:
        return version("cypher-builder")
    except PackageNotFoundError:
        return "unknown"

_STATUS_RE = re.compile(
    r"(?i)\b(what is|what's)\s+the\s+status\b|\bstatus of\b"
)
_CREATOR_RE = re.compile(r"(?i)\b(who|which user)\s+created\b")
_APPROVE_RE = re.compile(r"(?i)\bapprov")
_APPROVER_RE = re.compile(r"(?i)\bwho\s+approv")
_WHO_CAN_APPROVE_RE = re.compile(r"(?i)\bwho\s+can\s+approv")

_BUILDER = CypherQueryBuilder()


def plan_entity_detail(request: PlanRequest) -> PlanResponse | None:
    question = request.question
    payment_ids = extract_payment_ids(question)
    instruction_ids = extract_instruction_ids(question)

    if _STATUS_RE.search(question):
        if payment_ids:
            return _detail_response(
                "payment.status_by_id",
                _BUILDER.payment_detail(payment_ids[0]),
            )
        if instruction_ids:
            return _detail_response(
                "instruction.status_by_id",
                _BUILDER.instruction_detail(instruction_ids[0]),
            )

    if _CREATOR_RE.search(question) and not _APPROVE_RE.search(question):
        if payment_ids:
            return _detail_response(
                "payment.creator_by_id",
                _BUILDER.payment_detail(payment_ids[0]),
            )
        if instruction_ids:
            return _detail_response(
                "instruction.creator_by_id",
                _BUILDER.instruction_detail(instruction_ids[0]),
            )

    # Past-tense audit ("who approved") — fallback when plan_graph_queries misses (e.g. mode=all).
    if _APPROVER_RE.search(question) and not _WHO_CAN_APPROVE_RE.search(question):
        if payment_ids:
            return _detail_response(
                "payment.approver_by_id",
                _BUILDER.payment_approval_lookup(payment_ids[0]),
            )
        if instruction_ids:
            return _detail_response(
                "instruction.approver_by_id",
                _BUILDER.instruction_approval_lookup(instruction_ids[0]),
            )

    return None


def _detail_response(
    intent_id: str, planned: list[tuple[str, str]] | None
) -> PlanResponse | None:
    if not planned:
        return None
    queries = [
        PlannedQuery(label=label, cypher=normalize_read_only_cypher(cypher))
        for label, cypher in planned
    ]
    return PlanResponse(
        matched=True,
        intent_id=intent_id,
        strategy="neo4j_direct",
        planned=queries,
        meta={
            "cypher_class": "deterministic",
            "builder_version": _builder_version(),
            "plan_labels": [q.label for q in queries],
            "source": "entity_detail",
        },
    )
