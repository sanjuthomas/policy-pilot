from __future__ import annotations

from chat_application.auth.capabilities import capabilities_for
from chat_application.auth.subject import Subject
from chat_application.formatting.common import format_identity_token_list
from chat_application.me.models import MeIntentResult

_AMOUNT_CLUBS = frozenset(
    {
        "UP_TO_100_MILLION_CLUB",
        "UP_TO_1_BILLION_CLUB",
        "UP_TO_100_BILLION_CLUB",
    }
)


def _capability_lines(subject: Subject) -> list[str]:
    roles = set(subject.roles)
    groups = set(subject.groups)
    org_groups = [g for g in subject.groups if g not in _AMOUNT_CLUBS]
    clubs = [g for g in subject.groups if g in _AMOUNT_CLUBS]
    club_text = (
        format_identity_token_list(clubs, empty="no amount-limit club")
        if clubs
        else "no amount-limit club"
    )
    covering = (
        ", ".join(subject.covering_lobs) if subject.covering_lobs else "no covering LOBs"
    )
    desk = subject.lob or "no desk LOB"
    lines: list[str] = []

    if "FUNDING_APPROVER" in roles and "MIDDLE_OFFICE" in groups:
        lines.append(
            f"- **Approve/reject payments** for covering LOBs ({covering}) within "
            f"{club_text}, subject to four-eyes and reporting-line checks"
        )
    if "PAYMENT_CREATOR" in roles and "MIDDLE_OFFICE" in groups:
        lines.append(
            f"- **Create/update/cancel draft payments** for covering LOBs ({covering}) "
            f"within {club_text}"
        )
    if "PAYMENT_CREATOR" in roles and subject.lob:
        lines.append(f"- **Submit payments** for desk LOB {desk}")
    elif "PAYMENT_CREATOR" in roles and "MIDDLE_OFFICE" not in groups and not subject.lob:
        lines.append(
            "- **Payment creator role** is present, but middle-office group / desk LOB "
            "gates may still block create or submit under OPA"
        )
    if "INSTRUCTION_CREATOR" in roles and "MIDDLE_OFFICE" in groups:
        lines.append(
            f"- **Create/update/submit/cancel instructions** as middle-office creator "
            f"(title {subject.title})"
        )
    if "INSTRUCTION_APPROVER" in roles and subject.lob:
        lines.append(
            f"- **Approve/reject instructions** for desk LOB {desk} "
            f"(title {subject.title})"
        )
    if "COMPLIANCE_ANALYST" in roles or "COMPLIANCE_OFFICER" in roles:
        lines.append(
            "- **Compliance inquiry** — policy summaries, directory, and eligible approvers"
        )
    if "PLATFORM_ADMIN" in roles:
        lines.append("- **Platform admin** — administer the platform user directory")

    caps = capabilities_for(subject)
    if caps.is_compliance or caps.is_operational:
        lines.append(
            "- **Policy Pilot chat** — ask graph/audit questions"
            + (" and me-centric permission questions" if caps.is_operational else "")
        )

    if not lines:
        lines.append(
            "- No payment/instruction capabilities were derived from your roles and groups."
        )

    # Identity context for the summary header section
    _ = org_groups
    return lines


def answer_my_permissions(subject: Subject) -> MeIntentResult:
    display = (
        f"{subject.family_name}, {subject.given_name}"
        if subject.family_name and subject.given_name
        else subject.user_id
    )
    org_groups = [g for g in subject.groups if g not in _AMOUNT_CLUBS]
    clubs = [g for g in subject.groups if g in _AMOUNT_CLUBS]

    lines = [
        f"Permissions for **{display}** (`{subject.user_id}`), derived from your "
        "signed-in identity (roles, groups, covering LOBs, amount clubs):",
        "",
        f"- **Roles:** {format_identity_token_list(subject.roles)}",
        f"- **Groups:** {format_identity_token_list(org_groups)}",
        f"- **Amount clubs:** {format_identity_token_list(clubs)}",
        f"- **Covering LOBs:** {', '.join(subject.covering_lobs) or '—'}",
        f"- **Desk LOB:** {subject.lob or '—'}",
        "",
        "**Derived capabilities:**",
        *_capability_lines(subject),
        "",
        "Live allow/deny on a specific payment still goes through OPA "
        "(four-eyes, reporting line, amount ceiling, instruction status).",
    ]
    return MeIntentResult(answer="\n".join(lines), intent_id="me.my_permissions")
