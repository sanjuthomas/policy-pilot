from chat_application.authorization_client import format_eligible_approvers_answer


def test_format_eligible_approvers_answer_lists_users() -> None:
    text = format_eligible_approvers_answer(
        {
            "payment_id": "p1",
            "payment_status": "SUBMITTED",
            "amount": 1_000_000,
            "currency": "USD",
            "owning_lob": "FICC",
            "instruction_status": "STANDING",
            "candidates_evaluated": 3,
            "eligible": [
                {
                    "user_id": "pay-201",
                    "display_name": "Laurent, Sophie (pay-201)",
                    "title": "Vice President",
                    "allow_basis": ["has_role", "covers_lob"],
                }
            ],
        }
    )

    assert "pay-201" in text
    assert "Laurent, Sophie" in text
    assert "Evaluated 3" in text


def test_format_eligible_approvers_answer_empty() -> None:
    text = format_eligible_approvers_answer(
        {
            "payment_id": "p1",
            "payment_status": "SUBMITTED",
            "amount": 100,
            "currency": "USD",
            "owning_lob": "FICC",
            "instruction_status": "STANDING",
            "eligible": [],
        }
    )
    assert "No users currently satisfy" in text
