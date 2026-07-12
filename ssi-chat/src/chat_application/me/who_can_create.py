from __future__ import annotations

from pathlib import Path

from chat_application.config import settings
from chat_application.me.models import MeIntentResult
from chat_application.subject import Subject
from chat_application.users import SeedUser, load_users

_AMOUNT_CLUBS = frozenset(
    {
        "UP_TO_100_MILLION_CLUB",
        "UP_TO_1_BILLION_CLUB",
        "UP_TO_100_BILLION_CLUB",
    }
)


def payment_creators_for_lob(
    covering_lob: str | None,
    *,
    users_file: Path | None = None,
) -> list[SeedUser]:
    """Middle-office PAYMENT_CREATORs who may draft payments (optionally for a LOB)."""
    seed = load_users(users_file or settings.users_file)
    lob = covering_lob.strip().upper() if covering_lob else None
    matches: list[SeedUser] = []
    for user in seed.users:
        if user.user_id.startswith("svc-"):
            continue
        if "PAYMENT_CREATOR" not in user.roles:
            continue
        if "MIDDLE_OFFICE" not in user.groups:
            continue
        if lob and lob not in {item.upper() for item in user.covering_lobs}:
            continue
        matches.append(user)
    matches.sort(key=lambda row: (row.family_name, row.given_name, row.user_id))
    return matches


def instruction_creators(
    *,
    users_file: Path | None = None,
) -> list[SeedUser]:
    """Middle-office INSTRUCTION_CREATORs who may draft instructions."""
    seed = load_users(users_file or settings.users_file)
    matches: list[SeedUser] = []
    for user in seed.users:
        if user.user_id.startswith("svc-"):
            continue
        if "INSTRUCTION_CREATOR" not in user.roles:
            continue
        if "MIDDLE_OFFICE" not in user.groups:
            continue
        matches.append(user)
    matches.sort(key=lambda row: (row.family_name, row.given_name, row.user_id))
    return matches


def answer_who_can_create_payment(
    *,
    covering_lob: str | None,
    subject: Subject | None = None,
    users_file: Path | None = None,
) -> MeIntentResult:
    creators = payment_creators_for_lob(covering_lob, users_file=users_file)
    lob_label = covering_lob.upper() if covering_lob else None

    if lob_label:
        header = (
            f"Users who can **create** (draft) payments for LOB **{lob_label}** — "
            "role `PAYMENT_CREATOR`, group `MIDDLE_OFFICE`, covering LOBs include "
            f"{lob_label}:"
        )
    else:
        header = (
            "Users who can **create** (draft) payments — role `PAYMENT_CREATOR` "
            "and group `MIDDLE_OFFICE` (with covering LOBs / amount clubs):"
        )

    if not creators:
        detail = (
            f"No middle-office payment creators cover LOB {lob_label}."
            if lob_label
            else "No middle-office payment creators were found in the directory."
        )
        return MeIntentResult(
            answer=f"{header}\n\n{detail}",
            intent_id="me.who_can_create.payment.empty",
        )

    lines = [header, ""]
    for user in creators:
        clubs = [g for g in user.groups if g in _AMOUNT_CLUBS]
        org = [g for g in user.groups if g not in _AMOUNT_CLUBS]
        covering = ", ".join(user.covering_lobs) or "—"
        club_text = ", ".join(clubs) or "—"
        marker = " ← you" if subject and user.user_id == subject.user_id else ""
        lines.append(
            f"- **{user.family_name}, {user.given_name}** (`{user.user_id}`) — "
            f"{user.title}; covering [{covering}]; clubs [{club_text}]; "
            f"groups [{', '.join(org) or '—'}]{marker}"
        )

    lines.extend(
        [
            "",
            "Front-office users with only desk lob (for example fo-fx-101) **submit** "
            "payment drafts; they do not create them. Payment CREATE still requires a "
            "usable instruction and an amount within the creator's club at mutation time.",
        ]
    )
    return MeIntentResult(answer="\n".join(lines), intent_id="me.who_can_create.payment")


def answer_who_can_create_instruction(
    *,
    covering_lob: str | None = None,
    subject: Subject | None = None,
    users_file: Path | None = None,
) -> MeIntentResult:
    creators = instruction_creators(users_file=users_file)
    lob_label = covering_lob.upper() if covering_lob else None

    header = (
        "Users who can **create** (draft) instructions — role `INSTRUCTION_CREATOR`, "
        "group `MIDDLE_OFFICE`, with an eligible creator title:"
    )
    if lob_label:
        header += (
            f"\n\nFor owning LOB **{lob_label}**, any of these creators may draft when the "
            "account owning LOB matches and other OPA checks pass (profit center, duration). "
            "Instruction creators are not scoped by payment `covering_lobs`."
        )

    if not creators:
        return MeIntentResult(
            answer=f"{header}\n\nNo middle-office instruction creators were found.",
            intent_id="me.who_can_create.instruction.empty",
        )

    lines = [header, ""]
    for user in creators:
        marker = " ← you" if subject and user.user_id == subject.user_id else ""
        lines.append(
            f"- **{user.family_name}, {user.given_name}** (`{user.user_id}`) — "
            f"{user.title}; supervisor `{user.supervisor_id or '—'}`{marker}"
        )

    lines.extend(
        [
            "",
            "Do not confuse with **payment** creators (`PAYMENT_CREATOR` + covering LOBs). "
            "Instruction create uses `INSTRUCTION_CREATOR` (e.g. mo-100, mo-101).",
        ]
    )
    return MeIntentResult(
        answer="\n".join(lines),
        intent_id="me.who_can_create.instruction",
    )


def answer_who_can_create(
    *,
    entity_type: str | None,
    covering_lob: str | None,
    subject: Subject | None = None,
    users_file: Path | None = None,
) -> MeIntentResult:
    if entity_type == "instruction":
        return answer_who_can_create_instruction(
            covering_lob=covering_lob,
            subject=subject,
            users_file=users_file,
        )
    return answer_who_can_create_payment(
        covering_lob=covering_lob,
        subject=subject,
        users_file=users_file,
    )
