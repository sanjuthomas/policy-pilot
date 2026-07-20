from __future__ import annotations

import json
import re
from typing import Any

_AMOUNT_IN_BASIS = re.compile(
    r"amount\s+([\d.eE+-]+)\s+(within subject and absolute limits)",
    re.IGNORECASE,
)

# Roles / groups / amount clubs (e.g. FUNDING_APPROVER, MIDDLE_OFFICE, UP_TO_1_BILLION_CLUB).
_IDENTITY_TOKEN = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
_CODE_SPAN = re.compile(r"`[^`]+`")
_CODE_SLOT = "\0IDCODE{index}\0"


def format_identity_token(name: str) -> str:
    """Wrap a role/group/club token in backticks for markdown-safe display."""
    token = str(name or "").strip()
    if not token:
        return token
    if token.startswith("`") and token.endswith("`") and token.count("`") == 2:
        return token
    if _IDENTITY_TOKEN.fullmatch(token):
        return f"`{token}`"
    return token


def format_identity_tokens_in_text(text: str) -> str:
    """Backtick SCREAMING_SNAKE identity tokens in prose without double-wrapping."""
    if not text:
        return text
    slots: list[str] = []

    def _protect(match: re.Match[str]) -> str:
        slots.append(match.group(0))
        return _CODE_SLOT.format(index=len(slots) - 1)

    protected = _CODE_SPAN.sub(_protect, text)
    wrapped = _IDENTITY_TOKEN.sub(lambda match: f"`{match.group(0)}`", protected)
    for index, snippet in enumerate(slots):
        wrapped = wrapped.replace(_CODE_SLOT.format(index=index), snippet)
    return wrapped


def escape_markdown_cell(value: Any) -> str:
    if value is None or value == "":
        text = "—"
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def format_markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    """Render a GitHub-flavored markdown table."""
    if not headers:
        return ""
    if not rows:
        return "_No rows._"

    str_headers = [escape_markdown_cell(header) for header in headers]
    str_rows = [[escape_markdown_cell(cell) for cell in row] for row in rows]

    widths = [len(header) for header in str_headers]
    for row in str_rows:
        for index, cell in enumerate(row):
            if index < len(widths):
                widths[index] = max(widths[index], len(cell))

    def format_line(cells: list[str]) -> str:
        parts: list[str] = []
        for index, cell in enumerate(cells):
            width = widths[index] if index < len(widths) else len(cell)
            parts.append(cell.ljust(width))
        return "| " + " | ".join(parts) + " |"

    separator = "| " + " | ".join("-" * max(3, width) for width in widths) + " |"
    body = "\n".join(format_line(row) for row in str_rows)
    return f"{format_line(str_headers)}\n{separator}\n{body}"


def coerce_numeric_amount(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def format_usd_compact(amount: float) -> str:
    """Format a USD amount in compact compliance-facing prose (e.g. $1 million)."""
    abs_amount = abs(amount)
    if abs_amount >= 1_000_000_000:
        value = abs_amount / 1_000_000_000
        if value.is_integer():
            return f"${int(value):,} billion"
        trimmed = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"${trimmed} billion"
    if abs_amount >= 1_000_000:
        value = abs_amount / 1_000_000
        if value.is_integer():
            return f"${int(value):,} million"
        trimmed = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"${trimmed} million"
    if abs_amount >= 1_000:
        return f"${abs_amount:,.0f}"
    if abs_amount.is_integer():
        return f"${int(abs_amount)}"
    return f"${abs_amount:,.2f}"


def format_money_amount(
    amount: Any,
    currency: str | None = None,
    *,
    currency_first: bool = True,
) -> str:
    """Format a monetary amount for display (handles scientific notation strings)."""
    value = coerce_numeric_amount(amount)
    if value is None:
        return "N/A"
    formatted = f"{value:,.2f}"
    if not currency:
        return formatted
    if currency_first:
        return f"{currency} {formatted}"
    return f"{formatted} {currency}"


def humanize_policy_basis_point(point: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        try:
            amount = float(match.group(1))
        except ValueError:
            return match.group(0)
        return f"amount {format_usd_compact(amount)} {match.group(2)}"

    return _AMOUNT_IN_BASIS.sub(_replace, point)


def humanize_policy_basis(basis: list[str]) -> list[str]:
    return [humanize_policy_basis_point(point) for point in basis]


def parse_authorization_basis(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item]
        except json.JSONDecodeError:
            pass
    return []


def format_approval_basis_line(basis: list[str]) -> str | None:
    if not basis:
        return None
    return f"BASIS: {' | '.join(humanize_policy_basis(basis))}"


def basis_redundant_with_summary(summary: str | None, basis: list[str]) -> bool:
    """True when every OPA allow_basis point is already present in the summary text."""
    if not summary or not basis:
        return False
    summary_lower = summary.lower()
    readable = humanize_policy_basis(basis)
    return all(point.lower() in summary_lower for point in readable)


def format_approval_auth_lines(
    *,
    summary: str | None,
    basis: list[str],
) -> list[str]:
    """Build WHY and/or BASIS lines without repeating the same OPA checks."""
    readable_summary = humanize_authorization_text(str(summary)) if summary else None
    readable_basis = humanize_policy_basis(basis) if basis else []
    redundant = basis_redundant_with_summary(readable_summary, basis)

    lines: list[str] = []
    if readable_summary:
        lines.append(f"WHY: {readable_summary}")
    elif readable_basis:
        basis_line = format_approval_basis_line(basis)
        if basis_line:
            lines.append(basis_line)

    if readable_basis and readable_summary and not redundant:
        basis_line = format_approval_basis_line(basis)
        if basis_line:
            lines.append(basis_line)

    return lines


def humanize_authorization_text(text: str) -> str:
    if not text:
        return text
    return _AMOUNT_IN_BASIS.sub(
        lambda match: humanize_policy_basis_point(match.group(0)),
        text,
    )


def format_policy_basis_cell(basis: list[str] | None) -> str:
    if not basis:
        return "—"
    return "; ".join(humanize_policy_basis_point(point) for point in basis)


def format_policy_violations(violations: list[str] | None) -> str:
    """Join violation codes for markdown answers without losing underscores.

    Chat renders answers as markdown; codes like ``ALERT_UNAPPROVED_INSTRUCTION``
    contain ``_token_`` segments that italicize and strip the underscores unless
    wrapped in backticks.
    """
    cleaned = [str(item).strip() for item in (violations or []) if str(item).strip()]
    if not cleaned:
        return "policy denied"
    return "; ".join(f"`{item}`" for item in cleaned)


def format_eligible_approvers_section(
    *,
    header: str,
    section_title: str,
    eligible: list[dict[str, Any]],
    empty_message: str,
    candidate_role_label: str,
    candidates_evaluated: int | None = None,
) -> str:
    if not eligible:
        return f"{header}\n\n{empty_message}"

    table_rows = [
        [
            index,
            row.get("display_name") or row.get("user_id") or "—",
            row.get("title") or "—",
            format_policy_basis_cell(row.get("allow_basis")),
        ]
        for index, row in enumerate(eligible, start=1)
    ]
    lines = [
        header,
        "",
        section_title,
        "",
        format_markdown_table(["#", "Approver", "Title", "Policy basis"], table_rows),
    ]
    if candidates_evaluated is not None:
        lines.extend(
            [
                "",
                f"Evaluated {candidates_evaluated} {candidate_role_label} candidate(s) from the user directory.",
            ]
        )
    return "\n".join(lines)
