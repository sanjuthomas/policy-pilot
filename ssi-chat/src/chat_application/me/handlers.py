from __future__ import annotations

from chat_application.capabilities import capabilities_for
from chat_application.me.can_create import (
    answer_can_approve_payment,
    answer_can_create_instruction,
    answer_can_create_payment,
    answer_can_submit_payment,
)
from chat_application.me.detect import detect_me_intent
from chat_application.me.models import MeIntent, MeIntentResult
from chat_application.me.my_permissions import answer_my_permissions
from chat_application.me.users_like_me import answer_users_like_me
from chat_application.me.who_am_i import answer_who_am_i
from chat_application.me.who_can_create import answer_who_can_create
from chat_application.me.who_covers_lob import answer_who_covers_lob
from chat_application.subject import Subject


async def try_me_intent(
    message: str,
    *,
    subject: Subject,
    intent: MeIntent | None = None,
) -> MeIntentResult | None:
    """Run a me-centric handler when intent is provided or heuristic fallback matches."""
    resolved = intent if intent is not None else detect_me_intent(message)
    if resolved is None:
        return None
    return await dispatch_me_intent(resolved, subject=subject)


async def dispatch_me_intent(
    intent: MeIntent,
    *,
    subject: Subject,
) -> MeIntentResult | None:
    caps = capabilities_for(subject)

    if intent.kind == "who_am_i":
        return answer_who_am_i(subject)

    if intent.kind == "my_permissions":
        return answer_my_permissions(subject)

    if intent.kind == "who_can_create":
        return answer_who_can_create(
            entity_type=intent.entity_type,
            covering_lob=intent.covering_lob,
            subject=subject,
        )

    if intent.kind == "who_covers_lob":
        return answer_who_covers_lob(covering_lob=intent.covering_lob)

    if intent.kind == "users_like_me":
        return answer_users_like_me(subject)

    if intent.kind == "waiting_for_me":
        if not caps.can_approve_payment:
            return MeIntentResult(
                answer=(
                    f"You (`{subject.user_id}`) do not hold the `FUNDING_APPROVER` role, "
                    "so no payments are waiting for your approval. "
                    "Payment creators submit drafts for funding review; "
                    "funding approvers authorize them."
                ),
                intent_id="me.waiting_for_me.not_approver",
            )
        return MeIntentResult(
            answer=(
                "I can answer “payments waiting for my approval” once the approver "
                "worklist intent is wired. You do hold `FUNDING_APPROVER` — "
                "ask again after that handler ships, or ask who can approve a specific payment id."
            ),
            intent_id="me.waiting_for_me.pending",
        )

    if intent.kind == "can_act_on_entity":
        if intent.action == "CREATE":
            if intent.entity_type == "instruction":
                return answer_can_create_instruction(subject)
            return answer_can_create_payment(subject)
        if intent.action == "SUBMIT":
            return answer_can_submit_payment(subject)
        if intent.action == "APPROVE" and not intent.entity_id:
            return answer_can_approve_payment(subject)
        if not intent.entity_id:
            return MeIntentResult(
                answer=(
                    "Include a payment id when asking about a specific payment action, "
                    "for example: “Do I have permission to approve payment 20260705-FX-P-534?”"
                ),
                intent_id="me.can_act_on_entity.need_id",
            )
        if not caps.can_approve_payment and intent.action == "APPROVE":
            return MeIntentResult(
                answer=(
                    f"You (`{subject.user_id}`) do not hold `FUNDING_APPROVER`, "
                    f"so you cannot approve payment `{intent.entity_id}` under current policy."
                ),
                intent_id="me.can_act_on_entity.not_approver",
            )
        return MeIntentResult(
            answer=(
                f"Live OPA evaluate for “can I approve payment `{intent.entity_id}`?” "
                "is wired next (service + on-behalf-of). "
                "You hold `FUNDING_APPROVER`; the next step checks amount club, "
                "covering LOBs, four-eyes, and reporting line against that payment."
            ),
            intent_id="me.can_act_on_entity.pending",
        )

    if intent.kind == "who_else_can_act":
        if not intent.entity_id:
            return MeIntentResult(
                answer=(
                    "Include a payment id, for example: "
                    "“Who else can approve payment 20260705-FX-P-534?”"
                ),
                intent_id="me.who_else_can_act.need_id",
            )
        return MeIntentResult(
            answer=(
                f"“Who else can approve payment `{intent.entity_id}`?” will reuse the "
                "eligible-approvers path and exclude you. That handler ships in the "
                "approver read-only phase."
            ),
            intent_id="me.who_else_can_act.pending",
        )

    return None
