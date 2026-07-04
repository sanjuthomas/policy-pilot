from chat_application.authorization_client import format_eligible_approvers_answer


def test_format_eligible_approvers_answer_lists_users() -> None:
    text = format_eligible_approvers_answer(
        {
            "payment_id": "p1",
            "payment_status": "SUBMITTED",
            "amount": 1_000_000,
            "currency": "USD",
            "owning_lob": "FICC",
            "instruction_status": "APPROVED",
            "candidates_evaluated": 3,
            "eligible": [
                {
                    "user_id": "pay-201",
                    "display_name": "Laurent, Sophie (pay-201)",
                    "title": "Vice President",
                    "allow_basis": ["has_role", "covers LOB FICC"],
                }
            ],
        }
    )

    assert "pay-201" in text
    assert "Laurent, Sophie" in text
    assert "Evaluated 3" in text
    assert "| Approver" in text
    assert "| Policy basis" in text
    assert "USD 1,000,000.00" in text


def test_format_eligible_approvers_answer_humanizes_scientific_amounts() -> None:
    text = format_eligible_approvers_answer(
        {
            "payment_id": "20260628-FICC-P-14",
            "payment_status": "APPROVED",
            "amount": 1_000_000,
            "currency": "USD",
            "owning_lob": "FICC",
            "instruction_status": "APPROVED",
            "candidates_evaluated": 2,
            "eligible": [
                {
                    "user_id": "pay-201",
                    "display_name": "Laurent, Sophie (pay-201)",
                    "title": "Vice President",
                    "allow_basis": [
                        "amount 1e+06 within subject and absolute limits",
                        "role FUNDING_APPROVER",
                    ],
                }
            ],
        }
    )

    assert "USD 1,000,000.00" in text
    assert "1e+06" not in text
    assert "$1 million within subject and absolute limits" in text
    assert "| Laurent, Sophie (pay-201)" in text


def test_format_eligible_approvers_answer_empty() -> None:
    text = format_eligible_approvers_answer(
        {
            "payment_id": "p1",
            "payment_status": "SUBMITTED",
            "amount": 100,
            "currency": "USD",
            "owning_lob": "FICC",
            "instruction_status": "APPROVED",
            "eligible": [],
        }
    )
    assert "No users currently satisfy" in text


def test_format_eligible_approvers_answer_shows_used_instruction_block() -> None:
    text = format_eligible_approvers_answer(
        {
            "payment_id": "20260704-FICC-P-2",
            "instruction_id": "20260704-FICC-I-6",
            "payment_status": "DRAFT",
            "amount": 100_000_000,
            "currency": "USD",
            "owning_lob": "FICC",
            "instruction_status": "USED",
            "eligible": [],
            "prospective_eligible": [],
            "approval_blocked_reason": (
                "The backing instruction 20260704-FICC-I-6 is USED and cannot support "
                "payment approval."
            ),
        }
    )

    assert "20260704-FICC-P-2" in text
    assert "20260704-FICC-I-6" in text
    assert "backing instruction 20260704-FICC-I-6 (USED)" in text
    assert "cannot support payment approval" in text
    assert "No users currently satisfy" not in text


def test_format_eligible_approvers_answer_shows_draft_block_and_prospective() -> None:
    text = format_eligible_approvers_answer(
        {
            "payment_id": "p1",
            "payment_status": "DRAFT",
            "amount": 100,
            "currency": "USD",
            "owning_lob": "FICC",
            "instruction_status": "APPROVED",
            "eligible": [],
            "prospective_eligible": [
                {
                    "user_id": "pay-400",
                    "display_name": "Osei, Victoria (pay-400)",
                    "title": "Vice President",
                    "allow_basis": ["has_role"],
                }
            ],
            "candidates_evaluated": 3,
            "approval_blocked_reason": (
                "Payment approval is not permitted while status is DRAFT. "
                "Submit the payment first."
            ),
        }
    )

    assert "Payment approval is not permitted while status is DRAFT" in text
    assert "After the payment is submitted" in text
    assert "Osei, Victoria" in text
    assert "Users who can approve this payment" not in text
