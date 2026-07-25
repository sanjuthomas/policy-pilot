from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AuditTimelineStep(BaseModel):
    at: str | None = None
    step: str
    summary: str
    decision: str | None = None


class AuditPolicyExchange(BaseModel):
    """Provisional OPA exchange when no security event exists yet (e.g. chat preflight)."""

    evaluate_request: dict[str, Any] = Field(default_factory=dict)
    evaluate_response: dict[str, Any] = Field(default_factory=dict)


class AuditGovernance(BaseModel):
    security_event_id: str | None = None
    policy_exchange: AuditPolicyExchange | None = None


class CreateAuditExecutionRequest(BaseModel):
    capability: str = Field(default="CREATE_PAYMENT", min_length=1)
    skill: str = Field(default="create_payment", min_length=1)
    channel: str = Field(default="chat", min_length=1)
    status: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    request: dict[str, Any] = Field(default_factory=dict)
    interpretation: dict[str, Any] = Field(default_factory=dict)
    timeline: list[AuditTimelineStep] = Field(default_factory=list)
    timings_ms: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    governance: AuditGovernance | None = None
    execution_id: str | None = None


class PatchAuditExecutionRequest(BaseModel):
    status: str | None = None
    outcome: str | None = None
    timeline: list[AuditTimelineStep] | None = None
    timings_ms: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    governance: AuditGovernance | None = None
