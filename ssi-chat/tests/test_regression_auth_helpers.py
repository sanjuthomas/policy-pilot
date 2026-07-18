from __future__ import annotations

import pytest
from regression.auth_helpers import obo_headers


def test_obo_headers_composes_service_and_user() -> None:
    headers = obo_headers(
        {
            "Authorization": "Bearer svc-token",
            "X-Session-Id": "svc-sid",
        },
        {
            "Authorization": "Bearer user-token",
            "X-Session-Id": "user-sid",
        },
    )
    assert headers == {
        "Authorization": "Bearer svc-token",
        "Accept": "application/json",
        "X-On-Behalf-Of": "user-token",
        "X-Session-Id": "svc-sid",
        "X-On-Behalf-Of-Session-Id": "user-sid",
    }


def test_obo_headers_requires_bearer_tokens() -> None:
    with pytest.raises(ValueError, match="service_headers"):
        obo_headers({}, {"Authorization": "Bearer user"})
    with pytest.raises(ValueError, match="user_headers"):
        obo_headers({"Authorization": "Bearer svc"}, {})
