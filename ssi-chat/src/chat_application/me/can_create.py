from __future__ import annotations

from chat_application.me.models import MeIntentResult
from chat_application.subject import Subject

_AMOUNT_CLUBS = frozenset(
    {
        "UP_TO_100_MILLION_CLUB",
        "UP_TO_1_BILLION_CLUB",
        "UP_TO_100_BILLION_CLUB",
    }
)


def _display(subject: Subject) -> str:
    if subject.family_name and subject.given_name:
        return f"{subject.family_name}, {subject.given_name}"
    return subject.user_id


def _clubs(subject: Subject) -> list[str]:
    return [g for g in subject.groups if g in _AMOUNT_CLUBS]


def answer_can_create_payment(subject: Subject) -> MeIntentResult:
    """Directory-level CREATE capability (not live OPA against an instruction)."""
    has_role = "PAYMENT_CREATOR" in subject.roles
    in_mo = "MIDDLE_OFFICE" in subject.groups
    clubs = _clubs(subject)
    covering = subject.covering_lobs
    name = _display(subject)

    if has_role and in_mo and covering and clubs:
        return MeIntentResult(
            answer=(
                f"**Yes** — `{subject.user_id}` ({name}) may **create** draft payments "
                f"under policy, for covering LOBs **{', '.join(covering)}** within "
                f"amount club(s) **{', '.join(clubs)}**.\n\n"
                "OPA still checks the specific instruction (usable status, not expired) "
                "and that the amount is within your club ceiling at create time."
            ),
            intent_id="me.can_create_payment.yes",
        )

    if has_role and subject.lob and not in_mo:
        return MeIntentResult(
            answer=(
                f"**No** — you cannot **create** a draft payment.\n\n"
                f"You (`{subject.user_id}`) hold `PAYMENT_CREATOR` with desk LOB "
                f"**{subject.lob}**, which is the **front-office submit** profile. "
                "CREATE requires `MIDDLE_OFFICE`, covering LOBs, and an amount-limit club "
                "(e.g. `pay-101`).\n\n"
                f"You **can submit** an existing **{subject.lob}** draft for funding "
                "approval when the backing instruction is APPROVED."
            ),
            intent_id="me.can_create_payment.fo_submitter",
        )

    gaps: list[str] = []
    if not has_role:
        gaps.append("role `PAYMENT_CREATOR`")
    if not in_mo:
        gaps.append("group `MIDDLE_OFFICE`")
    if not covering:
        gaps.append("covering LOBs")
    if not clubs:
        gaps.append("an amount-limit club")

    return MeIntentResult(
        answer=(
            f"**No** — `{subject.user_id}` ({name}) is missing what CREATE requires: "
            f"{', '.join(gaps)}.\n\n"
            "Payment CREATE needs `PAYMENT_CREATOR` + `MIDDLE_OFFICE` + covering LOBs "
            "+ amount club, then OPA checks the instruction and amount."
        ),
        intent_id="me.can_create_payment.no",
    )


def answer_can_submit_payment(subject: Subject) -> MeIntentResult:
    has_role = "PAYMENT_CREATOR" in subject.roles
    name = _display(subject)

    if has_role and subject.lob:
        return MeIntentResult(
            answer=(
                f"**Yes** — you may **submit** draft payments whose instruction owning LOB "
                f"is **{subject.lob}** (your desk LOB).\n\n"
                "OPA also requires the payment to be DRAFT and the backing instruction "
                "APPROVED and not expired."
            ),
            intent_id="me.can_submit_payment.yes",
        )

    if has_role and "MIDDLE_OFFICE" in subject.groups:
        return MeIntentResult(
            answer=(
                f"**Partially** — `{subject.user_id}` ({name}) is a middle-office "
                "`PAYMENT_CREATOR` (create/update/cancel drafts). "
                "SUBMIT normally uses front-office desk `lob` matching the instruction. "
                "Your subject has no desk `lob`, so submit may be denied unless that "
                "attribute is set."
            ),
            intent_id="me.can_submit_payment.mo_no_desk",
        )

    return MeIntentResult(
        answer=(
            f"**No** — SUBMIT needs `PAYMENT_CREATOR` and desk `lob` matching the "
            f"instruction owning LOB. Your subject (`{subject.user_id}`) does not "
            "meet that profile."
        ),
        intent_id="me.can_submit_payment.no",
    )
