from __future__ import annotations

from enum import StrEnum


class PipelineKind(StrEnum):
    INSTRUCTION_SECURITY_EVENT = "instruction_security_event"
    INSTRUCTION_FACT = "instruction_fact"
    PAYMENT_SECURITY_EVENT = "payment_security_event"
    PAYMENT_FACT = "payment_fact"


class DlqStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    EXHAUSTED = "exhausted"
    POISON = "poison"


class FailureClass(StrEnum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    POISON = "poison"
    DOWNSTREAM = "downstream"
