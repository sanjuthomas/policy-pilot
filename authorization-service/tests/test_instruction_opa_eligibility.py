from __future__ import annotations

from authz.instruction_opa import instruction_opa_context_for_approval_eligibility


def test_draft_instruction_evaluated_as_submitted_for_eligibility() -> None:
    instruction = {
        "status": "DRAFT",
        "instruction_type": "STANDING",
        "owning_lob": "FICC",
        "effective_date": "2026-07-03T00:00:00Z",
        "end_date": "2027-07-03T00:00:00Z",
        "created_by": {
            "user_id": "mo-100",
            "title": "Analyst",
            "supervisor_id": "mo-050",
        },
        "funding_account": {"owning_lob": "FICC"},
    }

    opa_instruction, _opa_account, note = instruction_opa_context_for_approval_eligibility(
        instruction
    )

    assert opa_instruction["status"] == "DRAFT"
    assert note is not None


def test_draft_instruction_prospective_context_uses_submitted() -> None:
    from authz.instruction_opa import instruction_opa_context_after_submission

    instruction = {
        "status": "DRAFT",
        "instruction_type": "STANDING",
        "owning_lob": "FICC",
        "created_by": {"user_id": "mo-100", "title": "Analyst"},
        "funding_account": {"owning_lob": "FICC"},
    }

    opa_instruction, _opa_account = instruction_opa_context_after_submission(instruction)

    assert opa_instruction is not None
    assert opa_instruction["status"] == "SUBMITTED"


def test_submitted_instruction_not_rewritten_for_eligibility() -> None:
    instruction = {
        "status": "SUBMITTED",
        "instruction_type": "STANDING",
        "owning_lob": "FICC",
        "created_by": {"user_id": "mo-100", "title": "Analyst"},
        "funding_account": {"owning_lob": "FICC"},
    }

    opa_instruction, _opa_account, note = instruction_opa_context_for_approval_eligibility(
        instruction
    )

    assert opa_instruction["status"] == "SUBMITTED"
    assert note is None
