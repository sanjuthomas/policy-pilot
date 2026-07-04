from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from authz.opa import OpaClient


@pytest.mark.asyncio
async def test_list_policy_ids() -> None:
    client = OpaClient(base_url="http://opa.test")

    with patch("authz.opa.httpx.AsyncClient") as client_cls:
        http_client = AsyncMock()
        response = AsyncMock()
        response.raise_for_status = lambda: None
        response.json = lambda: {
            "result": [{"id": "policies/instruction/lifecycle.rego"}],
        }
        http_client.get = AsyncMock(return_value=response)
        client_cls.return_value.__aenter__.return_value = http_client

        policy_ids = await client.list_policy_ids()

    assert policy_ids == ["policies/instruction/lifecycle.rego"]


@pytest.mark.asyncio
async def test_policy_health_ok() -> None:
    client = OpaClient(base_url="http://opa.test")

    with patch.object(client, "list_policy_ids", new_callable=AsyncMock) as list_policies:
        with patch.object(client, "_post_data", new_callable=AsyncMock, return_value=True):
            list_policies.return_value = ["p"] * 11
            status = await client.policy_health()

    assert status["ok"] is True
    assert status["policy_count"] == 11


@pytest.mark.asyncio
async def test_policy_health_degraded_when_empty() -> None:
    client = OpaClient(base_url="http://opa.test")

    with patch.object(client, "list_policy_ids", new_callable=AsyncMock, return_value=[]):
        status = await client.policy_health()

    assert status["ok"] is False
    assert status["policy_count"] == 0


@pytest.mark.asyncio
async def test_policy_health_degraded_when_smoke_denied() -> None:
    client = OpaClient(base_url="http://opa.test")

    with patch.object(client, "list_policy_ids", new_callable=AsyncMock) as list_policies:
        with patch.object(client, "_post_data", new_callable=AsyncMock, return_value=False):
            list_policies.return_value = ["p"] * 11
            status = await client.policy_health()

    assert status["ok"] is False
    assert "smoke" in status["detail"]


@pytest.mark.asyncio
async def test_policy_health_degraded_when_opa_unreachable() -> None:
    client = OpaClient(base_url="http://opa.test")

    with patch.object(
        client,
        "list_policy_ids",
        new_callable=AsyncMock,
        side_effect=RuntimeError("connection refused"),
    ):
        status = await client.policy_health()

    assert status["ok"] is False
    assert "connection refused" in status["detail"]
