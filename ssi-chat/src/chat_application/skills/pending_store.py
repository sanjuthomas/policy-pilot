from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from chat_application.skills.models import PendingCreatePayment

_DEFAULT_TTL_SECONDS = 600.0


class PendingSkillStore:
    """In-process TTL store for awaiting-confirmation skill runs."""

    def __init__(self, *, ttl_seconds: float = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._items: dict[str, PendingCreatePayment] = {}

    def put(self, pending: PendingCreatePayment) -> PendingCreatePayment:
        with self._lock:
            self._purge_locked()
            self._items[pending.pending_id] = pending
            return pending

    def get(self, pending_id: str) -> PendingCreatePayment | None:
        with self._lock:
            self._purge_locked()
            return self._items.get(pending_id)

    def pop(self, pending_id: str) -> PendingCreatePayment | None:
        with self._lock:
            self._purge_locked()
            return self._items.pop(pending_id, None)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def _purge_locked(self) -> None:
        now = time.time()
        expired = [key for key, item in self._items.items() if item.expires_at <= now]
        for key in expired:
            self._items.pop(key, None)


def new_pending_id() -> str:
    return str(uuid.uuid4())


def build_pending(
    *,
    user_id: str,
    instruction_id: str,
    amount: float,
    value_date: str,
    currency: str,
    owning_lob: str,
    instruction_status: str,
    instruction_end_date: str,
    instruction_type: str,
    instruction_version: int,
    card: Any,
    ttl_seconds: float = _DEFAULT_TTL_SECONDS,
) -> PendingCreatePayment:
    now = time.time()
    return PendingCreatePayment(
        pending_id=new_pending_id(),
        user_id=user_id,
        instruction_id=instruction_id,
        amount=amount,
        value_date=value_date,
        currency=currency,
        owning_lob=owning_lob,
        instruction_status=instruction_status,
        instruction_end_date=instruction_end_date,
        instruction_type=instruction_type,
        instruction_version=instruction_version,
        card=card,
        expires_at=now + ttl_seconds,
    )


pending_create_payment_store = PendingSkillStore()
