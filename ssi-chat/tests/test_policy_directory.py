from __future__ import annotations

from chat_application.authz.client import format_group_members_answer
from chat_application.policy.directory import (
    directory_groups_for_question,
    is_payment_approval_directory_question,
    is_strict_payment_amount_threshold,
    merge_group_member_rows,
    payment_approval_clubs_for_amount,
    payment_approval_clubs_from_question,
)

# Mirror of opa-policy-seed/policies/payment/amount_limits.rego — test fixture only.
_OPA_CLUB_LIMITS = {
    "UP_TO_100_MILLION_CLUB": 100_000_000.0,
    "UP_TO_1_BILLION_CLUB": 1_000_000_000.0,
    "UP_TO_100_BILLION_CLUB": 100_000_000_000.0,
}
_OPA_ABSOLUTE_LIMIT = 100_000_000_000.0


def test_payment_approval_directory_question_detects_amount() -> None:
    question = "Who all have permission to approve payments worth more than 25 billion?"
    assert is_payment_approval_directory_question(question)
    clubs, amount, strict = payment_approval_clubs_from_question(
        question,
        club_limits=_OPA_CLUB_LIMITS,
        absolute_limit=_OPA_ABSOLUTE_LIMIT,
    )
    assert clubs == ["UP_TO_100_BILLION_CLUB"]
    assert amount == 25_000_000_000.0
    assert strict is True


def test_payment_approval_directory_detects_covering_lob() -> None:
    question = "Who has permission to approve payments belong to LOB FICC?"
    assert is_payment_approval_directory_question(question)
    groups, amount, _strict = directory_groups_for_question(
        question,
        club_limits=_OPA_CLUB_LIMITS,
        absolute_limit=_OPA_ABSOLUTE_LIMIT,
    )
    assert groups == ["MIDDLE_OFFICE"]
    assert amount is None


def test_payment_approval_directory_skips_past_tense_audit() -> None:
    assert not is_payment_approval_directory_question(
        "Who approved payments for LOB FICC?"
    )


def test_payment_approval_directory_skips_when_payment_id_present() -> None:
    question = "Who can approve payment 20260705-FICC-P-8?"
    assert not is_payment_approval_directory_question(question)


def test_payment_approval_clubs_for_amount_inclusive() -> None:
    assert payment_approval_clubs_for_amount(
        50_000_000,
        club_limits=_OPA_CLUB_LIMITS,
        absolute_limit=_OPA_ABSOLUTE_LIMIT,
        strict=False,
    ) == [
        "UP_TO_100_MILLION_CLUB",
        "UP_TO_1_BILLION_CLUB",
        "UP_TO_100_BILLION_CLUB",
    ]
    assert payment_approval_clubs_for_amount(
        500_000_000,
        club_limits=_OPA_CLUB_LIMITS,
        absolute_limit=_OPA_ABSOLUTE_LIMIT,
        strict=False,
    ) == [
        "UP_TO_1_BILLION_CLUB",
        "UP_TO_100_BILLION_CLUB",
    ]
    assert payment_approval_clubs_for_amount(
        25_000_000_000,
        club_limits=_OPA_CLUB_LIMITS,
        absolute_limit=_OPA_ABSOLUTE_LIMIT,
        strict=False,
    ) == [
        "UP_TO_100_BILLION_CLUB",
    ]


def test_exceeding_one_billion_requires_highest_club_only() -> None:
    question = (
        "Who has permission to approve payments exceeding $1 billion, "
        "and for which lines of business?"
    )
    clubs, amount, strict = payment_approval_clubs_from_question(
        question,
        club_limits=_OPA_CLUB_LIMITS,
        absolute_limit=_OPA_ABSOLUTE_LIMIT,
    )
    assert amount == 1_000_000_000.0
    assert strict is True
    assert clubs == ["UP_TO_100_BILLION_CLUB"]


def test_exceeding_one_million_unions_all_eligible_clubs() -> None:
    question = (
        "Who has permission to approve payments exceeding $1 million, "
        "and for which lines of business?"
    )
    clubs, amount, strict = payment_approval_clubs_from_question(
        question,
        club_limits=_OPA_CLUB_LIMITS,
        absolute_limit=_OPA_ABSOLUTE_LIMIT,
    )
    assert amount == 1_000_000.0
    assert strict is True
    assert clubs == [
        "UP_TO_100_MILLION_CLUB",
        "UP_TO_1_BILLION_CLUB",
        "UP_TO_100_BILLION_CLUB",
    ]


def test_at_least_one_billion_includes_one_billion_club() -> None:
    question = "Who can approve payments of at least $1 billion?"
    assert is_strict_payment_amount_threshold(question) is False
    assert payment_approval_clubs_for_amount(
        1_000_000_000.0,
        club_limits=_OPA_CLUB_LIMITS,
        absolute_limit=_OPA_ABSOLUTE_LIMIT,
        strict=False,
    ) == [
        "UP_TO_1_BILLION_CLUB",
        "UP_TO_100_BILLION_CLUB",
    ]


def test_merge_group_member_rows_deduplicates_by_user_id() -> None:
    merged = merge_group_member_rows(
        [
            {"user_id": "pay-201", "groups": ["MIDDLE_OFFICE", "UP_TO_1_BILLION_CLUB"]},
            {"user_id": "pay-201", "groups": ["MIDDLE_OFFICE"]},
            {"user_id": "pay-204", "groups": ["MIDDLE_OFFICE", "UP_TO_100_BILLION_CLUB"]},
        ]
    )
    assert [row["user_id"] for row in merged] == ["pay-201", "pay-204"]


def test_format_group_members_answer_includes_groups_column() -> None:
    text = format_group_members_answer(
        {
            "groups": ["UP_TO_100_BILLION_CLUB"],
            "members": [
                {
                    "user_id": "pay-204",
                    "display_name": "Chen, Wei",
                    "title": "Managing Director",
                    "groups": ["MIDDLE_OFFICE", "UP_TO_100_BILLION_CLUB"],
                    "covering_lobs": ["FICC", "FX", "DESK_RATES"],
                }
            ],
        },
        amount=25_000_000_000.0,
        strict_threshold=True,
    )
    assert "pay-204" in text
    assert "MIDDLE_OFFICE" in text
    assert "FICC" in text
    assert "Groups" in text
    assert "Covering LOBs" in text
    assert "LOB" not in text.split("Covering LOBs")[0]
    assert "exceeding $25 billion" in text


def test_format_group_members_answer_lob_only_header() -> None:
    text = format_group_members_answer(
        {
            "groups": ["MIDDLE_OFFICE"],
            "members": [
                {
                    "user_id": "pay-201",
                    "display_name": "Laurent, Sophie",
                    "title": "Vice President",
                    "groups": ["MIDDLE_OFFICE", "UP_TO_1_BILLION_CLUB"],
                    "covering_lobs": ["FICC", "FX"],
                }
            ],
        },
        covering_lob="FICC",
    )
    assert "FUNDING_APPROVER covering desk FICC" in text
    assert "pay-201" in text
    assert "policy directory" in text


def test_format_group_members_answer_multi_club_header() -> None:
    text = format_group_members_answer(
        {
            "groups": [
                "UP_TO_100_MILLION_CLUB",
                "UP_TO_1_BILLION_CLUB",
                "UP_TO_100_BILLION_CLUB",
            ],
            "members": [],
        },
        amount=1_000_000.0,
        strict_threshold=True,
    )
    assert "UP_TO_100_MILLION_CLUB" in text
    assert "UP_TO_1_BILLION_CLUB" in text
    assert "UP_TO_100_BILLION_CLUB" in text
    assert "exceeding $1 million" in text
