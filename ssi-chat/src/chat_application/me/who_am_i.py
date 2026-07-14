from __future__ import annotations

from chat_application.auth.capabilities import capabilities_for
from chat_application.auth.subject import Subject
from chat_application.me.models import MeIntentResult

_AMOUNT_CLUBS = frozenset(
    {
        "UP_TO_100_MILLION_CLUB",
        "UP_TO_1_BILLION_CLUB",
        "UP_TO_100_BILLION_CLUB",
    }
)


def answer_who_am_i(subject: Subject) -> MeIntentResult:
    caps = capabilities_for(subject)
    display = (
        f"{subject.family_name}, {subject.given_name}"
        if subject.family_name and subject.given_name
        else subject.user_id
    )
    org_groups = [g for g in subject.groups if g not in _AMOUNT_CLUBS]
    clubs = [g for g in subject.groups if g in _AMOUNT_CLUBS]

    audience_bits: list[str] = []
    if caps.is_compliance:
        audience_bits.append("compliance inquiry")
    if caps.can_create_payment:
        audience_bits.append("payment creator")
    if caps.can_approve_payment:
        audience_bits.append("funding approver")
    audience = ", ".join(audience_bits) if audience_bits else "chat user"

    lines = [
        f"You are signed in as **{display}** (`{subject.user_id}`).",
        "",
        f"- **Title:** {subject.title or '—'}",
        f"- **Roles:** {', '.join(subject.roles) or '—'}",
        f"- **Groups:** {', '.join(org_groups) or '—'}",
        f"- **Amount clubs:** {', '.join(clubs) or '—'}",
        f"- **Desk LOB:** {subject.lob or '—'}",
        f"- **Covering LOBs:** {', '.join(subject.covering_lobs) or '—'}",
        f"- **Supervisor:** {subject.supervisor_id or '—'}",
        f"- **Chat audience:** {audience}",
    ]
    return MeIntentResult(answer="\n".join(lines), intent_id="me.who_am_i")
