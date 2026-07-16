from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CreatePaymentParams:
    instruction_id: str
    amount: float
    value_date: str


@dataclass(frozen=True)
class SubmitPaymentParams:
    payment_id: str


@dataclass(frozen=True)
class ApprovePaymentParams:
    payment_id: str


@dataclass
class ConfirmationCard:
    instruction_id: str
    amount: float
    currency: str
    value_date: str
    owning_lob: str
    instruction_status: str
    debtor_name: str
    debtor_account: str
    creditor_name: str
    creditor_account: str
    intermediaries: list[str] = field(default_factory=list)
    payment_id: str | None = None
    payment_status: str | None = None

    def to_api(self) -> dict[str, Any]:
        payload = {
            "instruction_id": self.instruction_id,
            "amount": self.amount,
            "currency": self.currency,
            "value_date": self.value_date,
            "owning_lob": self.owning_lob,
            "instruction_status": self.instruction_status,
            "debtor_name": self.debtor_name,
            "debtor_account": self.debtor_account,
            "creditor_name": self.creditor_name,
            "creditor_account": self.creditor_account,
            "intermediaries": list(self.intermediaries),
        }
        if self.payment_id:
            payload["payment_id"] = self.payment_id
        if self.payment_status:
            payload["payment_status"] = self.payment_status
        return payload


@dataclass
class PendingCreatePayment:
    pending_id: str
    user_id: str
    instruction_id: str
    amount: float
    value_date: str
    currency: str
    owning_lob: str
    instruction_status: str
    instruction_end_date: str
    instruction_type: str
    instruction_version: int
    card: ConfirmationCard
    expires_at: float


@dataclass
class PendingSubmitPayment:
    pending_id: str
    user_id: str
    payment_id: str
    instruction_id: str
    amount: float
    value_date: str
    currency: str
    owning_lob: str
    payment_status: str
    instruction_status: str
    instruction_end_date: str
    instruction_type: str
    instruction_version: int
    created_by_user_id: str
    created_by_supervisor_id: str | None
    card: ConfirmationCard
    expires_at: float


@dataclass
class PendingApprovePayment:
    pending_id: str
    user_id: str
    payment_id: str
    instruction_id: str
    amount: float
    value_date: str
    currency: str
    owning_lob: str
    payment_status: str
    instruction_status: str
    instruction_end_date: str
    instruction_type: str
    instruction_version: int
    created_by_user_id: str
    created_by_supervisor_id: str | None
    card: ConfirmationCard
    expires_at: float


@dataclass
class SkillRunResult:
    """Outcome of a skill phase ready for the chat UI."""

    answer: str
    activities: list[str] = field(default_factory=list)
    pending_id: str | None = None
    confirmation: ConfirmationCard | None = None
    intent_id: str = "skill"
    skill: str = "create_payment"
