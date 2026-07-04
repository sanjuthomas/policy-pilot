from __future__ import annotations

_TERMINAL_INSTRUCTION_STATUSES = frozenset({"USED", "REJECTED", "EXPIRED", "DELETED"})
_TERMINAL_PAYMENT_STATUSES = frozenset({"APPROVED", "REJECTED", "CANCELLED", "DELETED"})


def _backing_instruction_label(instruction_id: str | None) -> str:
    instruction_id = str(instruction_id or "").strip()
    if instruction_id:
        return f"The backing instruction {instruction_id}"
    return "The backing instruction"


def payment_approval_blocked_reason(
    payment_status: str,
    instruction_status: str,
    *,
    instruction_id: str | None = None,
    instruction_type: str | None = None,
    payment_instruction_type: str | None = None,
) -> str | None:
    """Explain why APPROVE_PAYMENT is not permitted in the current lifecycle state."""
    payment_status = str(payment_status or "")
    instruction_status = str(instruction_status or "")
    instruction_type = str(instruction_type or "")
    payment_instruction_type = str(payment_instruction_type or "")
    instruction_label = _backing_instruction_label(instruction_id)

    if payment_status in _TERMINAL_PAYMENT_STATUSES:
        if payment_status == "APPROVED":
            return "This payment is already APPROVED."
        return f"This payment is {payment_status} and cannot be approved."

    single_use_consumed = (
        instruction_status == "USED"
        and instruction_type == "SINGLE_USE"
        and payment_instruction_type == "SINGLE_USE"
    )

    if instruction_status in _TERMINAL_INSTRUCTION_STATUSES:
        if single_use_consumed and payment_status == "SUBMITTED":
            pass
        else:
            return (
                f"{instruction_label} is {instruction_status} and cannot support "
                "payment approval."
            )

    if instruction_status and instruction_status != "APPROVED" and not single_use_consumed:
        return (
            f"{instruction_label} is {instruction_status}; it must be APPROVED "
            "before a payment can be approved."
        )

    if payment_status == "DRAFT":
        return (
            "Payment approval is not permitted while status is DRAFT. "
            "Submit the payment first."
        )

    return None


def payment_prospective_instruction_status(
    instruction_status: str,
    *,
    instruction_type: str = "",
    payment_instruction_type: str = "",
) -> str | None:
    """Instruction status to use for hypothetical approver evaluation."""
    instruction_status = str(instruction_status or "")
    if instruction_status == "APPROVED":
        return "APPROVED"
    if (
        instruction_status == "USED"
        and instruction_type == "SINGLE_USE"
        and payment_instruction_type == "SINGLE_USE"
    ):
        return "USED"
    return None
