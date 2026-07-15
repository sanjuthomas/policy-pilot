from __future__ import annotations

import threading
from dataclasses import dataclass

from etl.dlq.models import PipelineKind


@dataclass
class PauseState:
    paused: bool = False
    reason: str | None = None


class ConsumerPauseRegistry:
    """In-process pause flags for indexer Kafka consumers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, PauseState] = {}
        self._handlers: dict[PipelineKind, object] = {}

    def set_paused(self, consumer_name: str, *, reason: str) -> None:
        with self._lock:
            self._states[consumer_name] = PauseState(paused=True, reason=reason)

    def clear_paused(self, consumer_name: str) -> None:
        with self._lock:
            self._states[consumer_name] = PauseState(paused=False, reason=None)

    def is_paused(self, consumer_name: str) -> bool:
        with self._lock:
            state = self._states.get(consumer_name)
            return bool(state and state.paused)

    def snapshot(self) -> dict[str, dict[str, object]]:
        with self._lock:
            return {
                name: {"paused": state.paused, "reason": state.reason}
                for name, state in self._states.items()
            }

    def any_paused(self) -> bool:
        with self._lock:
            return any(state.paused for state in self._states.values())

    def register_replay(self, kind: PipelineKind, handler) -> None:
        self._handlers[kind] = handler

    def get_replay(self, kind: PipelineKind):
        return self._handlers.get(kind)


pause_registry = ConsumerPauseRegistry()
