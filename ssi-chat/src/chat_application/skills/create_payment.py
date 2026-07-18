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
from chat_application.skills.detect import parse_create_payment_params
from chat_application.skills.format import (
    confirmation_card_from_instruction,
    format_amount,
    format_created_payment_report,
)
from chat_application.skills.instruction_client import (
    InstructionClient,
    InstructionClientError,
    InstructionNotFoundError,
)
from chat_application.skills.models import CreatePaymentParams, SkillRunResult
from chat_application.skills.payment_client import (
    PaymentClient,
    PaymentClientError,
    PaymentCreateDenied,
)
from chat_application.skills.pending_store import (
    build_pending,
    pending_create_payment_store,
)

logger = logging.getLogger(__name__)


def _display(subject: Subject) -> str:
    if subject.family_name and subject.given_name:
        return f"{subject.family_name}, {subject.given_name}"
    return subject.user_id


def _clubs(subject: Subject) -> list[str]:
    return [
        group
        for group in subject.groups
        if group.endswith("_CLUB") or "MILLION" in group or "BILLION" in group
    ]


def _synthetic_payment_payload(
    *,
    params: CreatePaymentParams,
    instruction: dict[str, Any],
    subject: Subject,
) -> dict[str, Any]:
    return {
        "payment_id": "SKILL-PREFLIGHT",
        "instruction_id": params.instruction_id,
        "instruction_version": int(instruction.get("version_number") or 1),
        "status": "DRAFT",
        "amount": params.amount,
        "currency": instruction.get("currency") or "",
        "instruction_status": instruction.get("status") or "",
        "instruction_end_date": instruction.get("end_date") or "",
        "instruction_type": instruction.get("instruction_type") or "",
        "instruction_owning_lob": instruction.get("owning_lob") or "",
        "created_by": {
            "user_id": subject.user_id,
            "supervisor_id": subject.supervisor_id,
        },
    }


async def run_create_payment_phase1(
    message: str,
    *,
    subject: Subject,
    user_token: str | None,
    user_session_id: str | None,
    params: CreatePaymentParams | None = None,
) -> SkillRunResult | None:
    """Parse → load instruction → dry-run CREATE → confirmation card (no mutate)."""
    params = params or parse_create_payment_params(message)
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
                "create-payment skill (needs `PAYMENT_CREATOR`).\n\n"
                "No payment was created."
            ),
            activities=activities,
            intent_id="skill.create_payment.forbidden",
        )

    if not user_token:
        return SkillRunResult(
            answer="Sign-in token missing — cannot load the instruction or evaluate policy.",
            activities=["Missing user session token."],
            intent_id="skill.create_payment.auth_error",
        )

    activities.append(
        "Parsed request: instruction "
        f"`{params.instruction_id}`, amount **{params.amount:,.0f}**, "
        f"value date **{params.value_date}**."
    )
    activities.append(f"Loading instruction `{params.instruction_id}`…")

    instruction_client = InstructionClient()
    try:
        instruction = await instruction_client.get_instruction(
            params.instruction_id,
            user_token=user_token,
            user_session_id=user_session_id,
        )
    except InstructionNotFoundError:
        activities.append(f"Instruction `{params.instruction_id}` was not found.")
        return SkillRunResult(
            answer=(
                f"**Stopped** — instruction `{params.instruction_id}` was not found. "
                "No payment was created."
            ),
            activities=activities,
            intent_id="skill.create_payment.instruction_missing",
        )
    except InstructionClientError as exc:
        activities.append(f"Could not load instruction: {exc}")
        return SkillRunResult(
            answer=f"**Stopped** — could not load the instruction ({exc}).",
            activities=activities,
            intent_id="skill.create_payment.instruction_error",
        )

    owning_lob = str(instruction.get("owning_lob") or "—")
    currency = str(instruction.get("currency") or "")
    status = str(instruction.get("status") or "")
    activities.append(
        f"Loaded instruction `{params.instruction_id}` — LOB **{owning_lob}**, "
        f"status **{status}**, currency **{currency}**."
    )

    clubs = _clubs(subject)
    covering = ", ".join(subject.covering_lobs) or "—"
    club_text = ", ".join(clubs) or "—"
    activities.append(
        f"Checking if `{subject.user_id}` ({_display(subject)}) may **CREATE** a "
        f"payment for LOB **{owning_lob}** "
        f"(role `PAYMENT_CREATOR`, group `MIDDLE_OFFICE`, covering [{covering}], "
        f"clubs [{club_text}], amount {format_amount(params.amount, currency or 'USD')})…"
    )

    authz = AuthzOboClient()
    try:
        decision = await authz.evaluate_payment(
            action="CREATE",
            payment=_synthetic_payment_payload(
                params=params, instruction=instruction, subject=subject
            ),
            instruction_status=status,
            instruction_end_date=str(instruction.get("end_date") or ""),
            service_token=service_identity.token,
            service_session_id=service_identity.session_id,
            user_token=user_token,
            user_session_id=user_session_id,
            subject=subject.model_dump(),
        )
    except AuthzOboClientError as exc:
        activities.append(f"Policy evaluate failed: {exc}")
        return SkillRunResult(
            answer=f"**Stopped** — could not evaluate CREATE permission ({exc}).",
            activities=activities,
            intent_id="skill.create_payment.evaluate_error",
        )

    if not decision.allowed:
        reasons = "; ".join(decision.violations) or "policy denied"
        activities.append(f"**Denied** — {reasons}")
        return SkillRunResult(
            answer=(
                f"**No** — `{subject.user_id}` may not create this payment under policy.\n\n"
                f"Violations: {reasons}\n\n"
                "No payment was created."
            ),
            activities=activities,
            intent_id="skill.create_payment.denied",
        )

    basis = format_policy_basis_cell(decision.allow_basis) or "CREATE allowed"
    activities.append(
        f"**Yes** — `{subject.user_id}` ({_display(subject)}) may create this draft. "
        f"Basis: {basis}"
    )

    card = confirmation_card_from_instruction(
        instruction,
        amount=params.amount,
        value_date=params.value_date,
    )
    pending = build_pending(
        user_id=subject.user_id,
        instruction_id=params.instruction_id,
        amount=params.amount,
        value_date=params.value_date,
        currency=currency,
        owning_lob=owning_lob,
        instruction_status=status,
        instruction_end_date=str(instruction.get("end_date") or ""),
        instruction_type=str(instruction.get("instruction_type") or ""),
        instruction_version=int(instruction.get("version_number") or 1),
        card=card,
    )
    pending_create_payment_store.put(pending)

    return SkillRunResult(
        answer=(
            "Preflight passed. Review the payment details below, then choose "
            "**Go** to create the draft or **No Go** to cancel."
        ),
        activities=activities,
        pending_id=pending.pending_id,
        confirmation=card,
        intent_id="skill.create_payment.awaiting_confirmation",
    )


async def confirm_create_payment(
    *,
    pending_id: str,
    decision: str,
    subject: Subject,
    user_token: str | None,
    user_session_id: str | None,
) -> SkillRunResult:
    """Resume after Go / No Go."""
    pending = pending_create_payment_store.get(pending_id)
    if pending is None:
        return SkillRunResult(
            answer=(
                "That confirmation expired or was already used. "
                "Ask again to create the payment if you still need it."
            ),
            activities=["Pending skill not found or expired."],
            intent_id="skill.create_payment.pending_missing",
        )

    if pending.user_id != subject.user_id:
        return SkillRunResult(
            answer="This confirmation belongs to another user. No payment was created.",
            activities=["Pending skill user mismatch."],
            intent_id="skill.create_payment.pending_forbidden",
        )

    if decision == "no_go":
        pending_create_payment_store.pop(pending_id)
        return SkillRunResult(
            answer="**No Go** — cancelled. No payment was created.",
            activities=["User selected No Go — pending create discarded."],
            intent_id="skill.create_payment.cancelled",
        )

    if decision != "go":
        return SkillRunResult(
            answer='Decision must be `"go"` or `"no_go"`.',
            activities=[f"Invalid decision: {decision}"],
            intent_id="skill.create_payment.bad_decision",
        )

    if not user_token:
        return SkillRunResult(
            answer="Sign-in token missing — cannot create the payment.",
            activities=["Missing user session token on confirm."],
            intent_id="skill.create_payment.auth_error",
        )

    # Consume pending before mutate so double-click cannot create twice.
    pending = pending_create_payment_store.pop(pending_id)
    if pending is None:
        return SkillRunResult(
            answer="That confirmation was already used. No additional payment was created.",
            activities=["Pending skill already consumed."],
            intent_id="skill.create_payment.pending_missing",
        )

    activities = [
        f"Go selected — creating draft payment for instruction `{pending.instruction_id}`…",
    ]

    # Re-check policy before mutate (instruction/status may have changed).
    authz = AuthzOboClient()
    payment_payload = {
        "payment_id": "SKILL-PREFLIGHT",
        "instruction_id": pending.instruction_id,
        "instruction_version": pending.instruction_version,
        "status": "DRAFT",
        "amount": pending.amount,
        "currency": pending.currency,
        "instruction_status": pending.instruction_status,
        "instruction_end_date": pending.instruction_end_date,
        "instruction_type": pending.instruction_type,
        "instruction_owning_lob": pending.owning_lob,
        "created_by": {
            "user_id": subject.user_id,
            "supervisor_id": subject.supervisor_id,
        },
    }
    try:
        decision_result = await authz.evaluate_payment(
            action="CREATE",
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
            activities.append(f"Re-check denied CREATE: {reasons}")
            return SkillRunResult(
                answer=(
                    f"**Stopped before create** — policy no longer allows CREATE "
                    f"({reasons}). No payment was created."
                ),
                activities=activities,
                intent_id="skill.create_payment.recheck_denied",
            )
    except AuthzOboClientError as exc:
        # Fail closed (issue #50 / P1-3): do not mutate when policy re-check cannot complete.
        logger.warning("create-payment confirm recheck failed: %s — aborting create", exc)
        activities.append(f"Could not re-check policy ({exc}) — stopped before create.")
        return SkillRunResult(
            answer=(
                f"**Stopped before create** — could not re-check CREATE permission "
                f"({exc}). No payment was created."
            ),
            activities=activities,
            intent_id="skill.create_payment.recheck_error",
        )

    payment_client = PaymentClient()
    try:
        payment = await payment_client.create_payment(
            instruction_id=pending.instruction_id,
            amount=pending.amount,
            value_date=pending.value_date,
            user_token=user_token,
            user_session_id=user_session_id,
        )
    except PaymentCreateDenied as exc:
        activities.append(f"CREATE denied by payment-service: {exc.detail}")
        return SkillRunResult(
            answer=f"**Create denied** — {exc.detail}\n\nNo payment was persisted.",
            activities=activities,
            intent_id="skill.create_payment.create_denied",
        )
    except PaymentClientError as exc:
        activities.append(f"CREATE failed: {exc}")
        return SkillRunResult(
            answer=f"**Create failed** — {exc}",
            activities=activities,
            intent_id="skill.create_payment.create_error",
        )

    payment_id = str(payment.get("payment_id") or "")
    activities.append(f"Created draft payment `{payment_id}`.")
    activities.append("Looking up who can submit for approval…")

    submitters_section = await _eligible_submitters_section(
        payment=payment,
        instruction_status=pending.instruction_status,
        instruction_end_date=pending.instruction_end_date,
    )
    if submitters_section:
        activities.append("Eligible submitters loaded.")
    else:
        activities.append("Eligible submitters unavailable — see note in the report.")

    return SkillRunResult(
        answer=format_created_payment_report(
            payment,
            card=pending.card,
            submitters_section=submitters_section,
        ),
        activities=activities,
        intent_id="skill.create_payment.created",
    )


async def _eligible_submitters_section(
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
        data = await authz.eligible_payment_submitters(
            payment={
                "payment_id": payment.get("payment_id"),
                "instruction_id": payment.get("instruction_id"),
                "instruction_version": payment.get("instruction_version") or 1,
                "status": payment.get("status") or "DRAFT",
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
        logger.warning("eligible submitters lookup failed: %s", exc)
        return None

    blocked = data.get("submit_blocked_reason")
    if blocked:
        return f"### Who can submit `{payment.get('payment_id')}`\n\n{blocked}"

    eligible = list(data.get("eligible") or [])
    return format_eligible_approvers_section(
        header=f"### Who can submit `{payment.get('payment_id')}` for approval",
        section_title="Eligible desk submitters",
        eligible=eligible,
        empty_message=(
            "No eligible desk submitters were found for this payment "
            "(need PAYMENT_CREATOR with desk LOB matching the instruction)."
        ),
        candidate_role_label="PAYMENT_CREATOR",
        candidates_evaluated=data.get("candidates_evaluated"),
    )


__all__ = [
    "confirm_create_payment",
    "run_create_payment_phase1",
]
