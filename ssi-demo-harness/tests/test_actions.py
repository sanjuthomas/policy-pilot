from __future__ import annotations

from unittest.mock import MagicMock, patch

from harness.actions import (
    _ficc_payment_creator,
    _require_pat,
    create_instructions,
    setup_skill_fixture,
    teardown_skill_fixture,
)
from harness.config import Settings
from harness.fixtures import SeedFile, SeedUser
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


def _seed_user(**kwargs) -> SeedUser:
    base = dict(given_name="A", family_name="B", title="Analyst", roles=[], groups=[])
    base.update(kwargs)
    return SeedUser(**base)


def test_ficc_payment_creator_prefers_deterministic_covering_user() -> None:
    seed = SeedFile(
        users=[
            _seed_user(
                user_id="pay-102",
                roles=["PAYMENT_CREATOR"],
                groups=["MIDDLE_OFFICE"],
                covering_lobs=["FICC"],
            ),
            _seed_user(
                user_id="pay-101",
                roles=["PAYMENT_CREATOR"],
                groups=["MIDDLE_OFFICE"],
                covering_lobs=["FICC", "FX"],
            ),
            _seed_user(
                user_id="pay-203",
                roles=["PAYMENT_CREATOR"],
                groups=["MIDDLE_OFFICE"],
                covering_lobs=["FX"],
            ),
        ]
    )
    assert _ficc_payment_creator(seed) == "pay-101"


def test_ficc_payment_creator_none_when_no_coverage() -> None:
    seed = SeedFile(
        users=[
            _seed_user(
                user_id="pay-203",
                roles=["PAYMENT_CREATOR"],
                groups=["MIDDLE_OFFICE"],
                covering_lobs=["FX"],
            ),
        ]
    )
    assert _ficc_payment_creator(seed) is None


def test_setup_skill_fixture_without_pat() -> None:
    settings = Settings(zitadel_service_pat="")
    admin = SessionCredentials(session_id="s", session_token="t")
    result = setup_skill_fixture(settings, admin, need="instruction")
    assert result.ok is False
    assert result.context == {}
    assert "ZITADEL_SERVICE_PAT" in result.logs[0]


def test_setup_skill_fixture_instruction_only() -> None:
    settings = Settings(zitadel_service_pat="pat")
    admin = SessionCredentials(session_id="s", session_token="t")

    instr_created = MagicMock(status_code=201)
    instr_created.json.return_value = {"instruction_id": "instr-1"}
    ok_200 = MagicMock(status_code=200)

    seed_file = MagicMock(defaults={"password": "Password1!"})
    instruction_service = MagicMock()
    instruction_service.create_instruction.return_value = instr_created
    instruction_service.submit_instruction.return_value = ok_200
    instruction_service.approve_instruction.return_value = ok_200
    creator = _seed_user(user_id="mo-100", title="Analyst", roles=["INSTRUCTION_CREATOR"])

    with patch(
        "harness.actions._clients",
        return_value=(seed_file, MagicMock(), instruction_service),
    ), patch(
        "harness.actions._valid_instruction_seed_pairs",
        return_value=[("mo-100", "FICC")],
    ), patch(
        "harness.actions.user_by_id", return_value=creator
    ), patch(
        "harness.actions._eligible_instruction_approvers", return_value=["ficc-300"]
    ), patch(
        "harness.actions._session_for_user",
        return_value=SessionCredentials(session_id="u", session_token="t"),
    ), patch(
        "harness.actions.build_instruction_payload", return_value={"x": 1}
    ):
        result = setup_skill_fixture(settings, admin, need="instruction")

    assert result.ok is True
    assert result.succeeded == 1
    assert result.context["ficc_standing_instruction_id"] == "instr-1"
    assert "draft_payment_id" not in result.context
    assert "submitted_payment_id" not in result.context


def test_setup_skill_fixture_draft() -> None:
    settings = Settings(zitadel_service_pat="pat")
    admin = SessionCredentials(session_id="s", session_token="t")

    instr_created = MagicMock(status_code=201)
    instr_created.json.return_value = {"instruction_id": "instr-1"}
    ok_200 = MagicMock(status_code=200)
    draft = MagicMock(status_code=201)
    draft.json.return_value = {"payment_id": "pay-draft-1"}

    seed_file = MagicMock(defaults={"password": "Password1!"})
    instruction_service = MagicMock()
    instruction_service.create_instruction.return_value = instr_created
    instruction_service.submit_instruction.return_value = ok_200
    instruction_service.approve_instruction.return_value = ok_200
    ps = MagicMock()
    ps.create_payment.return_value = draft
    creator = _seed_user(user_id="mo-100", title="Analyst", roles=["INSTRUCTION_CREATOR"])

    with patch(
        "harness.actions._clients",
        return_value=(seed_file, MagicMock(), instruction_service),
    ), patch("harness.actions.payment_client", return_value=ps), patch(
        "harness.actions._valid_instruction_seed_pairs",
        return_value=[("mo-100", "FICC")],
    ), patch(
        "harness.actions.user_by_id", return_value=creator
    ), patch(
        "harness.actions._eligible_instruction_approvers", return_value=["ficc-300"]
    ), patch(
        "harness.actions._session_for_user",
        return_value=SessionCredentials(session_id="u", session_token="t"),
    ), patch(
        "harness.actions.build_instruction_payload", return_value={"x": 1}
    ), patch(
        "harness.actions._ficc_payment_creator", return_value="pay-101"
    ):
        result = setup_skill_fixture(settings, admin, need="draft")

    assert result.ok is True
    assert result.context == {
        "ficc_standing_instruction_id": "instr-1",
        "skill_fixture_instruction_creator": "mo-100",
        "skill_fixture_payment_creator": "pay-101",
        "draft_payment_id": "pay-draft-1",
    }
    ps.submit_payment.assert_not_called()


def test_teardown_skill_fixture_cancels_and_suspends() -> None:
    settings = Settings(zitadel_service_pat="pat")
    admin = SessionCredentials(session_id="s", session_token="t")
    ok_200 = MagicMock(status_code=200)
    suspend_session = SessionCredentials(session_id="md", session_token="t")

    seed_file = MagicMock(defaults={"password": "Password1!"})
    instruction_service = MagicMock()
    instruction_service.suspend_instruction.return_value = ok_200
    ps = MagicMock()
    ps.cancel_payment.return_value = ok_200

    with patch(
        "harness.actions._clients",
        return_value=(seed_file, MagicMock(), instruction_service),
    ), patch("harness.actions.payment_client", return_value=ps), patch(
        "harness.actions._session_for_user",
        return_value=suspend_session,
    ), patch(
        "harness.actions._ficc_instruction_suspender", return_value="ficc-400"
    ):
        result = teardown_skill_fixture(
            settings,
            admin,
            context={
                "ficc_standing_instruction_id": "instr-1",
                "draft_payment_id": "pay-1",
                "skill_fixture_payment_creator": "pay-101",
            },
        )

    assert result.ok is True
    assert result.succeeded == 2
    ps.cancel_payment.assert_called_once()
    instruction_service.suspend_instruction.assert_called_once_with(
        suspend_session, "instr-1"
    )
