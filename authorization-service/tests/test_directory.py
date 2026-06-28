from pathlib import Path

import yaml

from authz.directory import build_user_directory_rows
from authz.user_directory import UserDirectory


def test_build_user_directory_rows_splits_clubs(tmp_path: Path) -> None:
    users_file = tmp_path / "users.yaml"
    users_file.write_text(
        """
defaults:
  email_domain: ssi.local
users:
  - user_id: pay-201
    given_name: Sophie
    family_name: Laurent
    title: Vice President
    roles: [FUNDING_APPROVER]
    groups: [MIDDLE_OFFICE, UP_TO_1_BILLION_CLUB]
    covering_lobs: [FICC, FX]
    supervisor_id: pay-300
  - user_id: pay-300
    given_name: Thomas
    family_name: Bergmann
    title: Managing Director
    roles: [FUNDING_APPROVER]
    groups: [MIDDLE_OFFICE]
    covering_lobs: [FICC]
""",
        encoding="utf-8",
    )

    directory = UserDirectory(users_file)
    rows = build_user_directory_rows(directory)

    assert len(rows) == 2
    pay_201 = next(row for row in rows if row.user_id == "pay-201")
    assert pay_201.login_name == "pay-201@ssi.local"
    assert pay_201.display_name == "Laurent, Sophie"
    assert pay_201.groups == ["MIDDLE_OFFICE"]
    assert pay_201.amount_clubs == ["UP_TO_1_BILLION_CLUB"]
    assert pay_201.supervisor_display_name == "Bergmann, Thomas"


def test_all_users_sorted(tmp_path: Path) -> None:
    users_file = tmp_path / "users.yaml"
    users_file.write_text(
        """
users:
  - user_id: z-user
    given_name: Zed
    family_name: Last
    title: Analyst
    roles: [INSTRUCTION_CREATOR]
  - user_id: a-user
    given_name: Amy
    family_name: First
    title: Analyst
    roles: [INSTRUCTION_CREATOR]
""",
        encoding="utf-8",
    )

    directory = UserDirectory(users_file)
    assert [user.user_id for user in directory.all_users()] == ["a-user", "z-user"]
