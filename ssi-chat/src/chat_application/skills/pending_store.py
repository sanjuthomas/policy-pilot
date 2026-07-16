from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from chat_application.skills.models import PendingCreatePayment, PendingSubmitPayment

_DEFAULT_TTL_SECONDS = 600.0


class PendingSkillStore:
    """In-process TTL store for awaiting-confirmation skill runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, Any] = {}

    def put(self, pending: Any) -> Any:
        with self._lock:
            self._purge_locked()
            self._items[pending.pending_id] = pending
            return pending

    def get(self, pending_id: str) -> Any | None:
        with self._lock:
            self._purge_locked()
            return self._items.get(pending_id)

    def pop(self, pending_id: str) -> Any | None:
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


def build_submit_pending(
    *,
    user_id: str,
    payment_id: str,
    instruction_id: str,
    amount: float,
    value_date: str,
    currency: str,
    owning_lob: str,
    payment_status: str,
    instruction_status: str,
    instruction_end_date: str,
    instruction_type: str,
    instruction_version: int,
    created_by_user_id: str,
    created_by_supervisor_id: str | None,
    card: Any,
    ttl_seconds: float = _DEFAULT_TTL_SECONDS,
) -> PendingSubmitPayment:
    now = time.time()
    return PendingSubmitPayment(
        pending_id=new_pending_id(),
        user_id=user_id,
        payment_id=payment_id,
        instruction_id=instruction_id,
        amount=amount,
        value_date=value_date,
        currency=currency,
        owning_lob=owning_lob,
        payment_status=payment_status,
        instruction_status=instruction_status,
        instruction_end_date=instruction_end_date,
        instruction_type=instruction_type,
        instruction_version=instruction_version,
        created_by_user_id=created_by_user_id,
        created_by_supervisor_id=created_by_supervisor_id,
        card=card,
        expires_at=now + ttl_seconds,
    )


pending_create_payment_store = PendingSkillStore()
pending_submit_payment_store = PendingSkillStore()
