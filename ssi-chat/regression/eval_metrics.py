"""Retrieval and answer-quality metrics for PolicyPilot regression runs.

Lightweight proxies (no LLM-as-judge / ragas dependency):
- routing accuracy vs declared ``retrieval`` strategy
- entity source recall (id appears in sources, graph rows, or answer)
- source-channel precision@k (vector/neo4j/exact)
- graph groundedness (answer token overlap with graph row values)
- faithfulness proxy (answer token overlap with retrieved context)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from regression.models import ExpectConfig, RetrievalStrategy

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{2,}", re.IGNORECASE)
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "are",
        "was",
        "were",
        "with",
        "that",
        "this",
        "from",
        "have",
        "has",
        "had",
        "not",
        "any",
        "there",
        "who",
        "what",
        "when",
        "why",
        "how",
        "many",
        "payment",
        "instruction",
        "events",
        "today",
        "week",
    }
)


@dataclass(frozen=True)
class RoutingExpectation:
    paths: frozenset[str]
    cypher_classes: frozenset[str] | None
    synthesis_modes: frozenset[str] | None
    max_generation_ms: float | None = None
    min_sources: int = 0
    source_channels_any: frozenset[str] | None = None


ROUTING_BY_RETRIEVAL: dict[RetrievalStrategy, RoutingExpectation] = {
    "deterministic": RoutingExpectation(
        paths=frozenset({"neo4j_direct"}),
        cypher_classes=frozenset({"deterministic"}),
        synthesis_modes=frozenset({"formatter"}),
        max_generation_ms=100.0,
    ),
    "eligibility": RoutingExpectation(
        paths=frozenset({"eligibility"}),
        cypher_classes=frozenset({"none"}),
        synthesis_modes=frozenset({"eligibility_api"}),
        min_sources=0,
    ),
    "policy_directory": RoutingExpectation(
        paths=frozenset({"policy_directory"}),
        cypher_classes=frozenset({"none"}),
        synthesis_modes=frozenset({"policy_directory_api"}),
        min_sources=0,
    ),
    "graph": RoutingExpectation(
        paths=frozenset({"neo4j_direct", "full_rag"}),
        cypher_classes=frozenset({"deterministic", "llm"}),
        synthesis_modes=frozenset({"formatter", "gemini_full", "gemini_why_only"}),
    ),
    "vector": RoutingExpectation(
        paths=frozenset({"full_rag"}),
        cypher_classes=None,
        synthesis_modes=frozenset({"gemini_full", "formatter"}),
        min_sources=1,
        source_channels_any=frozenset({"vector"}),
    ),
    "skill": RoutingExpectation(
        paths=frozenset({"skill"}),
        cypher_classes=frozenset({"none"}),
        synthesis_modes=frozenset({"formatter"}),
        min_sources=0,
    ),
}


@dataclass
class CaseQualityScores:
    routing_ok: bool | None = None
    cypher_class_ok: bool | None = None
    synthesis_ok: bool | None = None
    entity_recall: float | None = None
    source_precision_at_k: float | None = None
    groundedness: float | None = None
    faithfulness: float | None = None
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "routing_ok": self.routing_ok,
            "cypher_class_ok": self.cypher_class_ok,
            "synthesis_ok": self.synthesis_ok,
            "entity_recall": self.entity_recall,
            "source_precision_at_k": round(self.source_precision_at_k, 4)
            if self.source_precision_at_k is not None
            else None,
            "groundedness": round(self.groundedness, 4) if self.groundedness is not None else None,
            "faithfulness": round(self.faithfulness, 4) if self.faithfulness is not None else None,
            "passed": self.passed,
            "failures": list(self.failures),
        }


@dataclass
class SuiteQualitySummary:
    cases_scored: int = 0
    routing_accuracy: float | None = None
    mean_entity_recall: float | None = None
    mean_source_precision_at_k: float | None = None
    mean_groundedness: float | None = None
    mean_faithfulness: float | None = None
    quality_failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cases_scored": self.cases_scored,
            "routing_accuracy": round(self.routing_accuracy, 4)
            if self.routing_accuracy is not None
            else None,
            "mean_entity_recall": round(self.mean_entity_recall, 4)
            if self.mean_entity_recall is not None
            else None,
            "mean_source_precision_at_k": round(self.mean_source_precision_at_k, 4)
            if self.mean_source_precision_at_k is not None
            else None,
            "mean_groundedness": round(self.mean_groundedness, 4)
            if self.mean_groundedness is not None
            else None,
            "mean_faithfulness": round(self.mean_faithfulness, 4)
            if self.mean_faithfulness is not None
            else None,
            "quality_failures": self.quality_failures,
        }


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_RE.findall(text)
        if token.lower() not in _STOPWORDS and not token.isdigit()
    }


def _routing_expectation(
    retrieval: RetrievalStrategy,
    expect: ExpectConfig,
) -> RoutingExpectation:
    base = ROUTING_BY_RETRIEVAL[retrieval]
    paths = frozenset({expect.routing_path}) if expect.routing_path else base.paths
    cypher_classes = (
        frozenset({expect.cypher_class}) if expect.cypher_class else base.cypher_classes
    )
    synthesis = (
        frozenset({expect.answer_synthesis}) if expect.answer_synthesis else base.synthesis_modes
    )
    channels = (
        frozenset(expect.source_channels_any)
        if expect.source_channels_any
        else base.source_channels_any
    )
    return RoutingExpectation(
        paths=paths,
        cypher_classes=cypher_classes,
        synthesis_modes=synthesis,
        max_generation_ms=expect.max_generation_ms
        if expect.max_generation_ms is not None
        else base.max_generation_ms,
        min_sources=max(expect.min_sources, base.min_sources),
        source_channels_any=channels,
    )


def _cypher_class(provenance: str | None) -> str | None:
    if not provenance or provenance == "none":
        return "none"
    if provenance == "llm_graph_plan":
        return "llm"
    if provenance in ("predefined_yaml", "predefined_planned"):
        return "deterministic"
    return None


def _collect_context_text(
    sources: list[Any],
    graph_rows: list[Any],
) -> str:
    parts: list[str] = []
    for source in sources:
        if isinstance(source, dict):
            parts.append(str(source.get("summary") or ""))
            merged = source.get("merged") or {}
            if isinstance(merged, dict):
                parts.extend(str(value) for value in merged.values() if value is not None)
        else:
            parts.append(str(getattr(source, "summary", "")))
    for row in graph_rows:
        if isinstance(row, dict):
            parts.extend(str(value) for value in row.values() if value is not None)
        else:
            parts.append(str(row))
    return " ".join(parts)


def _entity_ids_from_question(question: str) -> list[str]:
    patterns = [
        r"\b\d{8}-[A-Z]+-[IP]-\d+\b",
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    ]
    found: list[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, question, flags=re.IGNORECASE))
    return list(dict.fromkeys(found))


def entity_source_recall(
    *,
    question: str,
    answer: str,
    sources: list[Any],
    graph_rows: list[Any],
    entity_ids: list[str] | None = None,
) -> float | None:
    ids = entity_ids or _entity_ids_from_question(question)
    if not ids:
        return None

    haystacks: list[str] = [answer]
    for source in sources:
        if isinstance(source, dict):
            haystacks.append(str(source.get("event_id") or ""))
            haystacks.append(str(source.get("instruction_id") or ""))
            merged = source.get("merged") or {}
            if isinstance(merged, dict):
                haystacks.append(str(merged.get("payment_id") or ""))
                haystacks.append(str(merged.get("instruction_id") or ""))
    for row in graph_rows:
        if isinstance(row, dict):
            haystacks.extend(str(value) for value in row.values() if value is not None)

    blob = " ".join(haystacks).lower()
    hits = sum(1 for entity_id in ids if entity_id.lower() in blob)
    return hits / len(ids)


def source_channel_precision_at_k(
    sources: list[Any],
    *,
    required_channels: frozenset[str],
    k: int = 5,
) -> float | None:
    if not required_channels or not sources:
        return None

    top = sources[:k]
    if not top:
        return 0.0

    hits = 0
    for source in top:
        channels: set[str]
        if isinstance(source, dict):
            channels = set(source.get("sources") or [])
        else:
            channels = set(getattr(source, "sources", []) or [])
        if channels.intersection(required_channels):
            hits += 1
    return hits / len(top)


def graph_groundedness(answer: str, graph_rows: list[Any]) -> float | None:
    if not graph_rows:
        return None
    row = graph_rows[0]
    if not isinstance(row, dict):
        return None

    row_text = " ".join(str(value) for value in row.values() if value is not None)
    answer_tokens = _tokens(answer)
    row_tokens = _tokens(row_text)
    if not answer_tokens or not row_tokens:
        return None
    overlap = answer_tokens.intersection(row_tokens)
    return len(overlap) / len(answer_tokens)


def faithfulness_proxy(
    answer: str,
    *,
    sources: list[Any],
    graph_rows: list[Any],
) -> float | None:
    context = _collect_context_text(sources, graph_rows)
    if not context.strip():
        return None
    answer_tokens = _tokens(answer)
    context_tokens = _tokens(context)
    if not answer_tokens:
        return None
    overlap = answer_tokens.intersection(context_tokens)
    return len(overlap) / len(answer_tokens)


def evaluate_case_quality(
    *,
    retrieval: RetrievalStrategy,
    expect: ExpectConfig,
    question: str,
    answer: str,
    sources: list[Any],
    graph_rows: list[Any],
    routing: dict[str, Any] | None,
    generation_ms: float | None,
    source_precision_k: int = 5,
) -> CaseQualityScores:
    scores = CaseQualityScores()
    expectation = _routing_expectation(retrieval, expect)

    if routing:
        path = routing.get("path")
        scores.routing_ok = path in expectation.paths if path else False
        if not scores.routing_ok:
            scores.failures.append(
                f"routing path={path!r} not in expected {sorted(expectation.paths)}"
            )

        provenance = routing.get("cypher_provenance")
        if expectation.cypher_classes is not None:
            actual_class = _cypher_class(provenance)
            scores.cypher_class_ok = actual_class in expectation.cypher_classes
            if not scores.cypher_class_ok:
                scores.failures.append(
                    f"cypher class={actual_class!r} not in expected "
                    f"{sorted(expectation.cypher_classes)}"
                )

        synthesis = routing.get("answer_synthesis")
        if expectation.synthesis_modes is not None and synthesis:
            scores.synthesis_ok = synthesis in expectation.synthesis_modes
            if not scores.synthesis_ok:
                scores.failures.append(
                    f"answer_synthesis={synthesis!r} not in expected "
                    f"{sorted(expectation.synthesis_modes)}"
                )
    elif expect.require_routing:
        scores.routing_ok = False
        scores.failures.append("routing metadata missing from chat response")

    if expectation.max_generation_ms is not None and generation_ms is not None:
        if generation_ms > expectation.max_generation_ms:
            scores.failures.append(
                f"generation_ms={generation_ms} > max={expectation.max_generation_ms}"
            )

    if len(sources) < expectation.min_sources:
        scores.failures.append(
            f"sources={len(sources)} < expected min_sources={expectation.min_sources}"
        )

    if expectation.source_channels_any:
        scores.source_precision_at_k = source_channel_precision_at_k(
            sources,
            required_channels=expectation.source_channels_any,
            k=source_precision_k,
        )
        if scores.source_precision_at_k == 0.0:
            scores.failures.append(
                "no top sources matched required channels "
                f"{sorted(expectation.source_channels_any)}"
            )

    scores.entity_recall = entity_source_recall(
        question=question,
        answer=answer,
        sources=sources,
        graph_rows=graph_rows,
    )
    if expect.require_entity_recall and scores.entity_recall is not None:
        if scores.entity_recall < 1.0:
            scores.failures.append(f"entity_recall={scores.entity_recall:.2f} < 1.0")

    scores.groundedness = graph_groundedness(answer, graph_rows)
    if expect.min_groundedness is not None and scores.groundedness is not None:
        if scores.groundedness < expect.min_groundedness:
            scores.failures.append(
                f"groundedness={scores.groundedness:.2f} < min={expect.min_groundedness}"
            )

    scores.faithfulness = faithfulness_proxy(
        answer,
        sources=sources,
        graph_rows=graph_rows,
    )
    if expect.min_faithfulness is not None and scores.faithfulness is not None:
        if scores.faithfulness < expect.min_faithfulness:
            scores.failures.append(
                f"faithfulness={scores.faithfulness:.2f} < min={expect.min_faithfulness}"
            )

    return scores


def summarize_suite_quality(
    case_scores: list[tuple[RetrievalStrategy, CaseQualityScores]],
) -> SuiteQualitySummary:
    summary = SuiteQualitySummary()
    if not case_scores:
        return summary

    summary.cases_scored = len(case_scores)

    routing_values = [scores.routing_ok for _, scores in case_scores if scores.routing_ok is not None]
    if routing_values:
        summary.routing_accuracy = sum(1 for value in routing_values if value) / len(routing_values)

    entity_values = [scores.entity_recall for _, scores in case_scores if scores.entity_recall is not None]
    if entity_values:
        summary.mean_entity_recall = sum(entity_values) / len(entity_values)

    precision_values = [
        scores.source_precision_at_k
        for _, scores in case_scores
        if scores.source_precision_at_k is not None
    ]
    if precision_values:
        summary.mean_source_precision_at_k = sum(precision_values) / len(precision_values)

    groundedness_values = [
        scores.groundedness for _, scores in case_scores if scores.groundedness is not None
    ]
    if groundedness_values:
        summary.mean_groundedness = sum(groundedness_values) / len(groundedness_values)

    faithfulness_values = [
        scores.faithfulness for _, scores in case_scores if scores.faithfulness is not None
    ]
    if faithfulness_values:
        summary.mean_faithfulness = sum(faithfulness_values) / len(faithfulness_values)

    summary.quality_failures = sum(1 for _, scores in case_scores if not scores.passed)
    return summary
