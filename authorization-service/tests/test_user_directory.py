from pathlib import Path

from authz.user_directory import UserDirectory


def test_funding_approver_candidates_filters_lob(tmp_path: Path) -> None:
    users_yaml = tmp_path / "users.yaml"
    users_yaml.write_text(
        """
users:
  - user_id: pay-201
    given_name: A
    family_name: One
    title: VP
    roles: [FUNDING_APPROVER]
    groups: [MIDDLE_OFFICE]
    covering_lobs: [FICC]
  - user_id: pay-202
    given_name: B
    family_name: Two
    title: VP
    roles: [FUNDING_APPROVER]
    groups: [MIDDLE_OFFICE]
    covering_lobs: [FX]
  - user_id: pay-203
    given_name: C
    family_name: Three
    title: VP
    roles: [PAYMENT_CREATOR]
    groups: [MIDDLE_OFFICE]
    covering_lobs: [FICC]
""",
        encoding="utf-8",
    )

    directory = UserDirectory.from_yaml(users_yaml)
    candidates = directory.funding_approver_candidates("FICC")

    assert [subject.user_id for subject in candidates] == ["pay-201"]


def test_payment_submitter_candidates_filters_desk_lob(tmp_path: Path) -> None:
    users_yaml = tmp_path / "users.yaml"
    users_yaml.write_text(
        """
users:
  - user_id: fo-ficc-101
    given_name: A
    family_name: Desk
    title: Analyst
    lob: FICC
    roles: [PAYMENT_CREATOR]
    groups: [FRONT_OFFICE]
  - user_id: fo-fx-101
    given_name: B
    family_name: DeskFx
    title: Analyst
    lob: FX
    roles: [PAYMENT_CREATOR]
    groups: [FRONT_OFFICE]
  - user_id: pay-101
    given_name: C
    family_name: Middle
    title: Analyst
    roles: [PAYMENT_CREATOR]
    groups: [MIDDLE_OFFICE]
    covering_lobs: [FICC]
""",
        encoding="utf-8",
    )

    directory = UserDirectory.from_yaml(users_yaml)
    candidates = directory.payment_submitter_candidates("FICC")

    assert [subject.user_id for subject in candidates] == ["fo-ficc-101"]


def test_members_of_group_filters_role_and_covering_lob(tmp_path: Path) -> None:
    users_yaml = tmp_path / "users.yaml"
    users_yaml.write_text(
        """
users:
  - user_id: pay-204
    given_name: Wei
    family_name: Chen
    title: Managing Director
    roles: [FUNDING_APPROVER]
    groups: [MIDDLE_OFFICE, UP_TO_100_BILLION_CLUB]
    covering_lobs: [FICC, FX, DESK_RATES]
  - user_id: pay-201
    given_name: Sophie
    family_name: Laurent
    title: Vice President
    lob: FICC
    roles: [FUNDING_APPROVER]
    groups: [MIDDLE_OFFICE, UP_TO_1_BILLION_CLUB]
    covering_lobs: [FICC, FX]
  - user_id: pay-203
    given_name: Anna
    family_name: Kowalski
    title: Associate
    roles: [PAYMENT_CREATOR, FUNDING_APPROVER]
    groups: [MIDDLE_OFFICE, UP_TO_100_MILLION_CLUB]
    covering_lobs: [FX]
""",
        encoding="utf-8",
    )

    directory = UserDirectory.from_yaml(users_yaml)
    members = directory.members_of_group("UP_TO_100_BILLION_CLUB")

    assert [user.user_id for user in members] == ["pay-204"]

    filtered = directory.members_of_group(
        "UP_TO_1_BILLION_CLUB",
        role="FUNDING_APPROVER",
        covering_lob="FICC",
    )
    assert [user.user_id for user in filtered] == ["pay-201"]
    assert filtered[0].lob == "FICC"
    assert filtered[0].covering_lobs == ["FICC", "FX"]
