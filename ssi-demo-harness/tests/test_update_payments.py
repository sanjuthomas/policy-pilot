from __future__ import annotations

import random
from pathlib import Path
from unittest.mock import MagicMock

import httpx
from harness.fixtures import load_users
from harness.helpers import resolve_payment_update_amount
from harness.payment_client import PaymentServiceClient
from harness.results import HarnessActionResult


def _users_file() -> Path:
    return Path(__file__).resolve().parents[2] / "zitadel-seed" / "users.yaml"


def test_resolve_payment_update_amount_override() -> None:
    seed = load_users(_users_file())
    amount = resolve_payment_update_amount(
        1_000_000.0,
        "pay-101",
        seed=seed,
        override=2_000_000.0,
    )
    assert amount == 2_000_000.0


def test_resolve_payment_update_amount_auto_bump() -> None:
    seed = load_users(_users_file())
    amount = resolve_payment_update_amount(
        500_000.0,
        "pay-101",
        seed=seed,
        rng=random.Random(0),
    )
    assert amount > 500_000.0


def test_payment_client_update_payment(monkeypatch) -> None:
    client = PaymentServiceClient(MagicMock(payment_service_url="http://ps", payment_service_api_prefix="/api/v1"))
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {"payment_id": "p1", "version_number": 2, "amount": 2_000_000.0}

    class FakeHttpxClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["json"] = kwargs.get("json")
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: FakeHttpxClient())
    session = MagicMock(session_token="tok", session_id="sid")
    response = client.update_payment(session, "p1", "instr-1", 2_000_000.0, "2026-07-01")

    assert response.status_code == 200
    assert captured["method"] == "PUT"
    assert captured["json"]["amount"] == 2_000_000.0


def test_update_payments_action(monkeypatch) -> None:
    from harness import actions
    from harness.config import Settings

    settings = Settings()
    admin_session = MagicMock()

    drafts = [
        {
            "payment_id": "p1",
            "instruction_id": "instr-1",
            "value_date": "2026-07-01",
            "amount": 1_000_000.0,
            "created_by": {"user_id": "pay-101"},
        }
    ]

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {"payment_id": "p1", "version_number": 2, "amount": 2_000_000.0}

    fake_ps = MagicMock()
    fake_ps.update_payment.return_value = FakeResponse()

    monkeypatch.setattr(actions, "_require_pat", lambda _settings: None)
    monkeypatch.setattr(actions, "_payment_clients", lambda _settings: (MagicMock(), MagicMock(), fake_ps))
    monkeypatch.setattr(actions, "_fetch_api_payments", lambda *args, **kwargs: drafts)
    monkeypatch.setattr(actions, "_session_for_user", lambda *args, **kwargs: MagicMock())
    monkeypatch.setattr(
        "harness.actions.resolve_payment_update_amount",
        lambda current, creator, **kwargs: 2_000_000.0,
    )

    result = actions.update_payments(settings, 1, admin_session, amount=2_000_000.0)

    assert isinstance(result, HarnessActionResult)
    assert result.succeeded == 1
    fake_ps.update_payment.assert_called_once()
