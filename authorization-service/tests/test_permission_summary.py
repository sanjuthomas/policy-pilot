from __future__ import annotations

from authz.models import UserDirectoryRow
from authz.permission_summary import (
    build_person_permission_summary,
    filter_directory_rows,
)


def _row(**overrides) -> UserDirectoryRow:
    base = dict(
        user_id="pay-203",
        login_name="pay-203@ssi.local",
        given_name="Anna",
        family_name="Kowalski",
        display_name="Kowalski, Anna",
        title="Associate",
        lob=None,
        roles=["PAYMENT_CREATOR", "FUNDING_APPROVER"],
        groups=["MIDDLE_OFFICE"],
        amount_clubs=["UP_TO_100_MILLION_CLUB"],
        covering_lobs=["FX"],
    )
    base.update(overrides)
    return UserDirectoryRow(**base)


def test_filter_matches_display_name() -> None:
    rows = [_row(), _row(user_id="pay-201", given_name="Sophie", family_name="Laurent", display_name="Laurent, Sophie")]
    matches = filter_directory_rows(rows, "Kowalski, Anna")
    assert [row.user_id for row in matches] == ["pay-203"]


def test_filter_matches_reversed_name() -> None:
    rows = [_row()]
    matches = filter_directory_rows(rows, "Anna Kowalski")
    assert [row.user_id for row in matches] == ["pay-203"]


def test_build_person_permission_summary_for_dual_role() -> None:
    summary = build_person_permission_summary(_row())
    kinds = {item.kind for item in summary.capabilities}
    assert "funding_approve" in kinds
    assert "payment_create" in kinds
    assert "FX" in summary.narrative
    assert "UP_TO_100_MILLION_CLUB" in summary.narrative
