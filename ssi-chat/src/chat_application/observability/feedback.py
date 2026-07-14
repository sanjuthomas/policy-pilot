"""User thumbs-up/down feedback logging and metrics keyed by retrieval mechanism."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from telemetry import get_logger, get_meter, record_counter

from chat_application.observability.routing import (
    RetrievalStrategy,
    classify_retrieval_strategy,
    cypher_class_for_provenance,
)

FeedbackRating = Literal["up", "down"]

_logger = get_logger(__name__)
_meter = None


def _get_feedback_meter():
    global _meter
    if _meter is None:
        _meter = get_meter("chat_application.feedback", version="0.1.0")
    return _meter


@dataclass(frozen=True)
class ChatFeedbackContext:
    rating: FeedbackRating
    mode: str
    path: str
    cypher_provenance: str
    answer_synthesis: str
    retrieval_strategy: RetrievalStrategy
    user_id: str | None = None
    intent_id: str | None = None
    question_hash: str | None = None

    @classmethod
    def from_payload(
        cls,
        *,
        rating: FeedbackRating,
        mode: str,
        path: str,
        cypher_provenance: str,
        answer_synthesis: str,
        retrieval_strategy: str | None,
        user_id: str | None,
        intent_id: str | None = None,
        question_hash: str | None = None,
        graph_row_count: int = 0,
        source_channels: dict[str, int] | None = None,
    ) -> ChatFeedbackContext:
        strategy: RetrievalStrategy
        if retrieval_strategy in (
            "deterministic",
            "graph",
            "vector",
            "eligibility",
            "policy_directory",
            "skill",
        ):
            strategy = retrieval_strategy  # type: ignore[assignment]
        else:
            strategy = classify_retrieval_strategy(
                path=path,  # type: ignore[arg-type]
                cypher_provenance=cypher_provenance,  # type: ignore[arg-type]
                answer_synthesis=answer_synthesis,  # type: ignore[arg-type]
                source_channels=source_channels,
                graph_row_count=graph_row_count,
            )
        return cls(
            rating=rating,
            mode=mode,
            path=path,
            cypher_provenance=cypher_provenance,
            answer_synthesis=answer_synthesis,
            retrieval_strategy=strategy,
            user_id=user_id,
            intent_id=intent_id,
            question_hash=question_hash,
        )

    def log_fields(self) -> dict[str, Any]:
        return {
            "chat.event": "chat.feedback.received",
            "chat.feedback_rating": self.rating,
            "chat.retrieval_strategy": self.retrieval_strategy,
            "chat.path": self.path,
            "chat.cypher_provenance": self.cypher_provenance,
            "chat.cypher_class": cypher_class_for_provenance(self.cypher_provenance),  # type: ignore[arg-type]
            "chat.answer_synthesis": self.answer_synthesis,
            "chat.mode": self.mode,
            "chat.intent_id": self.intent_id,
            "chat.question_hash": self.question_hash,
            "chat.user_id": self.user_id,
        }


@dataclass
class FeedbackStrategyStats:
    up: int = 0
    down: int = 0

    @property
    def total(self) -> int:
        return self.up + self.down

    @property
    def satisfaction_rate(self) -> float | None:
        if self.total == 0:
            return None
        return self.up / self.total

    def to_dict(self) -> dict[str, Any]:
        return {
            "up": self.up,
            "down": self.down,
            "total": self.total,
            "satisfaction_rate": round(self.satisfaction_rate, 4)
            if self.satisfaction_rate is not None
            else None,
        }


@dataclass
class FeedbackDistributionSnapshot:
    total: int = 0
    up: int = 0
    down: int = 0
    by_strategy: dict[str, FeedbackStrategyStats] = field(default_factory=dict)
    updated_at: str | None = None

    @property
    def satisfaction_rate(self) -> float | None:
        if self.total == 0:
            return None
        return self.up / self.total

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "up": self.up,
            "down": self.down,
            "satisfaction_rate": round(self.satisfaction_rate, 4)
            if self.satisfaction_rate is not None
            else None,
            "by_strategy": {
                strategy: stats.to_dict() for strategy, stats in sorted(self.by_strategy.items())
            },
            "updated_at": self.updated_at,
        }


class FeedbackDistributionTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._up = 0
        self._down = 0
        self._by_strategy: dict[str, FeedbackStrategyStats] = defaultdict(FeedbackStrategyStats)
        self._updated_at: datetime | None = None

    def record(self, feedback: ChatFeedbackContext) -> None:
        with self._lock:
            if feedback.rating == "up":
                self._up += 1
                self._by_strategy[feedback.retrieval_strategy].up += 1
            else:
                self._down += 1
                self._by_strategy[feedback.retrieval_strategy].down += 1
            self._updated_at = datetime.now(UTC)

    def snapshot(self) -> FeedbackDistributionSnapshot:
        with self._lock:
            return FeedbackDistributionSnapshot(
                total=self._up + self._down,
                up=self._up,
                down=self._down,
                by_strategy=dict(self._by_strategy),
                updated_at=self._updated_at.isoformat() if self._updated_at else None,
            )

    def reset(self) -> None:
        with self._lock:
            self._up = 0
            self._down = 0
            self._by_strategy.clear()
            self._updated_at = None


_feedback_tracker = FeedbackDistributionTracker()


def get_feedback_distribution() -> FeedbackDistributionSnapshot:
    return _feedback_tracker.snapshot()


def reset_feedback_distribution() -> None:
    _feedback_tracker.reset()


def record_chat_feedback(feedback: ChatFeedbackContext) -> None:
    cypher_class = cypher_class_for_provenance(feedback.cypher_provenance)  # type: ignore[arg-type]
    metric_attrs = {
        "chat.feedback_rating": feedback.rating,
        "chat.retrieval_strategy": feedback.retrieval_strategy,
        "chat.path": feedback.path,
        "chat.mode": feedback.mode,
        "chat.cypher_class": cypher_class,
        "chat.answer_synthesis": feedback.answer_synthesis,
    }
    record_counter(_get_feedback_meter(), "chat.feedback.count", attributes=metric_attrs)
    _feedback_tracker.record(feedback)
    _logger.info(
        "chat.feedback.received rating=%s strategy=%s path=%s cypher=%s synthesis=%s mode=%s user=%s",
        feedback.rating,
        feedback.retrieval_strategy,
        feedback.path,
        feedback.cypher_provenance,
        feedback.answer_synthesis,
        feedback.mode,
        feedback.user_id or "-",
        extra=feedback.log_fields(),
    )
