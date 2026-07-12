from pathlib import Path

from chat_application.users import chat_users, compliance_users, load_users


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


def test_compliance_users_includes_platform_admin_when_allowed(tmp_path: Path) -> None:
    users_file = tmp_path / "users.yaml"
    users_file.write_text(
        """
users:
  - user_id: admin-001
    given_name: Platform
    family_name: Administrator
    title: Platform Administrator
    roles: [PLATFORM_ADMIN]
  - user_id: comp-001
    given_name: Alex
    family_name: Morgan
    title: Compliance Analyst
    roles: [COMPLIANCE_ANALYST]
""",
        encoding="utf-8",
    )

    users = compliance_users(
        users_file,
        allowed_roles={"COMPLIANCE_ANALYST", "PLATFORM_ADMIN"},
    )
    assert {user.user_id for user in users} == {"admin-001", "comp-001"}


def test_chat_users_includes_operational_and_compliance(tmp_path: Path) -> None:
    users_file = tmp_path / "users.yaml"
    users_file.write_text(
        """
users:
  - user_id: comp-001
    given_name: Alex
    family_name: Morgan
    title: Compliance Analyst
    roles: [COMPLIANCE_ANALYST]
  - user_id: pay-101
    given_name: Mina
    family_name: Okonkwo
    title: Payment Ops
    roles: [PAYMENT_CREATOR]
    groups: [MIDDLE_OFFICE]
    covering_lobs: [FICC]
  - user_id: pay-201
    given_name: Sophie
    family_name: Laurent
    title: VP
    roles: [FUNDING_APPROVER]
  - user_id: svc-chat
    given_name: Chat
    family_name: Service
    title: Service Account
    roles: [PAYMENT_CREATOR]
""",
        encoding="utf-8",
    )

    rows = chat_users(
        users_file,
        allowed_roles={"COMPLIANCE_ANALYST", "PAYMENT_CREATOR", "FUNDING_APPROVER"},
    )
    by_id = {row["user_id"]: row for row in rows}
    assert set(by_id) == {"comp-001", "pay-101", "pay-201"}
    assert by_id["pay-101"]["audiences"] == ["payment_creator"]
    assert by_id["pay-201"]["audiences"] == ["funding_approver"]
    assert by_id["comp-001"]["audiences"] == ["compliance"]


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
