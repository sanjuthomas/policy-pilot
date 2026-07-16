from __future__ import annotations

import logging
from typing import Any

from chat_application.auth.capabilities import capabilities_for
from chat_application.auth.service_identity import service_identity
from chat_application.auth.subject import Subject
from chat_application.authz.obo import AuthzOboClient, AuthzOboClientError
from chat_application.formatting import format_policy_basis_cell
from chat_application.skills.detect import parse_cancel_payment_params
from chat_application.skills.format import (
    confirmation_card_from_instruction,
    format_amount,
    format_cancelled_payment_report,
)
from chat_application.skills.instruction_client import (
    InstructionClient,
    InstructionClientError,
    InstructionNotFoundError,
)
from chat_application.skills.models import CancelPaymentParams, SkillRunResult
from chat_application.skills.payment_client import (
    PaymentCancelDenied,
    PaymentClient,
    PaymentClientError,
    PaymentNotFoundError,
)
from chat_application.skills.pending_store import (
    build_cancel_pending,
    pending_cancel_payment_store,
)

logger = logging.getLogger(__name__)

_CANCELLABLE_STATUSES = frozenset({"DRAFT", "SUBMITTED"})


def _display(subject: Subject) -> str:
    if subject.family_name and subject.given_name:
        return f"{subject.family_name}, {subject.given_name}"
    return subject.user_id


def _opa_payment_payload(
    *,
    payment: dict[str, Any],
    instruction: dict[str, Any],
) -> dict[str, Any]:
    created_by = payment.get("created_by") or {}
    return {
        "payment_id": payment.get("payment_id"),
        "instruction_id": payment.get("instruction_id"),
        "instruction_version": int(
            payment.get("instruction_version")
            or instruction.get("version_number")
            or 1
        ),
        "status": payment.get("status") or "DRAFT",
        "amount": payment.get("amount"),
        "currency": payment.get("currency") or instruction.get("currency") or "",
        "instruction_status": instruction.get("status") or "",
        "instruction_end_date": instruction.get("end_date") or "",
        "instruction_type": (
            payment.get("instruction_type")
            or instruction.get("instruction_type")
            or ""
        ),
        "instruction_owning_lob": (
            payment.get("owning_lob") or instruction.get("owning_lob") or ""
        ),
        "created_by": {
            "user_id": created_by.get("user_id") or "",
            "supervisor_id": created_by.get("supervisor_id"),
        },
    }


async def run_cancel_payment_phase1(
    message: str,
    *,
    subject: Subject,
    user_token: str | None,
    user_session_id: str | None,
    params: CancelPaymentParams | None = None,
) -> SkillRunResult | None:
    """Parse → load payment + instruction → dry-run CANCEL → confirmation card."""
    params = params or parse_cancel_payment_params(message)
    if params is None:
        return None

    activities: list[str] = []
    caps = capabilities_for(subject)
    if not caps.can_cancel_payment:
        activities.append(
            f"Checked role/group — `{subject.user_id}` cannot cancel payments "
            "(needs `PAYMENT_CREATOR` + `MIDDLE_OFFICE`)."
        )
        return SkillRunResult(
            answer=(
                f"**No Go from preflight** — `{subject.user_id}` cannot run the "
                "cancel-payment skill (needs `PAYMENT_CREATOR` and `MIDDLE_OFFICE`).\n\n"
                "No payment was cancelled."
            ),
            activities=activities,
            intent_id="skill.cancel_payment.forbidden",
            skill="cancel_payment",
        )

    if not user_token:
        return SkillRunResult(
            answer="Sign-in token missing — cannot load the payment or evaluate policy.",
            activities=["Missing user session token."],
            intent_id="skill.cancel_payment.auth_error",
            skill="cancel_payment",
        )

    activities.append(f"Parsed request: cancel payment `{params.payment_id}`.")
    activities.append(f"Loading payment `{params.payment_id}`…")

    payment_client = PaymentClient()
    try:
        payment = await payment_client.get_payment(
            params.payment_id,
            user_token=user_token,
            user_session_id=user_session_id,
        )
    except PaymentNotFoundError:
        activities.append(f"Payment `{params.payment_id}` was not found.")
        return SkillRunResult(
            answer=(
                f"**Stopped** — payment `{params.payment_id}` was not found. "
                "Nothing was cancelled."
            ),
            activities=activities,
            intent_id="skill.cancel_payment.payment_missing",
            skill="cancel_payment",
        )
    except PaymentClientError as exc:
        activities.append(f"Could not load payment: {exc}")
        return SkillRunResult(
            answer=f"**Stopped** — could not load the payment ({exc}).",
            activities=activities,
            intent_id="skill.cancel_payment.payment_error",
            skill="cancel_payment",
        )

    payment_status = str(payment.get("status") or "")
    instruction_id = str(payment.get("instruction_id") or "")
    amount = float(payment.get("amount") or 0)
    currency = str(payment.get("currency") or "USD")
    owning_lob = str(payment.get("owning_lob") or "—")
    value_date = str(payment.get("value_date") or "")
    activities.append(
        f"Loaded payment `{params.payment_id}` — status **{payment_status}**, "
        f"LOB **{owning_lob}**, amount **{format_amount(amount, currency)}**."
    )

    if payment_status not in _CANCELLABLE_STATUSES:
        activities.append(
            f"Payment status is **{payment_status}** — only DRAFT or SUBMITTED "
            "payments can be cancelled."
        )
        return SkillRunResult(
            answer=(
                f"**Stopped** — payment `{params.payment_id}` is **{payment_status}**. "
                "Only **DRAFT** or **SUBMITTED** payments can be cancelled."
            ),
            activities=activities,
            intent_id="skill.cancel_payment.wrong_status",
            skill="cancel_payment",
        )

    if not instruction_id:
        return SkillRunResult(
            answer="**Stopped** — payment is missing an instruction id.",
            activities=["Payment had no instruction_id."],
            intent_id="skill.cancel_payment.instruction_missing",
            skill="cancel_payment",
        )

    activities.append(f"Loading backing instruction `{instruction_id}`…")
    instruction_client = InstructionClient()
    try:
        instruction = await instruction_client.get_instruction(
            instruction_id,
            user_token=user_token,
            user_session_id=user_session_id,
        )
    except InstructionNotFoundError:
        activities.append(f"Instruction `{instruction_id}` was not found.")
        return SkillRunResult(
            answer=(
                f"**Stopped** — backing instruction `{instruction_id}` was not found. "
                "Nothing was cancelled."
            ),
            activities=activities,
            intent_id="skill.cancel_payment.instruction_missing",
            skill="cancel_payment",
        )
    except InstructionClientError as exc:
        activities.append(f"Could not load instruction: {exc}")
        return SkillRunResult(
            answer=f"**Stopped** — could not load the backing instruction ({exc}).",
            activities=activities,
            intent_id="skill.cancel_payment.instruction_error",
            skill="cancel_payment",
        )

    instruction_status = str(instruction.get("status") or "")
    instruction_end_date = str(instruction.get("end_date") or "")
    covering = ", ".join(subject.covering_lobs) or "—"
    activities.append(
        f"Loaded instruction `{instruction_id}` — status **{instruction_status}**, "
        f"owning LOB **{owning_lob}**."
    )
    activities.append(
        f"Checking if `{subject.user_id}` ({_display(subject)}) may **CANCEL** "
        f"payment `{params.payment_id}` "
        f"(role `PAYMENT_CREATOR`, group `MIDDLE_OFFICE`, covering [{covering}])…"
    )

    authz = AuthzOboClient()
    try:
        decision = await authz.evaluate_payment(
            action="CANCEL",
            payment=_opa_payment_payload(payment=payment, instruction=instruction),
            instruction_status=instruction_status,
            instruction_end_date=instruction_end_date,
            service_token=service_identity.token,
            service_session_id=service_identity.session_id,
            user_token=user_token,
            user_session_id=user_session_id,
            subject=subject.model_dump(),
        )
    except AuthzOboClientError as exc:
        activities.append(f"Policy evaluate failed: {exc}")
        return SkillRunResult(
            answer=f"**Stopped** — could not evaluate CANCEL permission ({exc}).",
            activities=activities,
            intent_id="skill.cancel_payment.evaluate_error",
            skill="cancel_payment",
        )

    if not decision.allowed:
        reasons = "; ".join(decision.violations) or "policy denied"
        activities.append(f"**Denied** — {reasons}")
        return SkillRunResult(
            answer=(
                f"**No** — `{subject.user_id}` may not cancel this payment under policy.\n\n"
                f"Violations: {reasons}\n\n"
                "Nothing was cancelled."
            ),
            activities=activities,
            intent_id="skill.cancel_payment.denied",
            skill="cancel_payment",
        )

    basis = format_policy_basis_cell(decision.allow_basis) or "CANCEL allowed"
    activities.append(
        f"**Yes** — `{subject.user_id}` ({_display(subject)}) may cancel this payment. "
        f"Basis: {basis}"
    )

    card = confirmation_card_from_instruction(
        instruction,
        amount=amount,
        value_date=value_date,
        payment_id=params.payment_id,
        payment_status=payment_status,
    )
    created_by = payment.get("created_by") or {}
    pending = build_cancel_pending(
        user_id=subject.user_id,
        payment_id=params.payment_id,
        instruction_id=instruction_id,
        amount=amount,
        value_date=value_date,
        currency=currency,
        owning_lob=owning_lob,
        payment_status=payment_status,
        instruction_status=instruction_status,
        instruction_end_date=instruction_end_date,
        instruction_type=str(
            payment.get("instruction_type") or instruction.get("instruction_type") or ""
        ),
        instruction_version=int(
            payment.get("instruction_version") or instruction.get("version_number") or 1
        ),
        created_by_user_id=str(created_by.get("user_id") or ""),
        created_by_supervisor_id=created_by.get("supervisor_id"),
        card=card,
    )
    pending_cancel_payment_store.put(pending)

    return SkillRunResult(
        answer=(
            "Preflight passed. Review the payment details below, then choose "
            "**Go** to cancel the payment or **No Go** to keep it."
        ),
        activities=activities,
        pending_id=pending.pending_id,
        confirmation=card,
        intent_id="skill.cancel_payment.awaiting_confirmation",
        skill="cancel_payment",
    )


async def confirm_cancel_payment(
    *,
    pending_id: str,
    decision: str,
    subject: Subject,
    user_token: str | None,
    user_session_id: str | None,
) -> SkillRunResult:
    """Resume after Go / No Go for cancel-payment."""
    pending = pending_cancel_payment_store.get(pending_id)
    if pending is None:
        return SkillRunResult(
            answer=(
                "That confirmation expired or was already used. "
                "Ask again to cancel the payment if you still need it."
            ),
            activities=["Pending skill not found or expired."],
            intent_id="skill.cancel_payment.pending_missing",
            skill="cancel_payment",
        )

    if pending.user_id != subject.user_id:
        return SkillRunResult(
            answer="This confirmation belongs to another user. Nothing was cancelled.",
            activities=["Pending skill user mismatch."],
            intent_id="skill.cancel_payment.pending_forbidden",
            skill="cancel_payment",
        )

    if decision == "no_go":
        pending_cancel_payment_store.pop(pending_id)
        return SkillRunResult(
            answer="**No Go** — cancelled. Nothing was changed on the payment.",
            activities=["User selected No Go — pending cancel discarded."],
            intent_id="skill.cancel_payment.no_go",
            skill="cancel_payment",
        )

    if decision != "go":
        return SkillRunResult(
            answer='Decision must be `"go"` or `"no_go"`.',
            activities=[f"Invalid decision: {decision}"],
            intent_id="skill.cancel_payment.bad_decision",
            skill="cancel_payment",
        )

    if not user_token:
        return SkillRunResult(
            answer="Sign-in token missing — cannot cancel the payment.",
            activities=["Missing user session token on confirm."],
            intent_id="skill.cancel_payment.auth_error",
            skill="cancel_payment",
        )

    pending = pending_cancel_payment_store.pop(pending_id)
    if pending is None:
        return SkillRunResult(
            answer="That confirmation was already used. No additional cancel was sent.",
            activities=["Pending skill already consumed."],
            intent_id="skill.cancel_payment.pending_missing",
            skill="cancel_payment",
        )

    activities = [
        f"Go selected — cancelling payment `{pending.payment_id}`…",
    ]

    authz = AuthzOboClient()
    payment_payload = {
        "payment_id": pending.payment_id,
        "instruction_id": pending.instruction_id,
        "instruction_version": pending.instruction_version,
        "status": pending.payment_status,
        "amount": pending.amount,
        "currency": pending.currency,
        "instruction_status": pending.instruction_status,
        "instruction_end_date": pending.instruction_end_date,
        "instruction_type": pending.instruction_type,
        "instruction_owning_lob": pending.owning_lob,
        "created_by": {
            "user_id": pending.created_by_user_id,
            "supervisor_id": pending.created_by_supervisor_id,
        },
    }
    try:
        decision_result = await authz.evaluate_payment(
            action="CANCEL",
            payment=payment_payload,
            instruction_status=pending.instruction_status,
            instruction_end_date=pending.instruction_end_date,
            service_token=service_identity.token,
            service_session_id=service_identity.session_id,
            user_token=user_token,
            user_session_id=user_session_id,
            subject=subject.model_dump(),
        )
        if not decision_result.allowed:
            reasons = "; ".join(decision_result.violations) or "policy denied"
            activities.append(f"Re-check denied CANCEL: {reasons}")
            return SkillRunResult(
                answer=(
                    f"**Stopped before cancel** — policy no longer allows CANCEL "
                    f"({reasons}). Nothing was cancelled."
                ),
                activities=activities,
                intent_id="skill.cancel_payment.recheck_denied",
                skill="cancel_payment",
            )
    except AuthzOboClientError as exc:
        logger.warning("cancel-payment confirm recheck failed: %s — proceeding", exc)
        activities.append(
            f"Could not re-check policy ({exc}); payment-service will enforce CANCEL."
        )

    payment_client = PaymentClient()
    try:
        payment = await payment_client.cancel_payment(
            pending.payment_id,
            user_token=user_token,
            user_session_id=user_session_id,
        )
    except PaymentCancelDenied as exc:
        activities.append(f"CANCEL denied by payment-service: {exc.detail}")
        return SkillRunResult(
            answer=f"**Cancel denied** — {exc.detail}\n\nNothing was persisted.",
            activities=activities,
            intent_id="skill.cancel_payment.cancel_denied",
            skill="cancel_payment",
        )
    except PaymentClientError as exc:
        activities.append(f"CANCEL failed: {exc}")
        return SkillRunResult(
            answer=f"**Cancel failed** — {exc}",
            activities=activities,
            intent_id="skill.cancel_payment.cancel_error",
            skill="cancel_payment",
        )

    payment_id = str(payment.get("payment_id") or pending.payment_id)
    activities.append(f"Cancelled payment `{payment_id}` (status CANCELLED).")

    return SkillRunResult(
        answer=format_cancelled_payment_report(
            payment,
            card=pending.card,
            canceller_display=_display(subject),
        ),
        activities=activities,
        intent_id="skill.cancel_payment.cancelled",
        skill="cancel_payment",
    )


__all__ = [
    "confirm_cancel_payment",
    "run_cancel_payment_phase1",
]
