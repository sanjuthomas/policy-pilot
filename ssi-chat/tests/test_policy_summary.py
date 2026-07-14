from __future__ import annotations

from chat_application.authz.client import format_policy_summary_answer
from chat_application.policy.summary import detect_policy_summary_question


def test_detect_funding_approval_policy() -> None:
    assert detect_policy_summary_question("What is the funding approval policy?") == (
        "payment",
        "APPROVE",
    )


def test_detect_instruction_approval_policy() -> None:
    assert detect_policy_summary_question("Can you tell me the instruction approval policy?") == (
        "instruction",
        "APPROVE",
    )


def test_detect_payment_creation_policy() -> None:
    assert detect_policy_summary_question("Explain the payment creation policy") == (
        "payment",
        "CREATE",
    )


def test_detect_policies_mode_relaxes_policy_cue() -> None:
    assert detect_policy_summary_question("funding approval", mode="policies") == (
        "payment",
        "APPROVE",
    )
    assert detect_policy_summary_question("instruction approval", mode="policies") == (
        "instruction",
        "APPROVE",
    )


def test_detect_skips_who_list_directory_questions() -> None:
    assert (
        detect_policy_summary_question(
            "Who has permission to approve payments worth more than $25 billion?"
        )
        is None
    )


def test_detect_skips_eligibility_questions() -> None:
    assert detect_policy_summary_question("Who can approve payment 20260705-FX-P-534?") is None


def test_format_policy_summary_answer() -> None:
    text = format_policy_summary_answer(
        {
            "domain": "payment",
            "action": "APPROVE",
            "title": "Funding approval",
            "narrative": (
                "Someone with the FUNDING_APPROVER role, who belongs to the "
                "MIDDLE_OFFICE group and an amount-limit club, and whose "
                "covering_lobs include the instruction's owning LOB, may approve "
                "a payment."
            ),
            "requires": [
                {"kind": "role", "value": "FUNDING_APPROVER"},
                {"kind": "group", "value": "MIDDLE_OFFICE"},
                {"kind": "covering_lobs", "value": "instruction owning LOB"},
            ],
            "source": "opa",
        }
    )
    assert "Funding approval" in text
    assert "FUNDING_APPROVER" in text
    assert "**role**: FUNDING_APPROVER" in text
    assert "authorization-service" in text
