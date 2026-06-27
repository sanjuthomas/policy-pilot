from pathlib import Path

from chat_application.users import compliance_users, load_users


def test_compliance_users_filters_role(tmp_path: Path) -> None:
    users_file = tmp_path / "users.yaml"
    users_file.write_text(
        """
users:
  - user_id: comp-001
    given_name: Alex
    family_name: Morgan
    title: Compliance Analyst
    roles: [COMPLIANCE_ANALYST]
  - user_id: pay-201
    given_name: Sophie
    family_name: Laurent
    title: VP
    roles: [FUNDING_APPROVER]
""",
        encoding="utf-8",
    )

    users = compliance_users(users_file)
    assert [user.user_id for user in users] == ["comp-001"]


def test_load_users_reads_defaults(tmp_path: Path) -> None:
    users_file = tmp_path / "users.yaml"
    users_file.write_text(
        """
defaults:
  password: Password1!
users: []
""",
        encoding="utf-8",
    )

    seed = load_users(users_file)
    assert seed.defaults["password"] == "Password1!"
