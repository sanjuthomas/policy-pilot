from __future__ import annotations

from unittest.mock import AsyncMock, patch


def test_health_reports_degraded_when_opa_unready(test_client) -> None:
    with patch("authz.main.OpaClient") as opa_cls:
        opa_cls.return_value.policy_health = AsyncMock(
            return_value={
                "ok": False,
                "policy_count": 0,
                "detail": "expected at least 15 policies",
            }
        )
        response = test_client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "DEGRADED"
    assert payload["components"]["opa"]["ok"] is False


def test_health_reports_up_when_opa_ready(test_client) -> None:
    with patch("authz.main.OpaClient") as opa_cls:
        opa_cls.return_value.policy_health = AsyncMock(
            return_value={
                "ok": True,
                "policy_count": 15,
                "detail": "policies loaded",
            }
        )
        response = test_client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "UP"
    assert payload["components"]["opa"]["policy_count"] == 15
