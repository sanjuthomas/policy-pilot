from __future__ import annotations

from pathlib import Path

from chat_application.capabilities import OPERATIONAL_ROLES, capabilities_for
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


def _split_groups(groups: list[str]) -> tuple[list[str], list[str]]:
    org_groups: list[str] = []
    clubs: list[str] = []
    for group in groups:
        if group in _AMOUNT_CLUBS:
            clubs.append(group)
        else:
            org_groups.append(group)
    return org_groups, clubs


def _similarity_score(subject: Subject, other: SeedUser) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0

    shared_roles = sorted(set(subject.roles) & set(other.roles) & OPERATIONAL_ROLES)
    if shared_roles:
        score += 10 * len(shared_roles)
        reasons.append(f"roles {', '.join(shared_roles)}")

    subject_groups, subject_clubs = _split_groups(subject.groups)
    other_groups, other_clubs = _split_groups(other.groups)

    shared_groups = sorted(set(subject_groups) & set(other_groups))
    if shared_groups:
        score += 5 * len(shared_groups)
        reasons.append(f"groups {', '.join(shared_groups)}")

    shared_clubs = sorted(set(subject_clubs) & set(other_clubs))
    if shared_clubs:
        score += 4 * len(shared_clubs)
        reasons.append(f"amount clubs {', '.join(shared_clubs)}")

    shared_lobs = sorted(set(subject.covering_lobs) & set(other.covering_lobs))
    if shared_lobs:
        score += 3 * len(shared_lobs)
        reasons.append(f"covering LOBs {', '.join(shared_lobs)}")

    if subject.lob and other.lob and subject.lob == other.lob:
        score += 2
        reasons.append(f"desk LOB {subject.lob}")

    if subject.title and other.title and subject.title == other.title:
        score += 1
        reasons.append(f"title {subject.title}")

    return score, reasons


def find_users_like_me(
    subject: Subject,
    *,
    users_file: Path | None = None,
    limit: int = 12,
) -> list[tuple[SeedUser, int, list[str]]]:
    path = users_file or settings.users_file
    seed = load_users(path)
    scored: list[tuple[SeedUser, int, list[str]]] = []
    for user in seed.users:
        if user.user_id == subject.user_id:
            continue
        if user.user_id.startswith("svc-"):
            continue
        score, reasons = _similarity_score(subject, user)
        if score <= 0:
            continue
        scored.append((user, score, reasons))
    scored.sort(key=lambda item: (-item[1], item[0].family_name, item[0].given_name))
    return scored[:limit]


def answer_users_like_me(
    subject: Subject,
    *,
    users_file: Path | None = None,
) -> MeIntentResult:
    caps = capabilities_for(subject)
    matches = find_users_like_me(subject, users_file=users_file)
    display = (
        f"{subject.family_name}, {subject.given_name}"
        if subject.family_name and subject.given_name
        else subject.user_id
    )
    role_bits = ", ".join(subject.roles) or "none"
    group_bits = ", ".join(subject.groups) or "none"
    lob_bits = ", ".join(subject.covering_lobs) or "none"

    header = (
        f"Users similar to **{display}** (`{subject.user_id}`) — "
        f"roles [{role_bits}], groups [{group_bits}], covering LOBs [{lob_bits}]."
    )
    if not caps.is_operational and not caps.is_compliance:
        header += " No operational payment roles were found on your subject."

    if not matches:
        return MeIntentResult(
            answer=header + "\n\nNo other directory users share your operational roles, "
            "groups, amount clubs, or covering LOBs.",
            intent_id="me.users_like_me",
        )

    lines = [header, "", "Closest matches:"]
    for user, _score, reasons in matches:
        name = f"{user.family_name}, {user.given_name}"
        why = "; ".join(reasons) if reasons else "shared attributes"
        lines.append(
            f"- **{name}** (`{user.user_id}`) — {user.title}. Overlap: {why}."
        )

    return MeIntentResult(answer="\n".join(lines), intent_id="me.users_like_me")
