from __future__ import annotations

from pathlib import Path

from authz.authorization_routes import _user_directory
from authz.dependencies import get_compliance_subject
from authz.main import app
from authz.models import Subject
from authz.user_directory import UserDirectory
from fastapi.testclient import TestClient


def test_person_permission_summary_for_kowalski(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("authz.config.settings.oidc_issuer_url", "http://localhost:8080")
    users_file = tmp_path / "users.yaml"
    users_file.write_text(
        """
users:
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
    directory = UserDirectory(users_file)
    compliance = Subject(
        user_id="comp-001",
        title="Compliance Analyst",
        roles=["COMPLIANCE_ANALYST"],
    )
    app.dependency_overrides[get_compliance_subject] = lambda: compliance
    app.dependency_overrides[_user_directory] = lambda: directory
    client = TestClient(app)
    try:
        response = client.get(
            "/api/v1/authorization/users/permission-summary",
            headers={"Authorization": "Bearer comp-token"},
            params={"q": "Kowalski, Anna"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    match = body["matches"][0]
    assert match["user_id"] == "pay-203"
    kinds = {item["kind"] for item in match["capabilities"]}
    assert "funding_approve" in kinds
    assert "payment_create" in kinds
