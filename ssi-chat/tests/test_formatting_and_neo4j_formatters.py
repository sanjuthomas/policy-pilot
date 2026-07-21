from __future__ import annotations

from chat_application.formatting import (
    coerce_numeric_amount,
    escape_markdown_cell,
    format_eligible_approvers_section,
    format_money_amount,
    format_policy_basis_cell,
    format_usd_compact,
    humanize_authorization_text,
    humanize_policy_basis,
)
from chat_application.formatting.neo4j import (
    FORMATTERS,
    format_alert_count_today,
    format_instruction_approver_by_id,
    format_instruction_compliance_table,
    format_instruction_conflict_table,
    format_instruction_creator_and_approver_by_id,
    format_instruction_creator_by_id,
    format_instruction_inventory_table,
    format_instruction_mutual_approval,
    format_instruction_status_by_id,
    format_security_event_alert_list,
    format_security_event_timeline,
)


class TestFormattingExtended:
    def test_escape_markdown_cell_none(self) -> None:
        assert escape_markdown_cell(None) == "—"

    def test_format_markdown_table_empty_headers(self) -> None:
        from chat_application.formatting import format_markdown_table

        assert format_markdown_table([], [["a"]]) == ""

    def test_coerce_numeric_amount_invalid(self) -> None:
        assert coerce_numeric_amount("not-a-number") is None
        assert coerce_numeric_amount({}) is None

    def test_format_money_amount_without_currency(self) -> None:
        assert format_money_amount(1234.5) == "1,234.50"

    def test_format_usd_compact_billion(self) -> None:
        assert format_usd_compact(2_500_000_000) == "$2.5 billion"

    def test_format_usd_compact_thousands(self) -> None:
        assert format_usd_compact(12_345) == "$12,345"

    def test_format_usd_compact_small_decimal(self) -> None:
        assert format_usd_compact(12.34) == "$12.34"

    def test_humanize_policy_basis_list(self) -> None:
        basis = humanize_policy_basis(["amount 1000000 within subject and absolute limits"])
        assert "$1 million" in basis[0]

    def test_humanize_authorization_text_empty(self) -> None:
        assert humanize_authorization_text("") == ""

    def test_format_policy_basis_cell_empty(self) -> None:
        assert format_policy_basis_cell(None) == "—"

    def test_format_eligible_approvers_section_empty(self) -> None:
        text = format_eligible_approvers_section(
            header="Header",
            section_title="Approvers",
            eligible=[],
            empty_message="No approvers.",
            candidate_role_label="FUNDING_APPROVER",
        )
        assert "No approvers." in text

    def test_format_eligible_approvers_section_with_candidates(self) -> None:
        text = format_eligible_approvers_section(
            header="Header",
            section_title="Approvers",
            eligible=[
                {
                    "display_name": "Bob Jones",
                    "title": "MD",
                    "allow_basis": ["role FUNDING_APPROVER"],
                }
            ],
            empty_message="No approvers.",
            candidate_role_label="FUNDING_APPROVER",
            candidates_evaluated=3,
        )
        assert "Bob Jones" in text
        assert "Evaluated 3" in text


class TestNeo4jFormatters:
    def test_instruction_creator_by_id_empty(self) -> None:
        assert "No instruction" in format_instruction_creator_by_id("q", [])

    def test_instruction_creator_by_id_unknown_creator(self) -> None:
        text = format_instruction_creator_by_id(
            "q",
            [{"instruction_id": "i1", "creator_display": "unknown"}],
        )
        assert "No creator is recorded" in text

    def test_instruction_creator_by_id_success(self) -> None:
        text = format_instruction_creator_by_id(
            "q",
            [{"instruction_id": "i1", "creator_display": "Alice Smith"}],
        )
        assert "Alice Smith" in text

    def test_instruction_status_by_id(self) -> None:
        text = format_instruction_status_by_id(
            "q",
            [{"instruction_id": "i1", "status": "APPROVED", "owning_lob": "FICC"}],
        )
        assert "APPROVED" in text
        assert "FICC" in text

    def test_instruction_creator_and_approver_by_id(self) -> None:
        text = format_instruction_creator_and_approver_by_id(
            "q",
            [
                {
                    "instruction_id": "i1",
                    "creator_display": "Alice",
                    "approver_display": "Bob",
                    "approved_at": "2025-01-01",
                }
            ],
        )
        assert "Alice" in text
        assert "Bob" in text
        assert "Approved at" in text

    def test_instruction_inventory_table(self) -> None:
        text = format_instruction_inventory_table(
            "q",
            [{"instruction_id": "i1", "status": "DRAFT", "owning_lob": "FICC"}],
        )
        assert "Found 1 instruction" in text

    def test_instruction_approver_by_id(self) -> None:
        text = format_instruction_approver_by_id(
            "q",
            [
                {
                    "approver_display": "Bob",
                    "approved_at": "2025-01-01",
                    "authorization_summary": "amount 1000000 within subject and absolute limits",
                }
            ],
        )
        assert "Bob" in text
        assert "$1 million" in text

    def test_instruction_approver_by_id_includes_basis(self) -> None:
        text = format_instruction_approver_by_id(
            "q",
            [
                {
                    "approver_display": "Vasquez, Elena (ficc-300)",
                    "approved_at": "2026-07-04T12:29:42.385807",
                    "authorization_basis": [
                        "amount 1000000 within subject and absolute limits",
                        "role FICC_SUPERVISOR",
                    ],
                }
            ],
        )
        assert "WHO: Vasquez, Elena (ficc-300)" in text
        assert "WHEN: 2026-07-04T12:29:42.385807" in text
        assert "BASIS:" in text
        assert "WHY:" not in text
        assert "FICC_SUPERVISOR" in text
        assert "$1 million" in text

    def test_instruction_approver_by_id_skips_redundant_basis(self) -> None:
        summary = (
            "Vasquez, Elena (ficc-300) was allowed to APPROVE because "
            "role FICC_SUPERVISOR; valid transition for status SUBMITTED"
        )
        text = format_instruction_approver_by_id(
            "q",
            [
                {
                    "approver_display": "Vasquez, Elena (ficc-300)",
                    "approved_at": "2026-07-04T12:29:42.385807",
                    "authorization_summary": summary,
                    "authorization_basis": [
                        "role FICC_SUPERVISOR",
                        "valid transition for status SUBMITTED",
                    ],
                }
            ],
        )
        assert "WHY:" in text
        assert "BASIS:" not in text

    def test_payment_approver_not_approved_with_status(self) -> None:
        from chat_application.formatting.neo4j import format_payment_approver_by_id

        text = format_payment_approver_by_id(
            "Who approved 20260720-FICC-P-19?",
            [
                {
                    "payment_id": "20260720-FICC-P-19",
                    "status": "CANCELLED",
                    "has_approval": False,
                    "approver_display": "",
                }
            ],
        )
        assert text == (
            "Payment 20260720-FICC-P-19 was not approved. Its status is CANCELLED."
        )

    def test_payment_approver_has_approval_false_but_approver_present(self) -> None:
        from chat_application.formatting.neo4j import format_payment_approver_by_id

        text = format_payment_approver_by_id(
            "Who approved payment 20260720-FICC-P-1 and why?",
            [
                {
                    "payment_id": "20260720-FICC-P-1",
                    "status": "APPROVED",
                    "has_approval": False,
                    "approver_display": "Laurent, Sophie (pay-201)",
                    "approved_at": "2026-07-20T01:19:04.508813Z",
                    "authorization_summary": (
                        "Laurent, Sophie (pay-201) was allowed to APPROVE "
                        "because role FUNDING_APPROVER"
                    ),
                }
            ],
        )
        assert "WHO: Laurent, Sophie (pay-201)" in text
        assert "was not approved" not in text
        assert "FUNDING_APPROVER" in text

    def test_instruction_mutual_approval_table(self) -> None:
        text = format_instruction_mutual_approval(
            "q",
            [{"user_a_display": "A", "user_b_display": "B", "approved_by_a": "X", "approved_by_b": "Y"}],
        )
        assert "mutual approval" in text
        assert "B created, A approved" in text
        assert "A created, B approved" in text

    def test_instruction_compliance_table_with_approver(self) -> None:
        text = format_instruction_compliance_table(
            "q",
            [{"instruction_id": "i1", "creator_display": "Alice", "approver_display": "Bob"}],
        )
        assert "Approver" in text

    def test_instruction_compliance_table_creator_only(self) -> None:
        text = format_instruction_compliance_table(
            "q",
            [{"instruction_id": "i1", "creator_display": "Alice"}],
        )
        assert "Creator" in text
        assert "Approver" not in text.split("\n")[0]

    def test_instruction_conflict_table(self) -> None:
        text = format_instruction_conflict_table(
            "q",
            [{"instruction_id_a": "a", "instruction_id_b": "b", "owning_lob": "FICC"}],
        )
        assert "conflicting instruction pair" in text

    def test_security_event_timeline_dedupes(self) -> None:
        text = format_security_event_timeline(
            "q",
            [
                {"event_id": "e1", "timestamp": "2025-01-02", "action": "CREATE"},
                {"event_id": "e1", "timestamp": "2025-01-02", "action": "CREATE"},
            ],
        )
        assert "1 event" in text

    def test_alert_count_today_singular_and_plural(self) -> None:
        assert "1 ALERT event" in format_alert_count_today("q", [{"total": 1}])
        assert "5 ALERT events" in format_alert_count_today("q", [{"total": 5}])

    def test_security_event_alert_list_table(self) -> None:
        text = format_security_event_alert_list(
            "summarize all alerts",
            [
                {
                    "event_id": "evt-1",
                    "timestamp": "2026-07-04T10:00:00Z",
                    "entity_type": "instruction",
                    "entity_id": "20260704-FICC-I-1",
                    "actor_display": "Chen, Sarah (mo-100)",
                    "action": "APPROVE",
                }
            ],
        )
        assert "evt-1" in text
        assert "Event ID" in text
        assert "Entity Type" in text
        assert "Entity ID" in text
        assert "20260704-FICC-I-1" in text
        assert "mo-100" in text

    def test_security_event_alert_list_missing_entity_id_shows_em_dash(self) -> None:
        text = format_security_event_alert_list(
            "report all alerts today",
            [
                {
                    "event_id": "evt-missing",
                    "timestamp": "2026-07-14T10:00:00Z",
                    "entity_type": "instruction",
                    "entity_id": "",
                    "actor_display": "Torres, Michael (ficc-201)",
                    "action": "CREATE",
                }
            ],
        )
        assert "evt-missing" in text
        assert "| — |" in text or " — " in text
    def test_formatters_registry(self) -> None:
        assert "instruction_creator_by_id" in FORMATTERS
        assert "instruction_detail_by_id" in FORMATTERS
        assert "instruction_versions_table" in FORMATTERS
        assert FORMATTERS["alert_count_today"] is format_alert_count_today

    def test_instruction_versions_table(self) -> None:
        from chat_application.formatting.neo4j import format_instruction_versions_table

        text = format_instruction_versions_table(
            "list all versions",
            [
                {
                    "instruction_id": "20260704-DESK_RATES-I-84",
                    "version_number": 1,
                    "status": "DRAFT",
                    "action": "CREATE",
                    "created_at": "2026-07-04T10:00:00Z",
                    "creator_display": "Patel, James (mo-101)",
                    "approver_display": "",
                },
                {
                    "instruction_id": "20260704-DESK_RATES-I-84",
                    "version_number": 3,
                    "status": "APPROVED",
                    "action": "APPROVE",
                    "created_at": "2026-07-04T23:40:00Z",
                    "creator_display": "Patel, James (mo-101)",
                    "approver_display": "Johansson, Nina (rates-201)",
                },
            ],
        )
        assert text is not None
        assert "versions (2)" in text
        assert "DRAFT" in text
        assert "APPROVED" in text
        assert "Ver" in text


class TestMultimodalIds:
    def test_document_ids_are_deterministic(self) -> None:
        from chat_application.vector.document_ids import (
            event_document_id,
            instruction_document_id,
            payment_document_id,
        )

        assert event_document_id("evt-1") == event_document_id("evt-1")
        assert instruction_document_id("i1") != payment_document_id("p1")


class TestPrompts:
    def test_answer_system_prompt_modes(self) -> None:
        from chat_application.gemini.prompts import answer_system_prompt

        assert "payment" in answer_system_prompt("payments").lower()
        assert "instruction" in answer_system_prompt("instructions").lower()
        assert answer_system_prompt("events") == answer_system_prompt("unknown")
