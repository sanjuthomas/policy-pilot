from __future__ import annotations

from unittest.mock import MagicMock, patch

from harness.actions import _require_pat, create_instructions
from harness.config import Settings
from harness.results import HarnessActionResult
from harness.zitadel_auth import SessionCredentials


def test_require_pat_missing() -> None:
    settings = Settings(zitadel_service_pat="")
    assert _require_pat(settings) == "ZITADEL_SERVICE_PAT is required for session login"


def test_require_pat_present() -> None:
    settings = Settings(zitadel_service_pat="pat")
    assert _require_pat(settings) is None


def test_create_instructions_without_pat() -> None:
    settings = Settings(zitadel_service_pat="")
    admin = SessionCredentials(session_id="s", session_token="t")
    result = create_instructions(settings, 1, admin)
    assert result.ok is False
    assert result.failed == 0
    assert "ZITADEL_SERVICE_PAT" in result.logs[0]


def test_create_instructions_success() -> None:
    settings = Settings(zitadel_service_pat="pat")
    admin = SessionCredentials(session_id="s", session_token="t")
    response = MagicMock(status_code=201)
    response.json.return_value = {"instruction_id": "instr-1"}

    with patch("harness.actions.load_users") as mock_seed, patch(
        "harness.actions.auth_client"
    ) as mock_auth_factory, patch("harness.actions.instruction_service_client") as mock_instruction_factory, patch(
        "harness.actions._session_for_user",
        return_value=SessionCredentials(session_id="u", session_token="t"),
    ), patch(
        "harness.actions.build_seed_plan",
        return_value=[("mo-100", "FICC", "SINGLE_USE", "USD")],
    ), patch(
        "harness.actions.build_instruction_payload",
        return_value={"instruction_type": "SINGLE_USE"},
    ):
        mock_seed.return_value = MagicMock(defaults={"password": "Password1!"})
        mock_instruction_service = MagicMock()
        mock_instruction_service.create_instruction.return_value = response
        mock_instruction_factory.return_value = mock_instruction_service
        mock_auth_factory.return_value = MagicMock()

        result = create_instructions(settings, 1, admin)

    assert isinstance(result, HarnessActionResult)
    assert result.succeeded == 1
    assert result.ok is True
