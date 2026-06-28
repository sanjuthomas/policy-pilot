from __future__ import annotations

from authz.models import UserDirectoryRow
from authz.user_directory import _AMOUNT_CLUBS, UserDirectory


def _split_groups(groups: list[str]) -> tuple[list[str], list[str]]:
    org_groups: list[str] = []
    amount_clubs: list[str] = []
    for group in groups:
        if group in _AMOUNT_CLUBS:
            amount_clubs.append(group)
        else:
            org_groups.append(group)
    return org_groups, amount_clubs


def build_user_directory_rows(directory: UserDirectory) -> list[UserDirectoryRow]:
    email_domain = directory.email_domain
    rows: list[UserDirectoryRow] = []

    for user in directory.all_users():
        org_groups, amount_clubs = _split_groups(user.groups)
        rows.append(
            UserDirectoryRow(
                user_id=user.user_id,
                login_name=f"{user.user_id}@{email_domain}",
                given_name=user.given_name,
                family_name=user.family_name,
                display_name=f"{user.family_name}, {user.given_name}",
                title=user.title,
                lob=user.lob,
                roles=list(user.roles),
                groups=org_groups,
                amount_clubs=amount_clubs,
                covering_lobs=list(user.covering_lobs),
                supervisor_id=user.supervisor_id,
                supervisor_display_name=directory.display_name_for(user.supervisor_id),
            )
        )

    return rows
