from __future__ import annotations

import os

import pytest
from authz.admin import get_admin_subject
from authz.models import Subject
from authz.user_directory import UserDirectory
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def disable_open_telemetry_for_tests() -> None:
    os.environ["OTEL_SDK_DISABLED"] = "true"


@pytest.fixture
def test_client(monkeypatch):
    monkeypatch.setattr("authz.config.settings.oidc_issuer_url", "http://localhost:8080")
    monkeypatch.setattr(
        "authz.user_directory.UserDirectory.from_zitadel",
        classmethod(lambda cls, **kwargs: UserDirectory.from_users([])),
    )

    from authz import main as main_module

    admin_subject = Subject(
        user_id="admin-001",
        title="Platform Admin",
        roles=["PLATFORM_ADMIN"],
    )
    main_module.app.dependency_overrides[get_admin_subject] = lambda: admin_subject

    with TestClient(main_module.app) as client:
        yield client

    main_module.app.dependency_overrides.clear()
