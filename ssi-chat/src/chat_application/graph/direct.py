"""YAML-driven Neo4j-direct intent matching and execution."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import yaml

from chat_application.formatting.dispatch import format_planned_graph_answer
from chat_application.formatting.neo4j import FORMATTERS
from chat_application.graph.cypher import (
    CypherQueryBuilder,
    extract_entity_ids,
    extract_instruction_ids,
    extract_payment_ids,
    is_approval_denial_alert_list_question,
    lob_filter_from_question,
    normalize_read_only_cypher,
    plan_graph_queries,
    validate_read_only_cypher,
)
from chat_application.graph.neo4j import Neo4jClient
from chat_application.models import SearchMode

logger = logging.getLogger(__name__)
_INTENTS_PATH = Path(__file__).resolve().parent / "intents" / "neo4j_direct.yaml"
_USER_ID_PATTERN = re.compile(
    r"\b(mo|ficc|fx|rates|pay|fo|comp|admin|svc)-\d+\b",
    re.IGNORECASE,
)

QueryBuilder = Callable[[dict[str, Any], str, SearchMode], list[tuple[str, str]]]
_GRAPH_BUILDER = CypherQueryBuilder()


def _instruction_id_from_context(context: dict[str, Any]) -> str | None:
    instruction_ids = context.get("instruction_ids") or []
    return instruction_ids[0] if instruction_ids else None


def _payment_id_from_context(context: dict[str, Any]) -> str | None:
    payment_ids = context.get("payment_ids") or []
    return payment_ids[0] if payment_ids else None


def _build_instruction_detail(context: dict[str, Any], _question: str, _mode: SearchMode):
    instruction_id = _instruction_id_from_context(context)
    if not instruction_id:
        return []
    return _GRAPH_BUILDER.instruction_detail(instruction_id)


def _build_payment_detail(context: dict[str, Any], _question: str, _mode: SearchMode):
    payment_id = _payment_id_from_context(context)
    if not payment_id:
        return []
    return _GRAPH_BUILDER.payment_detail(payment_id)


def _build_instruction_approval_lookup(context: dict[str, Any], _question: str, _mode: SearchMode):
    instruction_id = _instruction_id_from_context(context)
    if not instruction_id:
        return []
    return _GRAPH_BUILDER.instruction_approval_lookup(instruction_id)


def _build_payment_approval_lookup(context: dict[str, Any], _question: str, _mode: SearchMode):
    payment_id = _payment_id_from_context(context)
    if not payment_id:
        return []
    return _GRAPH_BUILDER.payment_approval_lookup(payment_id)


def _build_instruction_list_by_type(context: dict[str, Any], question: str, _mode: SearchMode):
    from chat_application.graph.cypher import (
        instruction_status_filter_from_question,
        instruction_type_filter_from_question,
    )

    instruction_type = instruction_type_filter_from_question(question)
    if not instruction_type:
        return []
    return _GRAPH_BUILDER.instruction_list_by_type(
        instruction_type=instruction_type,
        lob=lob_filter_from_question(question),
        status=instruction_status_filter_from_question(question),
    )


def _build_instruction_list_by_status(context: dict[str, Any], question: str, _mode: SearchMode):
    from chat_application.graph.cypher import (
        instruction_status_filter_from_question,
        instruction_type_filter_from_question,
    )

    status = instruction_status_filter_from_question(question)
    if not status:
        return []
    return _GRAPH_BUILDER.instruction_list_by_status(
        status=status,
        lob=lob_filter_from_question(question),
        instruction_type=instruction_type_filter_from_question(question),
    )


def _build_instructions_created_by_user(context: dict[str, Any], _question: str, _mode: SearchMode):
    user_id = context.get("user_id")
    if not user_id:
        return []
    return _GRAPH_BUILDER.instructions_created_by_user(user_id)


def _build_instruction_mutual_approval(context: dict[str, Any], _question: str, _mode: SearchMode):
    return _GRAPH_BUILDER.instruction_mutual_approval()


def _build_cross_entity_reciprocal_approval(
    context: dict[str, Any], _question: str, _mode: SearchMode
):
    return _GRAPH_BUILDER.cross_entity_reciprocal_approval()


def _build_instruction_self_approval(context: dict[str, Any], _question: str, _mode: SearchMode):
    return _GRAPH_BUILDER.instruction_self_approval()


def _build_instruction_duplicate_routes(context: dict[str, Any], question: str, _mode: SearchMode):
    lob = lob_filter_from_question(question)
    return _GRAPH_BUILDER.instruction_duplicate_routes(lob=lob)


def _build_instruction_subordinate_approver(context: dict[str, Any], _question: str, _mode: SearchMode):
    return _GRAPH_BUILDER.instruction_subordinate_approver()


def _build_instruction_security_event_timeline(
    context: dict[str, Any], _question: str, _mode: SearchMode
):
    instruction_id = _instruction_id_from_context(context)
    if not instruction_id:
        return []
    return _GRAPH_BUILDER.instruction_security_event_timeline(instruction_id)


def _build_alert_count_today(context: dict[str, Any], _question: str, _mode: SearchMode):
    return _GRAPH_BUILDER.alert_count_today()


def _build_instruction_versions(context: dict[str, Any], _question: str, _mode: SearchMode):
    instruction_id = _instruction_id_from_context(context)
    if not instruction_id:
        return []
    return _GRAPH_BUILDER.instruction_versions(instruction_id)


def _build_payment_versions(context: dict[str, Any], _question: str, _mode: SearchMode):
    payment_id = _payment_id_from_context(context)
    if not payment_id:
        return []
    return _GRAPH_BUILDER.payment_versions(payment_id)


def _build_security_event_alert_list(context: dict[str, Any], question: str, _mode: SearchMode):
    from chat_application.graph.cypher import (
        security_event_domain_from_question,
        security_event_time_filter_from_question,
    )

    approval_only = is_approval_denial_alert_list_question(question)
    return _GRAPH_BUILDER.security_event_alert_list(
        time_filter=security_event_time_filter_from_question(question),
        domain=security_event_domain_from_question(question),
        approval_only=approval_only,
    )


QUERY_BUILDERS: dict[str, QueryBuilder] = {
    "instruction_detail_by_id": _build_instruction_detail,
    "instruction_versions_by_id": _build_instruction_versions,
    "payment_detail_by_id": _build_payment_detail,
    "payment_versions_by_id": _build_payment_versions,
    "instruction_approval_lookup": _build_instruction_approval_lookup,
    "payment_approval_lookup": _build_payment_approval_lookup,
    "instruction_list_by_type": _build_instruction_list_by_type,
    "instruction_list_by_status": _build_instruction_list_by_status,
    "instructions_created_by_user": _build_instructions_created_by_user,
    "instruction_mutual_approval": _build_instruction_mutual_approval,
    "cross_entity_reciprocal_approval": _build_cross_entity_reciprocal_approval,
    "instruction_self_approval": _build_instruction_self_approval,
    "instruction_duplicate_routes": _build_instruction_duplicate_routes,
    "instruction_subordinate_approver": _build_instruction_subordinate_approver,
    "instruction_security_event_timeline": _build_instruction_security_event_timeline,
    "alert_count_today": _build_alert_count_today,
    "security_event_alert_list": _build_security_event_alert_list,
}


@dataclass(frozen=True)
class Neo4jDirectMatch:
    intent_id: str
    planned: list[tuple[str, str]]
    formatter_name: str
    source: str = "yaml"


@dataclass(frozen=True)
class Neo4jDirectResult:
    answer: str
    cypher: str | None
    graph_rows: list[dict[str, Any]]
    intent_id: str
    source: str = "yaml"


@lru_cache(maxsize=1)
def load_neo4j_direct_intents() -> list[dict[str, Any]]:
    if not _INTENTS_PATH.is_file():
        logger.warning("neo4j direct intents file not found: %s", _INTENTS_PATH)
        return []
    with _INTENTS_PATH.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    return list(payload.get("intents") or [])


def extract_user_ids(text: str) -> list[str]:
    return list(dict.fromkeys(match.group(0) for match in _USER_ID_PATTERN.finditer(text)))


def build_match_context(question: str) -> dict[str, Any]:
    from cypher_builder.entity_id import find_entity_ids

    parsed = find_entity_ids(question)
    instruction_ids = [p.normalized for p in parsed if p.is_instruction]
    payment_ids = [p.normalized for p in parsed if p.is_payment]
    # Legacy UUID / odd tokens still surface via extract_entity_ids when no I/P code.
    if not instruction_ids and not payment_ids:
        instruction_ids = list(extract_instruction_ids(question))
        if not instruction_ids:
            mentions_instruction = bool(re.search(r"\binstruction\b", question, re.IGNORECASE))
            for entity_id in extract_entity_ids(question):
                if "-I-" in entity_id.upper():
                    instruction_ids.append(entity_id)
                elif mentions_instruction and "-P-" not in entity_id.upper():
                    instruction_ids.append(entity_id)
            instruction_ids = list(dict.fromkeys(instruction_ids))
        payment_ids = extract_payment_ids(question) or [
            entity_id
            for entity_id in extract_entity_ids(question)
            if "-P-" in entity_id.upper()
        ]
    user_ids = extract_user_ids(question)
    return {
        "instruction_ids": instruction_ids,
        "payment_ids": payment_ids,
        "user_id": user_ids[0] if user_ids else None,
        "entity_stories": [p.story() for p in parsed],
    }


def _requirements_met(requirements: dict[str, Any] | None, context: dict[str, Any]) -> bool:
    if not requirements:
        return True
    if requirements.get("instruction_id") and not context.get("instruction_ids"):
        return False
    if requirements.get("payment_id") and not context.get("payment_ids"):
        return False
    if requirements.get("user_id") and not context.get("user_id"):
        return False
    return True


def _intent_mode_applies(
    intent_modes: list[str],
    mode: SearchMode,
    requirements: dict[str, Any] | None,
    context: dict[str, Any],
) -> bool:
    if mode in intent_modes:
        return True
    # When the question names a specific instruction or payment ID, honor the
    # graph intent regardless of the UI search-mode radio (default is Events).
    if requirements:
        if requirements.get("instruction_id") and context.get("instruction_ids"):
            return True
        if requirements.get("payment_id") and context.get("payment_ids"):
            return True
    return False


def match_neo4j_direct_intent(question: str, *, mode: SearchMode) -> Neo4jDirectMatch | None:
    context = build_match_context(question)
    candidates: list[tuple[int, dict[str, Any]]] = []

    for intent in load_neo4j_direct_intents():
        modes = intent.get("modes") or []
        if not _intent_mode_applies(modes, mode, intent.get("requires"), context):
            continue
        match_pattern = intent.get("match")
        if not match_pattern or not re.search(match_pattern, question, re.IGNORECASE):
            continue
        exclude = intent.get("exclude")
        if exclude and re.search(exclude, question, re.IGNORECASE):
            continue
        if not _requirements_met(intent.get("requires"), context):
            continue
        query_key = intent.get("query")
        formatter_name = intent.get("formatter")
        if not query_key or not formatter_name:
            continue
        if query_key not in QUERY_BUILDERS:
            logger.warning("unknown neo4j direct query key: %s", query_key)
            continue
        if formatter_name not in FORMATTERS:
            logger.warning("unknown neo4j direct formatter: %s", formatter_name)
            continue
        builder = QUERY_BUILDERS[query_key]
        planned = builder(context, question, mode)
        if not planned:
            continue
        priority = int(intent.get("priority") or 50)
        candidates.append((priority, intent))

    if not candidates:
        return None

    _, intent = max(candidates, key=lambda item: item[0])
    query_key = str(intent["query"])
    builder = QUERY_BUILDERS[query_key]
    planned = builder(context, question, mode)
    return Neo4jDirectMatch(
        intent_id=str(intent["id"]),
        planned=planned,
        formatter_name=str(intent["formatter"]),
        source="yaml",
    )


def match_planned_graph_intent(question: str, *, mode: SearchMode) -> Neo4jDirectMatch | None:
    planned = plan_graph_queries(question, mode=mode)
    if not planned:
        return None
    return Neo4jDirectMatch(
        intent_id="planned_graph",
        planned=planned,
        formatter_name="planned_graph",
        source="planned",
    )


async def run_neo4j_direct_queries(
    neo4j: Neo4jClient,
    match: Neo4jDirectMatch,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    cyphers: list[str] = []
    for _label, query in match.planned:
        normalized = normalize_read_only_cypher(query)
        validate_read_only_cypher(normalized)
        cyphers.append(normalized)
        rows.extend(await neo4j.run_cypher(normalized))
    return rows, cyphers


def format_neo4j_direct_answer(
    match: Neo4jDirectMatch,
    question: str,
    rows: list[dict[str, Any]],
    *,
    mode: SearchMode,
) -> str | None:
    if match.formatter_name == "planned_graph":
        return format_planned_graph_answer(question, mode=mode, planned=match.planned, rows=rows)
    formatter = FORMATTERS.get(match.formatter_name)
    if formatter is None:
        return None
    return formatter(question, rows)


async def try_neo4j_direct_answer(
    neo4j: Neo4jClient,
    question: str,
    *,
    mode: SearchMode,
    allowed_lobs: frozenset[str] | None = None,
) -> Neo4jDirectResult | None:
    from cypher_builder import retrieval_lob_scope

    from chat_application.auth.retrieval_scope import filter_rows_by_retrieval_lobs

    with retrieval_lob_scope(allowed_lobs):
        match = match_neo4j_direct_intent(question, mode=mode)
        if match is None:
            match = match_planned_graph_intent(question, mode=mode)
        if match is None:
            return None

        rows, cyphers = await run_neo4j_direct_queries(neo4j, match)

    rows = filter_rows_by_retrieval_lobs(rows, allowed_lobs)
    answer = format_neo4j_direct_answer(match, question, rows, mode=mode)
    if answer is None:
        return None

    return Neo4jDirectResult(
        answer=answer,
        cypher="\n\n".join(cyphers) if cyphers else None,
        graph_rows=rows,
        intent_id=match.intent_id,
        source=match.source,
    )
