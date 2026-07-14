import re
from enum import StrEnum

# FICC, FX, or desk codes such as DESK_RATES, DESK_CREDIT
OWNING_LOB_PATTERN = re.compile(r"^(FICC|FX|DESK_[A-Z][A-Z0-9_]*)$")


def is_valid_owning_lob(value: str) -> bool:
    return bool(OWNING_LOB_PATTERN.match(value))


class InstructionType(StrEnum):
    """How long the instruction remains available for payment."""

    STANDING = "STANDING"
    SINGLE_USE = "SINGLE_USE"


class InstructionStatus(StrEnum):
    """Lifecycle state — orthogonal to instruction_type (STANDING vs SINGLE_USE)."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    SUSPENDED = "SUSPENDED"
    REJECTED = "REJECTED"
    USED = "USED"
    CANCELLED = "CANCELLED"


class WireScope(StrEnum):
    """Domestic or cross-border cash wire."""

    DOMESTIC = "DOMESTIC"
    INTERNATIONAL = "INTERNATIONAL"


class ChargeBearer(StrEnum):
    """ISO 20022 ChargeBearerType1Code."""

    DEBT = "DEBT"  # debtor pays all charges (OUR)
    CRED = "CRED"  # creditor pays (BEN)
    SHAR = "SHAR"  # shared (SHA)
    SLEV = "SLEV"  # service level charges


class AccountIdentificationScheme(StrEnum):
    """ISO 20022 AccountIdentification4Choice schemes."""

    IBAN = "IBAN"
    BBAN = "BBAN"
    PROPRIETARY = "PROPRIETARY"


class FinancialInstitutionIdScheme(StrEnum):
    """ISO 20022 FinancialInstitutionIdentification18 identification."""

    BICFI = "BICFI"
    CLEARING_SYSTEM = "CLEARING_SYSTEM"
    PROPRIETARY = "PROPRIETARY"


class LifecycleAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    CANCEL = "CANCEL"
    SUBMIT = "SUBMIT"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    SUSPEND = "SUSPEND"
    REACTIVATE = "REACTIVATE"
    USE = "USE"
    RELEASE_USE = "RELEASE_USE"
    VIEW = "VIEW"


class SecurityEventSeverity(StrEnum):
    """Severity for security event monitoring — INFO for allows, ALERT for denials."""

    INFO = "INFO"
    ALERT = "ALERT"


class SecurityEventOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
