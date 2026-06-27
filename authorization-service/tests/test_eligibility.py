from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from authz.eligibility import EligibilityService
from authz.models import PaymentRecord, UserReference
from authz.user_directory import UserDirectory


@pytest.fixture
def sample_payment() -> PaymentRecord:
    return PaymentRecord(
        payment_id="pay-11111111-1111-1111-1111-111111111111",
        instruction_id="instr-22222222-2222-2222-2222-222222222222",
        instruction_version=1,
        status="SUBMITTED",
        amount=5_000_000.0,
        currency="USD",
        owning_lob="FICC",
        created_by=UserReference(user_id="pay-101", supervisor_id="pay-201"),
    )


@pytest.mark.asyncio
async def test_eligible_approvers_filters_by_opa(
    tmp_path,
    sample_payment: PaymentRecord,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    users_yaml = tmp_path / "users.yaml"
    users_yaml.write_text(
        """
defaults:
  password: Password1!
users:
  - user_id: pay-201
    given_name: Sophie
    family_name: Laurent
    title: Vice President
    roles: [FUNDING_APPROVER]
    groups: [MIDDLE_OFFICE, UP_TO_1_BILLION_CLUB]
    covering_lobs: [FICC, FX]
    supervisor_id: pay-300
  - user_id: pay-202
    given_name: Marcus
    family_name: Johnson
    title: Vice President
    roles: [FUNDING_APPROVER]
    groups: [MIDDLE_OFFICE, UP_TO_1_BILLION_CLUB]
    covering_lobs: [FICC, DESK_RATES]
    supervisor_id: pay-300
""",
        encoding="utf-8",
    )

    payments = AsyncMock()
    payments.get_payment.return_value = sample_payment

    ilm = AsyncMock()
    ilm.get_instruction.return_value = {
        "status": "STANDING",
        "end_date": datetime.now(UTC).isoformat(),
    }

    opa = AsyncMock()
    opa.can_approve_payment.side_effect = [
        (True, ["has_role", "covers_lob"]),
        (False, []),
    ]

    service = EligibilityService(
        payments=payments,
        users=UserDirectory(users_yaml),
        ilm=ilm,
        opa=opa,
    )

    result = await service.eligible_approvers_for_payment(sample_payment.payment_id)

    assert result.payment_id == sample_payment.payment_id
    assert len(result.eligible) == 1
    assert result.eligible[0].user_id == "pay-201"
    assert result.candidates_evaluated == 2
    opa.can_approve_payment.assert_awaited()
