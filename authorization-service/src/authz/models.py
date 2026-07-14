from __future__ import annotations

from pydantic import BaseModel, Field


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

    @property
    def display_name(self) -> str:
        if self.family_name and self.given_name:
            return f"{self.family_name}, {self.given_name} ({self.user_id})"
        return self.user_id


class SeedUser(BaseModel):
    user_id: str
    given_name: str
    family_name: str
    title: str
    roles: list[str]
    lob: str | None = None
    groups: list[str] = Field(default_factory=list)
    supervisor_id: str | None = None
    covering_lobs: list[str] = Field(default_factory=list)

    def to_subject(self) -> Subject:
        return Subject(
            user_id=self.user_id,
            given_name=self.given_name,
            family_name=self.family_name,
            title=self.title,
            lob=self.lob,
            roles=self.roles,
            groups=self.groups,
            supervisor_id=self.supervisor_id,
            covering_lobs=self.covering_lobs,
        )


class UserReference(BaseModel):
    user_id: str
    supervisor_id: str | None = None


class PaymentRecord(BaseModel):
    payment_id: str
    instruction_id: str
    instruction_version: int
    status: str
    amount: float
    currency: str
    owning_lob: str
    instruction_type: str = ""
    created_by: UserReference

    def to_opa_payment(self, *, instruction_end_date: str, instruction_status: str) -> dict:
        return {
            "payment_id": self.payment_id,
            "instruction_id": self.instruction_id,
            "instruction_version": self.instruction_version,
            "amount": self.amount,
            "currency": self.currency,
            "instruction_status": instruction_status,
            "instruction_end_date": instruction_end_date,
            "instruction_type": self.instruction_type,
            "instruction_owning_lob": self.owning_lob,
            "created_by": {
                "user_id": self.created_by.user_id,
                "supervisor_id": self.created_by.supervisor_id,
            },
        }


class EligibleApprover(BaseModel):
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
    eligible: list[EligibleApprover]
    prospective_eligible: list[EligibleApprover] = Field(default_factory=list)
    candidates_evaluated: int
    approval_blocked_reason: str | None = None


class InstructionEligibleApproversResponse(BaseModel):
    instruction_id: str
    instruction_status: str
    instruction_type: str
    owning_lob: str
    created_by_user_id: str
    created_by_title: str
    evaluated_at: str
    eligible: list[EligibleApprover]
    prospective_eligible: list[EligibleApprover] = Field(default_factory=list)
    candidates_evaluated: int
    approval_blocked_reason: str | None = None


class UserDirectoryRow(BaseModel):
    user_id: str
    login_name: str
    given_name: str
    family_name: str
    display_name: str
    title: str
    lob: str | None = None
    roles: list[str]
    groups: list[str] = Field(default_factory=list)
    amount_clubs: list[str] = Field(default_factory=list)
    covering_lobs: list[str] = Field(default_factory=list)
    supervisor_id: str | None = None
    supervisor_display_name: str | None = None


class UserDirectoryResponse(BaseModel):
    count: int
    email_domain: str
    users: list[UserDirectoryRow]


class GroupMemberRow(BaseModel):
    user_id: str
    display_name: str
    title: str
    roles: list[str]
    groups: list[str] = Field(default_factory=list)
    covering_lobs: list[str] = Field(default_factory=list)


class GroupMembersResponse(BaseModel):
    group: str
    count: int
    members: list[GroupMemberRow]


class PolicyRequirement(BaseModel):
    kind: str
    value: str


class PolicySummaryResponse(BaseModel):
    domain: str
    action: str
    title: str
    narrative: str
    requires: list[PolicyRequirement] = Field(default_factory=list)
    source: str = "opa"


class PersonCapability(BaseModel):
    kind: str
    description: str


class PersonPermissionSummary(BaseModel):
    user_id: str
    display_name: str
    title: str
    lob: str | None = None
    roles: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    amount_clubs: list[str] = Field(default_factory=list)
    covering_lobs: list[str] = Field(default_factory=list)
    capabilities: list[PersonCapability] = Field(default_factory=list)
    narrative: str = ""


class PersonPermissionSummaryResponse(BaseModel):
    query: str
    count: int
    matches: list[PersonPermissionSummary] = Field(default_factory=list)
    source: str = "user_directory"


class PolicyDecisionResponse(BaseModel):
    allowed: bool
    allow_basis: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    is_alert: bool = False


class InstructionEvaluateRequest(BaseModel):
    action: str
    instruction: dict
    account: dict
    subject: Subject | None = None


class PaymentEvaluateRequest(BaseModel):
    action: str
    payment: dict
    instruction_end_date: str = ""
    instruction_status: str = ""
    subject: Subject | None = None


class PaymentEligibilityContext(BaseModel):
    payment_id: str
    instruction_id: str
    instruction_version: int
    status: str
    amount: float
    currency: str
    owning_lob: str
    instruction_type: str = ""
    created_by_user_id: str
    created_by_supervisor_id: str | None = None


class PaymentEligibleApproversEvaluateRequest(BaseModel):
    payment: PaymentEligibilityContext
    instruction_status: str
    instruction_end_date: str = ""


class InstructionEligibleApproversEvaluateRequest(BaseModel):
    instruction: dict
