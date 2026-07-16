from __future__ import annotations

import logging
from typing import Any

from chat_application.auth.capabilities import capabilities_for
from chat_application.auth.service_identity import service_identity
from chat_application.auth.subject import Subject
from chat_application.authz.obo import AuthzOboClient, AuthzOboClientError
from chat_application.formatting import (
    format_eligible_approvers_section,
    format_policy_basis_cell,
)
from chat_application.skills.detect import parse_submit_payment_params
from chat_application.skills.format import (
    confirmation_card_from_instruction,
    format_amount,
    format_submitted_payment_report,
)
from chat_application.skills.instruction_client import (
    InstructionClient,
    InstructionClientError,
    InstructionNotFoundError,
)
from chat_application.skills.models import SkillRunResult, SubmitPaymentParams
from chat_application.skills.payment_client import (
    PaymentClient,
    PaymentClientError,
    PaymentNotFoundError,
    PaymentSubmitDenied,
)
from chat_application.skills.pending_store import (
    build_submit_pending,
    pending_submit_payment_store,
)

logger = logging.getLogger(__name__)


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


async def run_submit_payment_phase1(
    message: str,
    *,
    subject: Subject,
    user_token: str | None,
    user_session_id: str | None,
    params: SubmitPaymentParams | None = None,
) -> SkillRunResult | None:
    """Parse → load payment + instruction → dry-run SUBMIT → confirmation card."""
    params = params or parse_submit_payment_params(message)
    if params is None:
        return None

    activities: list[str] = []
    caps = capabilities_for(subject)
    if not caps.can_create_payment:
        activities.append(
            f"Checked role — `{subject.user_id}` does not hold `PAYMENT_CREATOR`."
        )
        return SkillRunResult(
            answer=(
                f"**No Go from preflight** — `{subject.user_id}` cannot run the "
                "submit-payment skill (needs `PAYMENT_CREATOR`).\n\n"
                "No payment was submitted."
            ),
            activities=activities,
            intent_id="skill.submit_payment.forbidden",
            skill="submit_payment",
        )

    if not user_token:
        return SkillRunResult(
            answer="Sign-in token missing — cannot load the payment or evaluate policy.",
            activities=["Missing user session token."],
            intent_id="skill.submit_payment.auth_error",
            skill="submit_payment",
        )

    activities.append(f"Parsed request: submit payment `{params.payment_id}`.")
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
                "Nothing was submitted."
            ),
            activities=activities,
            intent_id="skill.submit_payment.payment_missing",
            skill="submit_payment",
        )
    except PaymentClientError as exc:
        activities.append(f"Could not load payment: {exc}")
        return SkillRunResult(
            answer=f"**Stopped** — could not load the payment ({exc}).",
            activities=activities,
            intent_id="skill.submit_payment.payment_error",
            skill="submit_payment",
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

    if payment_status != "DRAFT":
        activities.append(
            f"Payment status is **{payment_status}** — only DRAFT payments can be submitted."
        )
        return SkillRunResult(
            answer=(
                f"**Stopped** — payment `{params.payment_id}` is **{payment_status}**. "
                "Only **DRAFT** payments can be submitted for approval."
            ),
            activities=activities,
            intent_id="skill.submit_payment.wrong_status",
            skill="submit_payment",
        )

    if not instruction_id:
        return SkillRunResult(
            answer="**Stopped** — payment is missing an instruction id.",
            activities=["Payment had no instruction_id."],
            intent_id="skill.submit_payment.instruction_missing",
            skill="submit_payment",
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
                "Nothing was submitted."
            ),
            activities=activities,
            intent_id="skill.submit_payment.instruction_missing",
            skill="submit_payment",
        )
    except InstructionClientError as exc:
        activities.append(f"Could not load instruction: {exc}")
        return SkillRunResult(
            answer=f"**Stopped** — could not load the backing instruction ({exc}).",
            activities=activities,
            intent_id="skill.submit_payment.instruction_error",
            skill="submit_payment",
        )

    instruction_status = str(instruction.get("status") or "")
    instruction_end_date = str(instruction.get("end_date") or "")
    desk_lob = subject.lob or "—"
    activities.append(
        f"Loaded instruction `{instruction_id}` — status **{instruction_status}**, "
        f"owning LOB **{owning_lob}**."
    )
    activities.append(
        f"Checking if `{subject.user_id}` ({_display(subject)}) may **SUBMIT** "
        f"payment `{params.payment_id}` "
        f"(role `PAYMENT_CREATOR`, desk LOB **{desk_lob}** must match owning LOB "
        f"**{owning_lob}**, backing instruction APPROVED)…"
    )

    authz = AuthzOboClient()
    try:
        decision = await authz.evaluate_payment(
            action="SUBMIT",
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
            answer=f"**Stopped** — could not evaluate SUBMIT permission ({exc}).",
            activities=activities,
            intent_id="skill.submit_payment.evaluate_error",
            skill="submit_payment",
        )

    if not decision.allowed:
        reasons = "; ".join(decision.violations) or "policy denied"
        activities.append(f"**Denied** — {reasons}")
        return SkillRunResult(
            answer=(
                f"**No** — `{subject.user_id}` may not submit this payment under policy.\n\n"
                f"Violations: {reasons}\n\n"
                "Nothing was submitted."
            ),
            activities=activities,
            intent_id="skill.submit_payment.denied",
            skill="submit_payment",
        )

    basis = format_policy_basis_cell(decision.allow_basis) or "SUBMIT allowed"
    activities.append(
        f"**Yes** — `{subject.user_id}` ({_display(subject)}) may submit this payment. "
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
    pending = build_submit_pending(
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
    pending_submit_payment_store.put(pending)

    return SkillRunResult(
        answer=(
            "Preflight passed. Review the payment details below, then choose "
            "**Go** to submit for funding approval or **No Go** to cancel."
        ),
        activities=activities,
        pending_id=pending.pending_id,
        confirmation=card,
        intent_id="skill.submit_payment.awaiting_confirmation",
        skill="submit_payment",
    )


async def confirm_submit_payment(
    *,
    pending_id: str,
    decision: str,
    subject: Subject,
    user_token: str | None,
    user_session_id: str | None,
) -> SkillRunResult:
    """Resume after Go / No Go for submit-payment."""
    pending = pending_submit_payment_store.get(pending_id)
    if pending is None:
        return SkillRunResult(
            answer=(
                "That confirmation expired or was already used. "
                "Ask again to submit the payment if you still need it."
            ),
            activities=["Pending skill not found or expired."],
            intent_id="skill.submit_payment.pending_missing",
            skill="submit_payment",
        )

    if pending.user_id != subject.user_id:
        return SkillRunResult(
            answer="This confirmation belongs to another user. Nothing was submitted.",
            activities=["Pending skill user mismatch."],
            intent_id="skill.submit_payment.pending_forbidden",
            skill="submit_payment",
        )

    if decision == "no_go":
        pending_submit_payment_store.pop(pending_id)
        return SkillRunResult(
            answer="**No Go** — cancelled. Nothing was submitted.",
            activities=["User selected No Go — pending submit discarded."],
            intent_id="skill.submit_payment.cancelled",
            skill="submit_payment",
        )

    if decision != "go":
        return SkillRunResult(
            answer='Decision must be `"go"` or `"no_go"`.',
            activities=[f"Invalid decision: {decision}"],
            intent_id="skill.submit_payment.bad_decision",
            skill="submit_payment",
        )

    if not user_token:
        return SkillRunResult(
            answer="Sign-in token missing — cannot submit the payment.",
            activities=["Missing user session token on confirm."],
            intent_id="skill.submit_payment.auth_error",
            skill="submit_payment",
        )

    pending = pending_submit_payment_store.pop(pending_id)
    if pending is None:
        return SkillRunResult(
            answer="That confirmation was already used. No additional submit was sent.",
            activities=["Pending skill already consumed."],
            intent_id="skill.submit_payment.pending_missing",
            skill="submit_payment",
        )

    activities = [
        f"Go selected — submitting payment `{pending.payment_id}` for funding approval…",
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
            action="SUBMIT",
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
            activities.append(f"Re-check denied SUBMIT: {reasons}")
            return SkillRunResult(
                answer=(
                    f"**Stopped before submit** — policy no longer allows SUBMIT "
                    f"({reasons}). Nothing was submitted."
                ),
                activities=activities,
                intent_id="skill.submit_payment.recheck_denied",
                skill="submit_payment",
            )
    except AuthzOboClientError as exc:
        logger.warning("submit-payment confirm recheck failed: %s — proceeding", exc)
        activities.append(
            f"Could not re-check policy ({exc}); payment-service will enforce SUBMIT."
        )

    payment_client = PaymentClient()
    try:
        payment = await payment_client.submit_payment(
            pending.payment_id,
            user_token=user_token,
            user_session_id=user_session_id,
        )
    except PaymentSubmitDenied as exc:
        activities.append(f"SUBMIT denied by payment-service: {exc.detail}")
        return SkillRunResult(
            answer=f"**Submit denied** — {exc.detail}\n\nNothing was persisted.",
            activities=activities,
            intent_id="skill.submit_payment.submit_denied",
            skill="submit_payment",
        )
    except PaymentClientError as exc:
        activities.append(f"SUBMIT failed: {exc}")
        return SkillRunResult(
            answer=f"**Submit failed** — {exc}",
            activities=activities,
            intent_id="skill.submit_payment.submit_error",
            skill="submit_payment",
        )

    payment_id = str(payment.get("payment_id") or pending.payment_id)
    activities.append(f"Submitted payment `{payment_id}` (status SUBMITTED).")
    activities.append("Looking up who can approve…")

    approvers_section = await _eligible_approvers_section(
        payment=payment,
        instruction_status=pending.instruction_status,
        instruction_end_date=pending.instruction_end_date,
    )
    if approvers_section:
        activities.append("Eligible approvers loaded.")
    else:
        activities.append("Eligible approvers unavailable — see note in the report.")

    return SkillRunResult(
        answer=format_submitted_payment_report(
            payment,
            card=pending.card,
            approvers_section=approvers_section,
        ),
        activities=activities,
        intent_id="skill.submit_payment.submitted",
        skill="submit_payment",
    )


async def _eligible_approvers_section(
    *,
    payment: dict[str, Any],
    instruction_status: str,
    instruction_end_date: str,
) -> str | None:
    if not service_identity.token:
        return None

    authz = AuthzOboClient()
    created_by = payment.get("created_by") or {}
    try:
        data = await authz.eligible_payment_approvers(
            payment={
                "payment_id": payment.get("payment_id"),
                "instruction_id": payment.get("instruction_id"),
                "instruction_version": payment.get("instruction_version") or 1,
                "status": payment.get("status") or "SUBMITTED",
                "amount": payment.get("amount"),
                "currency": payment.get("currency"),
                "owning_lob": payment.get("owning_lob"),
                "instruction_type": payment.get("instruction_type") or "",
                "created_by_user_id": created_by.get("user_id") or "",
                "created_by_supervisor_id": created_by.get("supervisor_id"),
            },
            instruction_status=instruction_status,
            instruction_end_date=instruction_end_date,
            service_token=service_identity.token,
            service_session_id=service_identity.session_id,
        )
    except Exception as exc:
        logger.warning("eligible approvers lookup failed: %s", exc)
        return None

    eligible = list(data.get("eligible") or [])
    return format_eligible_approvers_section(
        header=f"### Who can approve `{payment.get('payment_id')}`",
        section_title="Eligible funding approvers",
        eligible=eligible,
        empty_message="No eligible funding approvers were found for this payment.",
        candidate_role_label="FUNDING_APPROVER",
        candidates_evaluated=data.get("candidates_evaluated"),
    )


__all__ = [
    "confirm_submit_payment",
    "run_submit_payment_phase1",
]
