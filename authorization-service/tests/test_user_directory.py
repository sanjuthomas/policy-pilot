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

    directory = UserDirectory(users_yaml)
    candidates = directory.funding_approver_candidates("FICC")

    assert [subject.user_id for subject in candidates] == ["pay-201"]
