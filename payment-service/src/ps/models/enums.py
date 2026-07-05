from enum import StrEnum


class PaymentStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class PaymentAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    SUBMIT = "SUBMIT"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CANCEL = "CANCEL"


class SecurityEventSeverity(StrEnum):
    """Severity for security event monitoring — INFO for allows, ALERT for denials."""

    INFO = "INFO"
    ALERT = "ALERT"


class SecurityEventOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
