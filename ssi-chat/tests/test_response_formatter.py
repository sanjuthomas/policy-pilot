from __future__ import annotations

from chat_application.formatting import format_markdown_table
from chat_application.formatting.response import (
    format_chat_response,
    has_markdown_table,
    parse_key_value_record,
    records_to_markdown_table,
)

STANDING_INSTRUCTIONS_ANSWER = """1. instruction_id=20260628-FICC-I-1, owning_lob=FICC, status=APPROVED, instruction_type=STANDING, currency=USD, wire_scope=DOMESTIC, creditor=Counterparty LLC, creator=Walsh, Patricia (mo-010), effective=2026-06-28T00:00:00, end=2027-06-28T00:00:00, approver=Nguyen, Caroline (ficc-500), approved_at=2026-06-28T13:53:16.560562
2. instruction_id=20260628-FICC-I-12, owning_lob=FICC, status=APPROVED, instruction_type=STANDING, currency=USD, wire_scope=DOMESTIC, creditor=Counterparty LLC, creator=Chen, Sarah (mo-100), effective=2026-06-28T00:00:00, end=2027-06-28T00:00:00, approver=Vasquez, Elena (ficc-300), approved_at=2026-06-28T13:53:26.070029"""


class TestParseKeyValueRecord:
    def test_parses_commas_inside_display_names(self) -> None:
        record = parse_key_value_record(
            "creator=Walsh, Patricia (mo-010), status=APPROVED, approver=Nguyen, Caroline (ficc-500)"
        )
        assert record["creator"] == "Walsh, Patricia (mo-010)"
        assert record["status"] == "APPROVED"
        assert record["approver"] == "Nguyen, Caroline (ficc-500)"

    def test_parses_colon_separated_fields(self) -> None:
        record = parse_key_value_record(
            "instruction_id: 20260717-FICC-I-19, owning_lob: FICC, status: APPROVED, "
            "effective: 2026-07-17T00:00:00"
        )
        assert record["instruction_id"] == "20260717-FICC-I-19"
        assert record["owning_lob"] == "FICC"
        assert record["status"] == "APPROVED"
        assert record["effective"] == "2026-07-17T00:00:00"

    def test_parses_markdown_bold_colon_fields(self) -> None:
        record = parse_key_value_record(
            "**instruction_id:** 20260717-FICC-I-3, **owning_lob:** FICC, **status:** APPROVED"
        )
        assert record["instruction_id"] == "20260717-FICC-I-3"
        assert record["owning_lob"] == "FICC"
        assert record["status"] == "APPROVED"

    def test_does_not_mid_match_title_case_labels(self) -> None:
        """Downvote: Title:/Roles: must not become Itle/Oles via mid-word match."""
        assert parse_key_value_record("Title: Vice President") == {}
        assert parse_key_value_record("- **Title:** Vice President") == {}
        assert parse_key_value_record("- **Roles:** FUNDING_APPROVER") == {}
        assert parse_key_value_record("- **Groups:** MIDDLE_OFFICE") == {}
        assert parse_key_value_record("- **Supervisor:** mo-010") == {}
        assert parse_key_value_record("- **LOB:** FICC") == {}


class TestFormatChatResponse:
    def test_formats_numbered_instruction_list_as_table(self) -> None:
        formatted = format_chat_response(STANDING_INSTRUCTIONS_ANSWER)

        assert "| Instruction ID" in formatted
        assert "| LOB" in formatted
        assert "| Status" in formatted
        assert "20260628-FICC-I-1" in formatted
        assert "20260628-FICC-I-12" in formatted
        assert "Walsh, Patricia (mo-010)" in formatted
        assert "Vasquez, Elena (ficc-300)" in formatted
        assert "instruction_id=" not in formatted

    def test_preserves_intro_and_footer(self) -> None:
        text = (
            "Found 2 STANDING instructions for FICC:\n\n"
            f"{STANDING_INSTRUCTIONS_ANSWER}\n\n"
            "All are domestic USD wires."
        )
        formatted = format_chat_response(text)

        assert formatted.startswith("Found 2 STANDING instructions for FICC:")
        assert "| Instruction ID" in formatted
        assert formatted.endswith("All are domestic USD wires.")

    def test_leaves_who_am_i_title_case_bullets_unchanged(self) -> None:
        text = (
            "Here is your identity:\n\n"
            "- **Title:** Vice President\n"
            "- **Roles:** FUNDING_APPROVER\n"
            "- **Groups:** MIDDLE_OFFICE\n"
            "- **LOB:** FICC\n"
            "- **Supervisor:** mo-010"
        )
        assert format_chat_response(text) == text
        assert "Itle" not in format_chat_response(text)
        assert "Oles" not in format_chat_response(text)

    def test_leaves_who_when_why_answers_unchanged(self) -> None:
        text = (
            "WHO: Vasquez, Elena (ficc-300)\n"
            "WHEN: 2026-06-28T13:53:26.070029\n"
            "WHY: Approved as FICC supervisor."
        )
        assert format_chat_response(text) == text

    def test_leaves_existing_markdown_tables_unchanged(self) -> None:
        table = format_markdown_table(
            ["Payment ID", "Status"],
            [["pay-1", "APPROVED"]],
        )
        text = f"Payments:\n\n{table}"
        assert format_chat_response(text) == text

    def test_leaves_plain_prose_unchanged(self) -> None:
        text = "No such cases were found in the graph."
        assert format_chat_response(text) == text

    def test_formats_plain_key_value_lines(self) -> None:
        text = (
            "instruction_id=20260628-FICC-I-1, status=APPROVED, owning_lob=FICC\n"
            "instruction_id=20260628-FICC-I-12, status=APPROVED, owning_lob=FICC"
        )
        formatted = format_chat_response(text)
        assert "| Instruction ID" in formatted
        assert "20260628-FICC-I-1" in formatted
        assert "20260628-FICC-I-12" in formatted

    def test_formats_gemini_bold_colon_numbered_list(self) -> None:
        """Downvote shape: Gemini emits **field:** value in a numbered inventory."""
        text = (
            "Yes, there are 2 approved instructions in the system:\n\n"
            "1.  **instruction_id:** 20260717-DESK_RATES-I-1, **owning_lob:** DESK_RATES, "
            "**status:** APPROVED, **currency:** USD, **wire_scope:** DOMESTIC, "
            "**instruction_type:** SINGLE_USE\n"
            "2.  **instruction_id:** 20260717-FICC-I-3, **owning_lob:** FICC, "
            "**status:** APPROVED, **currency:** USD, **wire_scope:** DOMESTIC, "
            "**instruction_type:** SINGLE_USE"
        )
        formatted = format_chat_response(text)

        assert formatted.startswith("Yes, there are 2 approved instructions in the system:")
        assert "| Instruction ID" in formatted
        assert "| LOB" in formatted
        assert "20260717-DESK_RATES-I-1" in formatted
        assert "20260717-FICC-I-3" in formatted
        assert "instruction_id:" not in formatted
        assert "**" not in formatted

    def test_formats_gemini_colon_instruction_detail(self) -> None:
        """Single instruction detail becomes a vertical Field/Value card, not a wide row."""
        text = (
            "Instruction:\n"
            "instruction_id: 20260717-FICC-I-19, owning_lob: FICC, status: APPROVED, "
            "currency: USD, wire_scope: DOMESTIC, creditor: None, "
            "creator: Okonkwo, David (mo-050), effective: 2026-07-17T00:00:00, "
            "end: 2027-07-17T00:00:00\n"
            "approver: Nguyen, Caroline (ficc-500)"
        )
        formatted = format_chat_response(text)

        assert formatted.startswith("Instruction:")
        assert "| Field" in formatted
        assert "| Value" in formatted
        assert "Instruction ID" in formatted
        assert "20260717-FICC-I-19" in formatted
        assert "Okonkwo, David (mo-050)" in formatted
        assert "Nguyen, Caroline (ficc-500)" in formatted
        assert "instruction_id:" not in formatted
        # Must not be a one-row mega-table with entity columns across the header.
        assert not formatted.splitlines()[1].startswith("| Instruction ID")

    def test_formats_gemini_per_line_instruction_detail(self) -> None:
        """Upvote shape: one snake_case field per line → vertical Field/Value card."""
        text = (
            "instruction_id: 20260717-FICC-I-19\n"
            "owning_lob: FICC\n"
            "status: APPROVED\n"
            "instruction_type: STANDING\n"
            "currency: USD\n"
            "wire_scope: DOMESTIC\n"
            "creditor: None\n"
            "creator: Okonkwo, David (mo-050)\n"
            "approver: Nguyen, Caroline (ficc-500)\n"
            "approved_at: 2026-07-17T10:00:00\n"
            "effective_date: 2026-07-17T00:00:00\n"
            "end_date: 2027-07-17T00:00:00"
        )
        formatted = format_chat_response(text)

        assert "| Field" in formatted
        assert "| Value" in formatted
        assert "Instruction ID" in formatted
        assert "20260717-FICC-I-19" in formatted
        assert "STANDING" in formatted
        assert "instruction_id:" not in formatted


class TestHasMarkdownTable:
    def test_detects_gfm_table(self) -> None:
        table = format_markdown_table(["A"], [["1"]])
        assert has_markdown_table(table) is True

    def test_false_for_key_value_list(self) -> None:
        assert has_markdown_table(STANDING_INSTRUCTIONS_ANSWER) is False


class TestRecordsToMarkdownTable:
    def test_orders_instruction_columns_for_multi_record(self) -> None:
        table = records_to_markdown_table(
            [
                {
                    "status": "APPROVED",
                    "instruction_id": "20260628-FICC-I-1",
                    "owning_lob": "FICC",
                },
                {
                    "status": "DRAFT",
                    "instruction_id": "20260628-FICC-I-2",
                    "owning_lob": "FICC",
                },
            ]
        )
        header_line = table.splitlines()[0]
        assert header_line.index("Instruction ID") < header_line.index("LOB")
        assert header_line.index("LOB") < header_line.index("Status")

    def test_single_record_uses_vertical_field_value_card(self) -> None:
        table = records_to_markdown_table(
            [
                {
                    "status": "APPROVED",
                    "instruction_id": "20260628-FICC-I-1",
                    "owning_lob": "FICC",
                }
            ]
        )
        assert "| Field" in table.splitlines()[0]
        assert "Value" in table.splitlines()[0]
        assert table.startswith("| Field")
        assert "Instruction ID" in table
        assert "20260628-FICC-I-1" in table
        assert "FICC" in table
