from __future__ import annotations

from pathlib import Path

import pytest
from authz.authorization_routes import _user_directory
from authz.dependencies import get_compliance_subject
from authz.main import app
from authz.models import Subject
from authz.user_directory import UserDirectory
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("authz.config.settings.oidc_issuer_url", "http://localhost:8080")
    return TestClient(app)


def _seed_users(tmp_path: Path) -> Path:
    users_file = tmp_path / "users.yaml"
    users_file.write_text(
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
    roles: [FUNDING_APPROVER]
    groups: [MIDDLE_OFFICE, UP_TO_1_BILLION_CLUB]
    covering_lobs: [FICC, FX]
  - user_id: comp-001
    given_name: Alex
    family_name: Morgan
    title: Compliance Analyst
    roles: [COMPLIANCE_ANALYST]
    groups: [COMPLIANCE]
""",
        encoding="utf-8",
    )
    return users_file


def test_group_members_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/authorization/groups/UP_TO_100_BILLION_CLUB/members")
    assert response.status_code == 401


def test_group_members_returns_lob_and_covering_lobs(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    users_file = _seed_users(tmp_path)
    monkeypatch.setattr("authz.config.settings.users_file", users_file)
    directory = UserDirectory(users_file)

    compliance = Subject(user_id="comp-001", title="Compliance Analyst", roles=["COMPLIANCE_ANALYST"])
    app.dependency_overrides[get_compliance_subject] = lambda: compliance
    app.dependency_overrides[_user_directory] = lambda: directory
    try:
        response = client.get(
            "/api/v1/authorization/groups/UP_TO_100_BILLION_CLUB/members",
            headers={"Authorization": "Bearer comp-token"},
            params={"role": "FUNDING_APPROVER"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["group"] == "UP_TO_100_BILLION_CLUB"
    assert body["count"] == 1
    member = body["members"][0]
    assert member["user_id"] == "pay-204"
    assert member["covering_lobs"] == ["FICC", "FX", "DESK_RATES"]
    assert member["lob"] is None


def test_group_members_covering_lob_filter(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    users_file = _seed_users(tmp_path)
    monkeypatch.setattr("authz.config.settings.users_file", users_file)
    directory = UserDirectory(users_file)

    compliance = Subject(user_id="comp-001", title="Compliance Analyst", roles=["COMPLIANCE_ANALYST"])
    app.dependency_overrides[get_compliance_subject] = lambda: compliance
    app.dependency_overrides[_user_directory] = lambda: directory
    try:
        response = client.get(
            "/api/v1/authorization/groups/UP_TO_1_BILLION_CLUB/members",
            headers={"Authorization": "Bearer comp-token"},
            params={"role": "FUNDING_APPROVER", "covering_lob": "FX"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["members"][0]["user_id"] == "pay-201"
