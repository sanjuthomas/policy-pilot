from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from authz.eligibility import EligibilityService
from authz.models import InstructionEligibleApproversEvaluateRequest
from authz.user_directory import UserDirectory


@pytest.mark.asyncio
async def test_eligible_instruction_approvers_filters_by_opa(tmp_path) -> None:
    users_yaml = tmp_path / "users.yaml"
    users_yaml.write_text(
        """
defaults:
  password: Password1!
users:
  - user_id: ficc-300
    given_name: Elena
    family_name: Vasquez
    title: Vice President
    lob: FICC
    roles: [INSTRUCTION_APPROVER]
    supervisor_id: ficc-400
  - user_id: ficc-201
    given_name: Michael
    family_name: Torres
    title: Associate
    lob: FICC
    roles: [INSTRUCTION_APPROVER]
    supervisor_id: ficc-300
""",
        encoding="utf-8",
    )

    opa = AsyncMock()
    opa.can_approve_instruction.side_effect = [
        (True, ["approval matrix"]),
        (False, []),
    ]

    service = EligibilityService(
        users=UserDirectory.from_yaml(users_yaml),
        opa=opa,
    )

    result = await service.eligible_approvers_for_instruction(
        InstructionEligibleApproversEvaluateRequest(
            instruction={
                "instruction_id": "inst-1",
                "status": "SUBMITTED",
                "instruction_type": "STANDING",
                "owning_lob": "FICC",
                "effective_date": datetime.now(UTC).isoformat(),
                "end_date": datetime.now(UTC).isoformat(),
                "created_by": {
                    "user_id": "ficc-101",
                    "title": "Analyst",
                    "supervisor_id": "ficc-201",
                },
                "funding_account": {"owning_lob": "FICC"},
            }
        )
    )

    assert result.instruction_id == "inst-1"
    assert len(result.eligible) == 1
    assert result.eligible[0].user_id == "ficc-201"
    assert result.candidates_evaluated == 2


@pytest.mark.asyncio
async def test_eligible_instruction_approvers_evaluates_draft_as_submitted(tmp_path) -> None:
    users_yaml = tmp_path / "users.yaml"
    users_yaml.write_text(
        """
defaults:
  password: Password1!
users:
  - user_id: ficc-201
    given_name: Michael
    family_name: Torres
    title: Associate
    lob: FICC
    roles: [INSTRUCTION_APPROVER]
    supervisor_id: ficc-300
""",
        encoding="utf-8",
    )

    opa = AsyncMock()
    opa.can_approve_instruction.side_effect = [
        (False, []),
        (True, ["approval matrix"]),
    ]

    service = EligibilityService(
        users=UserDirectory.from_yaml(users_yaml),
        opa=opa,
    )

    result = await service.eligible_approvers_for_instruction(
        InstructionEligibleApproversEvaluateRequest(
            instruction={
                "instruction_id": "inst-draft",
                "status": "DRAFT",
                "instruction_type": "STANDING",
                "owning_lob": "FICC",
                "effective_date": datetime.now(UTC).isoformat(),
                "end_date": datetime.now(UTC).isoformat(),
                "created_by": {
                    "user_id": "mo-100",
                    "title": "Analyst",
                    "supervisor_id": "mo-050",
                },
                "funding_account": {"owning_lob": "FICC"},
            }
        )
    )

    assert len(result.eligible) == 0
    assert len(result.prospective_eligible) == 1
    assert result.prospective_eligible[0].user_id == "ficc-201"
    assert result.approval_blocked_reason is not None
    assert opa.can_approve_instruction.await_count == 2
    assert opa.can_approve_instruction.await_args_list[0].kwargs["opa_instruction"]["status"] == "DRAFT"
    assert opa.can_approve_instruction.await_args_list[1].kwargs["opa_instruction"]["status"] == "SUBMITTED"
