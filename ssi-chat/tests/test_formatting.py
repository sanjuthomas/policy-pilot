from __future__ import annotations

from chat_application.formatting import (
    format_approval_auth_lines,
    format_identity_token,
    format_identity_tokens_in_text,
    format_markdown_table,
    format_money_amount,
    format_policy_violations,
    format_usd_compact,
    humanize_policy_basis_point,
)


class TestFormatMarkdownTable:
    def test_renders_headers_and_rows(self) -> None:
        table = format_markdown_table(
            ["Payment ID", "Status", "Amount"],
            [
                ["pay-1", "APPROVED", "1,000.00 USD"],
                ["pay-2", "SUBMITTED", "500.00 USD"],
            ],
        )
        assert "| Payment ID | Status    | Amount       |" in table
        assert "| pay-1      | APPROVED  | 1,000.00 USD |" in table
        assert "| pay-2      | SUBMITTED | 500.00 USD   |" in table

    def test_empty_rows(self) -> None:
        assert format_markdown_table(["A"], []) == "_No rows._"

    def test_escapes_pipe_characters(self) -> None:
        table = format_markdown_table(["Name"], [["a|b"]])
        assert "a\\|b" in table

    def test_short_header_uses_gfm_separator(self) -> None:
        table = format_markdown_table(["#", "Policy check"], [[1, "role FUNDING_APPROVER"]])
        lines = table.split("\n")
        assert len(lines) == 3
        assert "---" in lines[1]
        assert lines[1].count("-") >= 6


class TestMoneyFormatting:
    def test_format_money_amount_currency_first(self) -> None:
        assert format_money_amount(1_000_000, "USD") == "USD 1,000,000.00"

    def test_format_money_amount_suffix(self) -> None:
        assert format_money_amount(1_000_000, "USD", currency_first=False) == "1,000,000.00 USD"

    def test_format_money_amount_from_scientific_string(self) -> None:
        assert format_money_amount("1e+06", "USD") == "USD 1,000,000.00"

    def test_humanize_basis_scientific_amount(self) -> None:
        point = humanize_policy_basis_point(
            "amount 1e+06 within subject and absolute limits"
        )
        assert point == "amount $1 million within subject and absolute limits"
        assert "1e+06" not in point

    def test_format_usd_compact(self) -> None:
        assert format_usd_compact(1_000_000) == "$1 million"


class TestFormatApprovalAuthLines:
    def test_basis_only_uses_basis_line(self) -> None:
        lines = format_approval_auth_lines(
            summary=None,
            basis=["role FICC_SUPERVISOR"],
        )
        assert lines == ["BASIS: role FICC_SUPERVISOR"]

    def test_summary_and_redundant_basis_uses_why_only(self) -> None:
        summary = (
            "Vasquez was allowed to APPROVE because role FICC_SUPERVISOR; "
            "valid transition for status SUBMITTED"
        )
        basis = ["role FICC_SUPERVISOR", "valid transition for status SUBMITTED"]
        lines = format_approval_auth_lines(summary=summary, basis=basis)
        assert len(lines) == 1
        assert lines[0].startswith("WHY:")
        assert "BASIS:" not in lines[0]


class TestFormatPolicyViolations:
    def test_backticks_preserve_alert_underscores_in_markdown(self) -> None:
        formatted = format_policy_violations(["ALERT_UNAPPROVED_INSTRUCTION"])
        assert formatted == "`ALERT_UNAPPROVED_INSTRUCTION`"

    def test_joins_multiple_codes(self) -> None:
        assert format_policy_violations(["SELF_APPROVAL", "LOB_MISMATCH"]) == (
            "`SELF_APPROVAL`; `LOB_MISMATCH`"
        )

    def test_empty_falls_back(self) -> None:
        assert format_policy_violations([]) == "policy denied"
        assert format_policy_violations(None) == "policy denied"


class TestFormatIdentityTokens:
    def test_wraps_role_group_club(self) -> None:
        assert format_identity_token("FUNDING_APPROVER") == "`FUNDING_APPROVER`"
        assert format_identity_token("MIDDLE_OFFICE") == "`MIDDLE_OFFICE`"
        assert format_identity_token("UP_TO_1_BILLION_CLUB") == "`UP_TO_1_BILLION_CLUB`"

    def test_leaves_plain_lob_and_prose(self) -> None:
        assert format_identity_token("FICC") == "FICC"
        assert format_identity_token("instruction owning LOB") == "instruction owning LOB"

    def test_does_not_double_wrap(self) -> None:
        assert format_identity_token("`FUNDING_APPROVER`") == "`FUNDING_APPROVER`"

    def test_protects_prose_from_markdown_italics(self) -> None:
        prose = (
            "Someone with the FUNDING_APPROVER role, who belongs to the "
            "MIDDLE_OFFICE group and an amount-limit club"
        )
        formatted = format_identity_tokens_in_text(prose)
        assert "`FUNDING_APPROVER`" in formatted
        assert "`MIDDLE_OFFICE`" in formatted
        # Already-backticked tokens stay single-wrapped.
        assert format_identity_tokens_in_text("role `FUNDING_APPROVER` ok") == (
            "role `FUNDING_APPROVER` ok"
        )
