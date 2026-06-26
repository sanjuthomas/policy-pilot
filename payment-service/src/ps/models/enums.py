from enum import StrEnum


class PaymentStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class PaymentAction(StrEnum):
    CREATE_PAYMENT = "CREATE_PAYMENT"
    SUBMIT_PAYMENT = "SUBMIT_PAYMENT"
    APPROVE_PAYMENT = "APPROVE_PAYMENT"
    REJECT_PAYMENT = "REJECT_PAYMENT"
    CANCEL_PAYMENT = "CANCEL_PAYMENT"


class SecurityEventSeverity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    ALERT = "ALERT"
    CRITICAL = "CRITICAL"


class SecurityEventOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
