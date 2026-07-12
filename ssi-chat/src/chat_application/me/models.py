from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MeIntentKind = Literal[
    "who_am_i",
    "my_permissions",
    "can_act_on_entity",
    "who_else_can_act",
    "who_can_create",
    "waiting_for_me",
    "users_like_me",
    "past_similar",
]

PaymentAction = Literal["CREATE", "APPROVE", "UPDATE", "SUBMIT", "REJECT", "CANCEL"]


@dataclass(frozen=True)
class MeIntent:
    kind: MeIntentKind
    action: PaymentAction | None = None
    entity_type: Literal["payment", "instruction"] | None = None
    entity_id: str | None = None
    covering_lob: str | None = None


@dataclass(frozen=True)
class MeIntentResult:
    answer: str
    intent_id: str
