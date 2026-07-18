from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Subject(BaseModel):
    user_id: str
    given_name: str | None = None
    family_name: str | None = None
    title: str
    lob: str | None = None
    roles: list[str] = Field(min_length=1)
    groups: list[str] = Field(default_factory=list)
    supervisor_id: str | None = None
    covering_lobs: list[str] = Field(default_factory=list)
    # Set when Authorization is a service token and X-On-Behalf-Of carries the user.
    delegated_by: str | None = None
    delegated_by_roles: list[str] = Field(default_factory=list)

    def to_opa_subject(self) -> dict:
        payload: dict = {
            "user_id": self.user_id,
            "title": self.title,
            "roles": self.roles,
            "groups": self.groups,
            "covering_lobs": self.covering_lobs,
            "delegated_by_roles": self.delegated_by_roles,
        }
        if self.lob is not None:
            payload["lob"] = self.lob
        if self.supervisor_id is not None:
            payload["supervisor_id"] = self.supervisor_id
        return payload


class CreatePaymentRequest(BaseModel):
    instruction_id: str = Field(min_length=1)
    value_date: str = Field(description="ISO date string, e.g. 2026-07-01")
    amount: float = Field(gt=0)


UpdatePaymentRequest = CreatePaymentRequest


class CancelPaymentRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1024)


class RejectPaymentRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1024)


class UserReference(BaseModel):
    user_id: str
    given_name: str | None = None
    family_name: str | None = None
    title: str
    lob: str | None = None
    roles: list[str] = Field(default_factory=list)
    supervisor_id: str | None = None


class LifecycleEvent(BaseModel):
    event_id: str
    action: str
    actor_user_id: str
    timestamp: str
    details: dict = Field(default_factory=dict)


class PaymentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    payment_id: str
    version_number: int
    record_in: str = Field(serialization_alias="in")
    record_out: str | None = Field(default=None, serialization_alias="out")
    instruction_id: str
    instruction_version: int
    status: str
    amount: float
    currency: str
    value_date: str
    owning_lob: str
    instruction_type: str
    created_by: UserReference
    submitted_by: UserReference | None = None
    approved_by: UserReference | None = None
    rejected_by: UserReference | None = None
    cancelled_by: UserReference | None = None
    rejection_reason: str | None = None
    cancellation_reason: str | None = None
    created_at: str
    updated_at: str
    submitted_at: str | None = None
    approved_at: str | None = None
    rejected_at: str | None = None
    cancelled_at: str | None = None
    lifecycle_events: list[LifecycleEvent] = Field(default_factory=list)


class EligibleApproverResponse(BaseModel):
    user_id: str
    display_name: str
    title: str
    allow_basis: list[str] = Field(default_factory=list)


class PaymentEligibleApproversResponse(BaseModel):
    payment_id: str
    instruction_id: str
    payment_status: str
    amount: float
    currency: str
    owning_lob: str
    instruction_status: str
    evaluated_at: str
    eligible: list[EligibleApproverResponse]
    prospective_eligible: list[EligibleApproverResponse] = Field(default_factory=list)
    candidates_evaluated: int
    approval_blocked_reason: str | None = None
