from pathlib import Path


def test_ui_index(test_client) -> None:
    response = test_client.get("/ui/")
    assert response.status_code == 200
    assert "User Directory" in response.text


def test_ui_list_users(tmp_path: Path, test_client, monkeypatch) -> None:
    users_file = tmp_path / "users.yaml"
    users_file.write_text(
        """
defaults:
  email_domain: ssi.local
users:
  - user_id: comp-001
    given_name: Alex
    family_name: Morgan
    title: Compliance Analyst
    roles: [COMPLIANCE_ANALYST]
    groups: [COMPLIANCE]
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("authz.config.settings.users_file", users_file)

    from authz import main as main_module
    from authz.user_directory import UserDirectory

    main_module.user_directory = UserDirectory(users_file)

    response = test_client.get("/api/ui/users")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["users"][0]["user_id"] == "comp-001"
    assert body["users"][0]["login_name"] == "comp-001@ssi.local"


def test_ui_list_users_role_filter(tmp_path: Path, test_client, monkeypatch) -> None:
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
    title: Vice President
    roles: [FUNDING_APPROVER]
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("authz.config.settings.users_file", users_file)

    from authz import main as main_module
    from authz.user_directory import UserDirectory

    main_module.user_directory = UserDirectory(users_file)

    response = test_client.get("/api/ui/users", params={"role": "COMPLIANCE_ANALYST"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["users"][0]["user_id"] == "comp-001"
