from __future__ import annotations

from chat_application.authorization_client import format_group_members_answer
from chat_application.policy_directory import (
    is_payment_approval_directory_question,
    payment_approval_club_for_amount,
    payment_approval_group_from_question,
)


def test_payment_approval_directory_question_detects_amount() -> None:
    question = "Who all have permission to approve payments worth more than 25 billion?"
    assert is_payment_approval_directory_question(question)
    group, amount = payment_approval_group_from_question(question)
    assert group == "UP_TO_100_BILLION_CLUB"
    assert amount == 25_000_000_000.0


def test_payment_approval_directory_skips_when_payment_id_present() -> None:
    question = "Who can approve payment 20260705-FICC-P-8?"
    assert not is_payment_approval_directory_question(question)


def test_payment_approval_club_for_amount() -> None:
    assert payment_approval_club_for_amount(50_000_000) == "UP_TO_100_MILLION_CLUB"
    assert payment_approval_club_for_amount(500_000_000) == "UP_TO_1_BILLION_CLUB"
    assert payment_approval_club_for_amount(25_000_000_000) == "UP_TO_100_BILLION_CLUB"


def test_format_group_members_answer_includes_lob_columns() -> None:
    text = format_group_members_answer(
        {
            "group": "UP_TO_100_BILLION_CLUB",
            "members": [
                {
                    "user_id": "pay-204",
                    "display_name": "Chen, Wei",
                    "title": "Managing Director",
                    "lob": None,
                    "covering_lobs": ["FICC", "FX", "DESK_RATES"],
                }
            ],
        },
        amount=25_000_000_000.0,
    )
    assert "pay-204" in text
    assert "FICC" in text
    assert "Covering LOBs" in text
    assert "$25 billion" in text
