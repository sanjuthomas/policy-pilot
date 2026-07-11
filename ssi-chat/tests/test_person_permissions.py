from __future__ import annotations

from chat_application.authorization_client import format_person_permission_summary_answer
from chat_application.person_permissions import extract_person_permission_query


def test_extract_permissions_of_display_name() -> None:
    assert (
        extract_person_permission_query("Can you list the permissions of Kowalski, Anna?")
        == "Kowalski, Anna"
    )


def test_extract_permissions_for_user_id() -> None:
    assert extract_person_permission_query("Summarize permissions for pay-203") == "pay-203"


def test_extract_skips_who_list_questions() -> None:
    assert (
        extract_person_permission_query(
            "Who has permission to approve payments for LOB FICC?"
        )
        is None
    )


def test_format_person_permission_summary_answer() -> None:
    text = format_person_permission_summary_answer(
        {
            "query": "Kowalski, Anna",
            "count": 1,
            "matches": [
                {
                    "user_id": "pay-203",
                    "display_name": "Kowalski, Anna",
                    "title": "Associate",
                    "lob": None,
                    "roles": ["PAYMENT_CREATOR", "FUNDING_APPROVER"],
                    "groups": ["MIDDLE_OFFICE"],
                    "amount_clubs": ["UP_TO_100_MILLION_CLUB"],
                    "covering_lobs": ["FX"],
                    "capabilities": [
                        {
                            "kind": "funding_approve",
                            "description": "Approve/reject payments for covering LOBs (FX)",
                        }
                    ],
                    "narrative": "Kowalski, Anna (pay-203) is a dual-role funding approver.",
                }
            ],
        }
    )
    assert "Kowalski, Anna" in text
    assert "pay-203" in text
    assert "funding_approve" in text
    assert "UP_TO_100_MILLION_CLUB" in text
