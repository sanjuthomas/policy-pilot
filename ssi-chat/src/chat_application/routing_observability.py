from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal

from telemetry import get_logger, get_meter, record_counter, record_histogram

from chat_application.models import (
    AnswerRoutingInfo,
    ChatResponse,
    SearchMode,
    SourceHit,
)

CypherProvenance = Literal[
    "predefined_yaml",
    "predefined_planned",
    "llm_graph_plan",
    "none",
]

CypherClass = Literal["deterministic", "llm", "none"]

AnswerSynthesis = Literal[
    "formatter",
    "gemini_full",
    "gemini_why_only",
    "eligibility_api",
]

RetrievalPath = Literal[
    "neo4j_direct",
    "eligibility",
    "full_rag",
]

CYPHER_LABELS: dict[str, str] = {
    "predefined_yaml": "Predefined Cypher (YAML)",
    "predefined_planned": "Predefined Cypher (planned)",
    "llm_graph_plan": "LLM-generated Cypher",
    "none": "No Cypher",
}

CYPHER_CLASS_LABELS: dict[str, str] = {
    "deterministic": "Predefined deterministic Cypher",
    "llm": "LLM-derived Cypher",
    "none": "No Cypher",
}

SYNTHESIS_LABELS: dict[str, str] = {
    "formatter": "Deterministic formatter",
    "gemini_full": "Gemini (full answer)",
    "gemini_why_only": "Gemini (WHY rewrite only)",
    "eligibility_api": "Eligibility API (OPA)",
}

PATH_LABELS: dict[str, str] = {
    "neo4j_direct": "Neo4j direct (early exit)",
    "eligibility": "Eligibility shortcut",
    "full_rag": "Full RAG (vector + BM25 + graph)",
}

_logger = get_logger(__name__)
_meter = None


def _get_routing_meter():
    global _meter
    if _meter is None:
        _meter = get_meter("chat_application.routing", version="0.1.0")
    return _meter


def cypher_class_for_provenance(provenance: CypherProvenance) -> CypherClass:
    if provenance in ("predefined_yaml", "predefined_planned"):
        return "deterministic"
    if provenance == "llm_graph_plan":
        return "llm"
    return "none"


def question_fingerprint(message: str) -> tuple[int, str]:
    normalized = message.strip()
    length = len(normalized)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return length, digest


def cypher_provenance_for_direct_intent(intent_id: str, *, source: str | None = None) -> CypherProvenance:
    if source == "planned" or intent_id == "planned_graph":
        return "predefined_planned"
    return "predefined_yaml"


def format_routing_label(
    *,
    path: RetrievalPath,
    cypher_provenance: CypherProvenance,
    answer_synthesis: AnswerSynthesis,
    intent_id: str | None = None,
) -> str:
    parts = [
        PATH_LABELS[path],
        CYPHER_LABELS[cypher_provenance],
        SYNTHESIS_LABELS[answer_synthesis],
    ]
    if intent_id:
        parts.append(f"intent={intent_id}")
    return " · ".join(parts)


@dataclass(frozen=True)
class AnswerRouting:
    path: RetrievalPath
    cypher_provenance: CypherProvenance
    answer_synthesis: AnswerSynthesis
    mode: SearchMode
    intent_id: str | None = None
    retrieval_ms: float | None = None
    generation_ms: float | None = None
    source_count: int = 0
    graph_row_count: int = 0
    question_length: int = 0
    question_hash: str = ""

    def to_api(self) -> AnswerRoutingInfo:
        return AnswerRoutingInfo(
            path=self.path,
            cypher_provenance=self.cypher_provenance,
            answer_synthesis=self.answer_synthesis,
            intent_id=self.intent_id,
            label=format_routing_label(
                path=self.path,
                cypher_provenance=self.cypher_provenance,
                answer_synthesis=self.answer_synthesis,
                intent_id=self.intent_id,
            ),
        )

    def log_fields(self) -> dict[str, Any]:
        return {
            "chat.event": "chat.answer.completed",
            "chat.path": self.path,
            "chat.cypher_provenance": self.cypher_provenance,
            "chat.answer_synthesis": self.answer_synthesis,
            "chat.intent_id": self.intent_id,
            "chat.mode": self.mode,
            "chat.retrieval_ms": self.retrieval_ms,
            "chat.generation_ms": self.generation_ms,
            "chat.source_count": self.source_count,
            "chat.graph_row_count": self.graph_row_count,
            "chat.question_length": self.question_length,
            "chat.question_hash": self.question_hash,
        }


def record_answer_routing_metrics(routing: AnswerRouting) -> None:
    cypher_class = cypher_class_for_provenance(routing.cypher_provenance)
    metric_attrs = {
        "chat.cypher_class": cypher_class,
        "chat.cypher_provenance": routing.cypher_provenance,
        "chat.path": routing.path,
        "chat.mode": routing.mode,
        "chat.answer_synthesis": routing.answer_synthesis,
    }
    meter = _get_routing_meter()
    record_counter(meter, "chat.answer.count", attributes=metric_attrs)
    record_counter(
        meter,
        "chat.cypher.route.count",
        attributes={
            "chat.cypher_class": cypher_class,
            "chat.cypher_provenance": routing.cypher_provenance,
            "chat.mode": routing.mode,
        },
    )
    if routing.retrieval_ms is not None:
        record_histogram(
            meter,
            "chat.answer.retrieval.duration",
            routing.retrieval_ms,
            attributes={
                "chat.cypher_class": cypher_class,
                "chat.path": routing.path,
                "chat.mode": routing.mode,
            },
        )
    if routing.generation_ms is not None:
        record_histogram(
            meter,
            "chat.answer.generation.duration",
            routing.generation_ms,
            attributes={
                "chat.cypher_class": cypher_class,
                "chat.answer_synthesis": routing.answer_synthesis,
                "chat.mode": routing.mode,
            },
        )


def log_answer_routing(routing: AnswerRouting) -> None:
    record_answer_routing_metrics(routing)
    _logger.info(
        "chat.answer.completed path=%s cypher=%s synthesis=%s mode=%s intent=%s",
        routing.path,
        routing.cypher_provenance,
        routing.answer_synthesis,
        routing.mode,
        routing.intent_id or "-",
        extra=routing.log_fields(),
    )


def finalize_chat_response(
    message: str,
    mode: SearchMode,
    *,
    answer: str,
    sources: list[SourceHit] | None = None,
    cypher: str | None = None,
    graph_rows: list[dict[str, Any]] | None = None,
    retrieval_ms: float,
    generation_ms: float,
    path: RetrievalPath,
    cypher_provenance: CypherProvenance,
    answer_synthesis: AnswerSynthesis,
    intent_id: str | None = None,
) -> ChatResponse:
    question_length, question_hash = question_fingerprint(message)
    routing = AnswerRouting(
        path=path,
        cypher_provenance=cypher_provenance,
        answer_synthesis=answer_synthesis,
        mode=mode,
        intent_id=intent_id,
        retrieval_ms=round(retrieval_ms, 1),
        generation_ms=round(generation_ms, 1),
        source_count=len(sources or []),
        graph_row_count=len(graph_rows or []),
        question_length=question_length,
        question_hash=question_hash,
    )
    log_answer_routing(routing)
    return ChatResponse(
        answer=answer,
        sources=sources or [],
        cypher=cypher,
        graph_rows=(graph_rows or [])[:20],
        retrieval_ms=round(retrieval_ms, 1),
        generation_ms=round(generation_ms, 1),
        routing=routing.to_api(),
    )
