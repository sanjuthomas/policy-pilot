from __future__ import annotations

from dataclasses import dataclass

from chat_application.subject import Subject

COMPLIANCE_ROLES = frozenset(
    {"COMPLIANCE_ANALYST", "COMPLIANCE_OFFICER", "PLATFORM_ADMIN"}
)
OPERATIONAL_ROLES = frozenset({"PAYMENT_CREATOR", "FUNDING_APPROVER"})


@dataclass(frozen=True)
class ChatCapabilities:
    """Derived chat capabilities from the logged-in subject's roles."""

    is_compliance: bool
    can_create_payment: bool
    can_approve_payment: bool

    @property
    def is_operational(self) -> bool:
        return self.can_create_payment or self.can_approve_payment


def capabilities_for(subject: Subject) -> ChatCapabilities:
    roles = set(subject.roles)
    return ChatCapabilities(
        is_compliance=bool(roles & COMPLIANCE_ROLES),
        can_create_payment="PAYMENT_CREATOR" in roles,
        can_approve_payment="FUNDING_APPROVER" in roles,
    )


def audience_labels(roles: list[str]) -> list[str]:
    """Human-readable audience tags for the login picker."""
    role_set = set(roles)
    labels: list[str] = []
    if role_set & COMPLIANCE_ROLES:
        labels.append("compliance")
    if "PAYMENT_CREATOR" in role_set:
        labels.append("payment_creator")
    if "FUNDING_APPROVER" in role_set:
        labels.append("funding_approver")
    return labels
