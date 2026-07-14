from __future__ import annotations

import hashlib
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
    "policy_directory_api",
]

RetrievalPath = Literal[
    "neo4j_direct",
    "eligibility",
    "policy_directory",
    "full_rag",
    "skill",
]

RetrievalStrategy = Literal[
    "deterministic",
    "graph",
    "vector",
    "eligibility",
    "policy_directory",
    "skill",
]

SOURCE_CHANNELS = ("vector", "neo4j", "exact")

CYPHER_LABELS: dict[str, str] = {
    "predefined_yaml": "Predefined Cypher (YAML)",
    "predefined_planned": "Predefined Cypher (planned)",
    "llm_graph_plan": "LLM-generated Cypher",
    "none": "No Cypher",
}

SYNTHESIS_LABELS: dict[str, str] = {
    "formatter": "Deterministic formatter",
    "gemini_full": "Gemini (full answer)",
    "gemini_why_only": "Gemini (WHY rewrite only)",
    "eligibility_api": "Eligibility API (OPA)",
    "policy_directory_api": "Policy directory API",
}

PATH_LABELS: dict[str, str] = {
    "neo4j_direct": "Neo4j direct (early exit)",
    "eligibility": "Eligibility shortcut",
    "policy_directory": "Policy directory",
    "full_rag": "Full RAG (vector + graph)",
    "skill": "Mutation skill",
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


def count_source_channels(sources: list[SourceHit] | list[Any] | None) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for source in sources or []:
        channels: list[str]
        if isinstance(source, SourceHit):
            channels = source.sources
        elif isinstance(source, dict):
            channels = list(source.get("sources") or [])
        else:
            channels = list(getattr(source, "sources", []) or [])
        for channel in channels:
            if channel in SOURCE_CHANNELS:
                counts[channel] += 1
    return {channel: counts.get(channel, 0) for channel in SOURCE_CHANNELS}


def classify_retrieval_strategy(
    *,
    path: RetrievalPath,
    cypher_provenance: CypherProvenance,
    answer_synthesis: AnswerSynthesis,
    source_channels: dict[str, int] | None = None,
    graph_row_count: int = 0,
) -> RetrievalStrategy:
    if path == "eligibility":
        return "eligibility"
    if path == "policy_directory":
        return "policy_directory"
    if path == "skill":
        return "skill"
    if path == "neo4j_direct":
        return "deterministic"

    channels = source_channels or {}
    vector_hits = channels.get("vector", 0)
    graph_hits = channels.get("neo4j", 0) + channels.get("exact", 0)

    if (
        answer_synthesis == "gemini_full"
        and vector_hits > 0
        and vector_hits >= graph_hits
        and graph_row_count == 0
    ):
        return "vector"
    if (
        cypher_provenance in ("predefined_planned", "llm_graph_plan")
        or graph_row_count > 0
        or answer_synthesis in ("formatter", "gemini_why_only")
    ):
        return "graph"
    if vector_hits > graph_hits:
        return "vector"
    return "graph"


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
    retrieval_strategy: RetrievalStrategy
    intent_id: str | None = None
    retrieval_ms: float | None = None
    generation_ms: float | None = None
    source_count: int = 0
    graph_row_count: int = 0
    source_channels: dict[str, int] = field(default_factory=dict)
    question_length: int = 0
    question_hash: str = ""

    def to_api(self) -> AnswerRoutingInfo:
        return AnswerRoutingInfo(
            path=self.path,
            cypher_provenance=self.cypher_provenance,
            answer_synthesis=self.answer_synthesis,
            intent_id=self.intent_id,
            retrieval_strategy=self.retrieval_strategy,
            label=format_routing_label(
                path=self.path,
                cypher_provenance=self.cypher_provenance,
                answer_synthesis=self.answer_synthesis,
                intent_id=self.intent_id,
            ),
        )

    def log_fields(self) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "chat.event": "chat.answer.completed",
            "chat.retrieval_strategy": self.retrieval_strategy,
            "chat.path": self.path,
            "chat.cypher_provenance": self.cypher_provenance,
            "chat.cypher_class": cypher_class_for_provenance(self.cypher_provenance),
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
        for channel, count in self.source_channels.items():
            if count:
                fields[f"chat.source_{channel}"] = count
        return fields


@dataclass
class RoutingDistributionSnapshot:
    total: int = 0
    by_strategy: dict[str, int] = field(default_factory=dict)
    by_path: dict[str, int] = field(default_factory=dict)
    by_cypher_class: dict[str, int] = field(default_factory=dict)
    by_synthesis: dict[str, int] = field(default_factory=dict)
    by_mode: dict[str, int] = field(default_factory=dict)
    by_source_channel: dict[str, int] = field(default_factory=dict)
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "by_strategy": dict(self.by_strategy),
            "by_path": dict(self.by_path),
            "by_cypher_class": dict(self.by_cypher_class),
            "by_synthesis": dict(self.by_synthesis),
            "by_mode": dict(self.by_mode),
            "by_source_channel": dict(self.by_source_channel),
            "updated_at": self.updated_at,
        }


class RoutingDistributionTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total = 0
        self._by_strategy: Counter[str] = Counter()
        self._by_path: Counter[str] = Counter()
        self._by_cypher_class: Counter[str] = Counter()
        self._by_synthesis: Counter[str] = Counter()
        self._by_mode: Counter[str] = Counter()
        self._by_source_channel: Counter[str] = Counter()
        self._updated_at: datetime | None = None

    def record(self, routing: AnswerRouting) -> None:
        cypher_class = cypher_class_for_provenance(routing.cypher_provenance)
        with self._lock:
            self._total += 1
            self._by_strategy[routing.retrieval_strategy] += 1
            self._by_path[routing.path] += 1
            self._by_cypher_class[cypher_class] += 1
            self._by_synthesis[routing.answer_synthesis] += 1
            self._by_mode[routing.mode] += 1
            for channel, count in routing.source_channels.items():
                if count:
                    self._by_source_channel[channel] += count
            self._updated_at = datetime.now(UTC)

    def snapshot(self) -> RoutingDistributionSnapshot:
        with self._lock:
            return RoutingDistributionSnapshot(
                total=self._total,
                by_strategy=dict(self._by_strategy),
                by_path=dict(self._by_path),
                by_cypher_class=dict(self._by_cypher_class),
                by_synthesis=dict(self._by_synthesis),
                by_mode=dict(self._by_mode),
                by_source_channel=dict(self._by_source_channel),
                updated_at=self._updated_at.isoformat() if self._updated_at else None,
            )

    def reset(self) -> None:
        with self._lock:
            self._total = 0
            self._by_strategy.clear()
            self._by_path.clear()
            self._by_cypher_class.clear()
            self._by_synthesis.clear()
            self._by_mode.clear()
            self._by_source_channel.clear()
            self._updated_at = None


_distribution_tracker = RoutingDistributionTracker()


def get_routing_distribution() -> RoutingDistributionSnapshot:
    return _distribution_tracker.snapshot()


def reset_routing_distribution() -> None:
    _distribution_tracker.reset()


def record_answer_routing_metrics(routing: AnswerRouting) -> None:
    cypher_class = cypher_class_for_provenance(routing.cypher_provenance)
    metric_attrs = {
        "chat.retrieval_strategy": routing.retrieval_strategy,
        "chat.cypher_class": cypher_class,
        "chat.cypher_provenance": routing.cypher_provenance,
        "chat.path": routing.path,
        "chat.mode": routing.mode,
        "chat.answer_synthesis": routing.answer_synthesis,
    }
    meter = _get_routing_meter()
    record_counter(meter, "chat.answer.count", attributes=metric_attrs)
    record_counter(meter, "chat.retrieval.route.count", attributes=metric_attrs)
    record_counter(
        meter,
        "chat.cypher.route.count",
        attributes={
            "chat.retrieval_strategy": routing.retrieval_strategy,
            "chat.cypher_class": cypher_class,
            "chat.cypher_provenance": routing.cypher_provenance,
            "chat.mode": routing.mode,
        },
    )
    for channel, count in routing.source_channels.items():
        if count:
            record_counter(
                meter,
                "chat.retrieval.source.channel.count",
                amount=count,
                attributes={
                    "chat.source_channel": channel,
                    "chat.retrieval_strategy": routing.retrieval_strategy,
                    "chat.mode": routing.mode,
                },
            )
    if routing.retrieval_ms is not None:
        record_histogram(
            meter,
            "chat.answer.retrieval.duration",
            routing.retrieval_ms,
            attributes={
                "chat.retrieval_strategy": routing.retrieval_strategy,
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
                "chat.retrieval_strategy": routing.retrieval_strategy,
                "chat.cypher_class": cypher_class,
                "chat.answer_synthesis": routing.answer_synthesis,
                "chat.mode": routing.mode,
            },
        )


def log_answer_routing(routing: AnswerRouting) -> None:
    record_answer_routing_metrics(routing)
    _distribution_tracker.record(routing)
    channel_summary = ",".join(
        f"{channel}={count}"
        for channel, count in routing.source_channels.items()
        if count
    ) or "-"
    _logger.info(
        (
            "chat.answer.completed strategy=%s path=%s cypher=%s synthesis=%s "
            "mode=%s intent=%s sources=%s graph_rows=%s channels=%s "
            "retrieval_ms=%s generation_ms=%s"
        ),
        routing.retrieval_strategy,
        routing.path,
        routing.cypher_provenance,
        routing.answer_synthesis,
        routing.mode,
        routing.intent_id or "-",
        routing.source_count,
        routing.graph_row_count,
        channel_summary,
        routing.retrieval_ms,
        routing.generation_ms,
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
    skill_activities: list[str] | None = None,
    skill_confirmation: Any | None = None,
) -> ChatResponse:
    from chat_application.models import SkillConfirmationInfo

    question_length, question_hash = question_fingerprint(message)
    source_channels = count_source_channels(sources)
    retrieval_strategy = classify_retrieval_strategy(
        path=path,
        cypher_provenance=cypher_provenance,
        answer_synthesis=answer_synthesis,
        source_channels=source_channels,
        graph_row_count=len(graph_rows or []),
    )
    routing = AnswerRouting(
        path=path,
        cypher_provenance=cypher_provenance,
        answer_synthesis=answer_synthesis,
        mode=mode,
        retrieval_strategy=retrieval_strategy,
        intent_id=intent_id,
        retrieval_ms=round(retrieval_ms, 1),
        generation_ms=round(generation_ms, 1),
        source_count=len(sources or []),
        graph_row_count=len(graph_rows or []),
        source_channels=source_channels,
        question_length=question_length,
        question_hash=question_hash,
    )
    log_answer_routing(routing)
    confirmation: SkillConfirmationInfo | None = None
    if skill_confirmation is not None:
        if isinstance(skill_confirmation, SkillConfirmationInfo):
            confirmation = skill_confirmation
        else:
            confirmation = SkillConfirmationInfo.model_validate(skill_confirmation)
    return ChatResponse(
        answer=answer,
        sources=sources or [],
        cypher=cypher,
        graph_rows=(graph_rows or [])[:20],
        retrieval_ms=round(retrieval_ms, 1),
        generation_ms=round(generation_ms, 1),
        routing=routing.to_api(),
        skill_activities=list(skill_activities or []),
        skill_confirmation=confirmation,
    )
