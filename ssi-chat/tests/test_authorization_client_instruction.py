from chat_application.authorization_client import (
    format_instruction_eligible_approvers_answer,
)


def test_format_instruction_eligible_approvers_answer_lists_users() -> None:
    text = format_instruction_eligible_approvers_answer(
        {
            "instruction_id": "inst-1",
            "instruction_status": "SUBMITTED",
            "instruction_type": "STANDING",
            "owning_lob": "FICC",
            "created_by_user_id": "ficc-101",
            "created_by_title": "Analyst",
            "eligible": [
                {
                    "user_id": "ficc-300",
                    "display_name": "Vasquez, Elena (ficc-300)",
                    "title": "Vice President",
                    "allow_basis": ["approval matrix"],
                }
            ],
            "candidates_evaluated": 4,
        }
    )

    assert "instruction inst-1" in text
    assert "Vasquez, Elena" in text
    assert "INSTRUCTION_APPROVER" in text
    assert "| Approver" in text


def test_format_instruction_eligible_approvers_answer_shows_draft_block_and_prospective() -> None:
    text = format_instruction_eligible_approvers_answer(
        {
            "instruction_id": "20260703-FICC-I-8",
            "instruction_status": "DRAFT",
            "instruction_type": "STANDING",
            "owning_lob": "FICC",
            "created_by_user_id": "mo-100",
            "created_by_title": "Analyst",
            "eligible": [],
            "prospective_eligible": [
                {
                    "user_id": "ficc-201",
                    "display_name": "Torres, Michael (ficc-201)",
                    "title": "Associate",
                    "allow_basis": ["approval matrix"],
                }
            ],
            "candidates_evaluated": 4,
            "approval_blocked_reason": (
                "Approval is not permitted while status is DRAFT. Submit the instruction first."
            ),
        }
    )

    assert "Approval is not permitted while status is DRAFT" in text
    assert "After submission" in text
    assert "Torres, Michael" in text
    assert "Users who can approve this instruction" not in text
