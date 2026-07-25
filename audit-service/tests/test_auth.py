from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException

from audit_console.auth import (
    decode_metadata,
    parse_list,
    resolve_auditor,
    zitadel_base,
    zitadel_headers,
)
from audit_console.config import settings


def test_metadata_helpers() -> None:
    encoded = base64.b64encode(b"Technology Auditor").decode()
    assert decode_metadata({"title": encoded, "skip": 1}) == {
        "title": "Technology Auditor"
    }
    assert parse_list(json.dumps(["TECH_AUDITOR"])) == ["TECH_AUDITOR"]
    assert parse_list("one,two") == ["one", "two"]
    assert parse_list(None) == []
    assert zitadel_base()
    assert zitadel_headers()["Host"] == "localhost:8080"


def response(status: int, body: dict, url: str) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("GET", url))


@pytest.mark.asyncio
async def test_resolve_auditor_allows_required_group() -> None:
    metadata = {
        "subject_user_id": "audit-001",
        "title": "Technology Auditor",
        "roles": json.dumps(["TECH_AUDITOR"]),
        "groups": json.dumps(["TECH_AUDITORS"]),
    }
    encoded = [
        {"key": key, "value": base64.b64encode(value.encode()).decode()}
        for key, value in metadata.items()
    ]
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get.return_value = response(
        200,
        {"session": {"factors": {"user": {"id": "z-1", "loginName": "audit-001"}}}},
        "http://zitadel/v2/sessions/s-1",
    )
    mock_client.post.return_value = response(
        200, {"metadata": encoded}, "http://zitadel/v2/users/z-1/metadata/search"
    )

    with (
        patch.object(settings, "zitadel_service_pat", "pat"),
        patch("audit_console.auth.httpx.AsyncClient", return_value=mock_client),
    ):
        subject = await resolve_auditor("Bearer token", "s-1")

    assert subject.user_id == "audit-001"
    assert subject.groups == ["TECH_AUDITORS"]


@pytest.mark.asyncio
async def test_resolve_auditor_rejects_missing_headers_and_group() -> None:
    with pytest.raises(HTTPException) as missing:
        await resolve_auditor(None, None)
    assert missing.value.status_code == 401

    metadata = [
        {
            "key": "groups",
            "value": base64.b64encode(json.dumps(["COMPLIANCE"]).encode()).decode(),
        },
        {
            "key": "roles",
            "value": base64.b64encode(json.dumps(["COMPLIANCE_ANALYST"]).encode()).decode(),
        },
    ]
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get.return_value = response(
        200,
        {"session": {"factors": {"user": {"id": "z-2", "loginName": "comp-001"}}}},
        "http://zitadel/v2/sessions/s-2",
    )
    mock_client.post.return_value = response(
        200, {"metadata": metadata}, "http://zitadel/v2/users/z-2/metadata/search"
    )
    with (
        patch.object(settings, "zitadel_service_pat", "pat"),
        patch("audit_console.auth.httpx.AsyncClient", return_value=mock_client),
        pytest.raises(HTTPException) as denied,
    ):
        await resolve_auditor("Bearer token", "s-2")
    assert denied.value.status_code == 403
