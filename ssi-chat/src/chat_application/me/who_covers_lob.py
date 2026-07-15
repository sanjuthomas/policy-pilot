from __future__ import annotations

from chat_application.auth.users import SeedFile, SeedUser, load_users
from chat_application.me.models import MeIntentResult


def users_covering_lob(
    covering_lob: str,
    *,
    seed: SeedFile | None = None,
) -> list[SeedUser]:
    """All non-service users whose covering_lobs include ``covering_lob``."""
    roster = seed or load_users()
    lob = covering_lob.strip().upper()
    matches: list[SeedUser] = []
    for user in roster.users:
        if user.user_id.startswith("svc-"):
            continue
        if lob not in {item.upper() for item in user.covering_lobs}:
            continue
        matches.append(user)
    matches.sort(key=lambda row: (row.family_name, row.given_name, row.user_id))
    return matches


def answer_who_covers_lob(
    *,
    covering_lob: str | None,
    seed: SeedFile | None = None,
) -> MeIntentResult:
    if not covering_lob or not covering_lob.strip():
        return MeIntentResult(
            answer=(
                "Include a desk LOB when asking who covers it, for example: "
                "“Who covers LOB FICC?” or “Which users cover FX?”"
            ),
            intent_id="me.who_covers_lob.need_lob",
        )

    lob = covering_lob.strip().upper()
    matches = users_covering_lob(lob, seed=seed)
    if not matches:
        return MeIntentResult(
            answer=f"No users in the directory list **{lob}** in their covering LOBs.",
            intent_id="me.who_covers_lob.empty",
        )

    lines = [
        f"Users who **cover LOB {lob}** "
        f"(directory `covering_lobs` includes {lob}) — {len(matches)} user(s):",
        "",
    ]
    for user in matches:
        display = f"{user.family_name}, {user.given_name}"
        roles = ", ".join(user.roles) or "—"
        covering = ", ".join(user.covering_lobs) or "—"
        lines.append(f"- **{display}** (`{user.user_id}`) — {user.title}")
        lines.append(f"  - Roles: {roles}")
        lines.append(f"  - Covering LOBs: {covering}")
    return MeIntentResult(answer="\n".join(lines), intent_id="me.who_covers_lob")
