from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class GraphIntent(str, Enum):
    """Consolidated intent families rendered by the dynamic Cypher builder."""

    ALERT_COUNT_TODAY = "alert_count_today"
    INSTRUCTION_APPROVAL = "instruction_approval"
    INSTRUCTION_APPROVER_VIA_PAYMENT = "instruction_approver_via_payment"
    INSTRUCTION_AGGREGATE = "instruction_aggregate"
    INSTRUCTION_COMPLIANCE = "instruction_compliance"
    INSTRUCTION_INVENTORY = "instruction_inventory"
    INSTRUCTION_LOOKUP = "instruction_lookup"
    MAX_PAYMENTS_PER_INSTRUCTION = "max_payments_per_instruction"
    PAYMENT_AGGREGATE = "payment_aggregate"
    PAYMENT_APPROVAL = "payment_approval"
    PAYMENTS_FOR_INSTRUCTION = "payments_for_instruction"
    SECURITY_EVENT_AGGREGATE = "security_event_aggregate"
    SECURITY_EVENT_RANK = "security_event_rank"


class GraphQueryPlan(BaseModel):
    """Structured filter object extracted from natural language."""

    intent: GraphIntent
    operation: Literal["count", "list", "sum", "rank"] | None = None
    time_window: Literal["today", "week", "all"] | None = None
    domain: Literal["payments", "instructions", "all"] | None = None
    instruction_id: str | None = None
    payment_id: str | None = None
    user_id: str | None = None
    status: str | None = None
    instruction_type: str | None = None
    owning_lob: str | None = None
    severity: str | None = None
    denial: bool | None = None
    use_value_date: bool = False
    compliance_pattern: Literal[
        "mutual", "self", "subordinate", "duplicate_routes"
    ] | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
