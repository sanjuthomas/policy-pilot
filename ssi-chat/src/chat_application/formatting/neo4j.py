"""Deterministic formatters for Neo4j-direct answers (no LLM synthesis)."""

from __future__ import annotations

from typing import Any, Callable

from cypher_builder.query_engine import is_approval_denial_alert_list_question

from chat_application.formatting.common import (
    format_approval_auth_lines,
    format_markdown_table,
    format_money_amount,
    parse_authorization_basis,
)

Formatter = Callable[[str, list[dict[str, Any]]], str | None]


def _first_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return rows[0] if rows else None


def format_instruction_creator_by_id(question: str, rows: list[dict[str, Any]]) -> str | None:
    row = _first_row(rows)
    if row is None:
        return "No instruction with that ID was found in the graph."
    instruction_id = row.get("instruction_id") or "unknown"
    creator = row.get("creator_display") or "unknown"
    if not creator or creator == "unknown":
        return f"No creator is recorded for instruction {instruction_id}."
    return f"Instruction {instruction_id} was created by {creator}."


def format_payment_creator_by_id(question: str, rows: list[dict[str, Any]]) -> str | None:
    row = _first_row(rows)
    if row is None:
        return "No payment with that ID was found in the graph."
    payment_id = row.get("payment_id") or "unknown"
    creator = row.get("creator_display") or "unknown"
    if not creator or creator == "unknown":
        return f"No creator is recorded for payment {payment_id}."
    return f"Payment {payment_id} was created by {creator}."


def format_payment_status_by_id(question: str, rows: list[dict[str, Any]]) -> str | None:
    row = _first_row(rows)
    if row is None:
        return "No payment with that ID was found in the graph."
    payment_id = row.get("payment_id") or "unknown"
    status = row.get("status") or "unknown"
    lob = row.get("owning_lob")
    suffix = f" (LOB {lob})" if lob else ""
    return f"Payment {payment_id} has status {status}{suffix}."


def format_payment_creator_and_approver_by_id(
    question: str, rows: list[dict[str, Any]]
) -> str | None:
    row = _first_row(rows)
    if row is None:
        return "No payment with that ID was found in the graph."
    payment_id = row.get("payment_id") or "unknown"
    creator = row.get("creator_display") or "—"
    approver = row.get("approver_display") or "—"
    lines = [
        f"Payment: {payment_id}",
        f"Creator: {creator}",
        f"Approver: {approver}",
    ]
    approved_at = row.get("approved_at")
    if approved_at:
        lines.append(f"Approved at: {approved_at}")
    return "\n".join(lines)


def _payment_amount_cell(row: dict[str, Any]) -> str:
    amount = row.get("amount")
    currency = row.get("currency")
    formatted = format_money_amount(amount, currency, currency_first=True)
    if formatted.endswith(".00") and currency:
        # Prefer USD 15,000,000 over USD 15,000,000.00 for whole amounts.
        return formatted[:-3]
    return formatted


def format_payment_detail_by_id(question: str, rows: list[dict[str, Any]]) -> str | None:
    """Full payment card for “show me payment …” style questions."""
    row = _first_row(rows)
    if row is None:
        return "No payment with that ID was found in the graph."

    payment_id = str(row.get("payment_id") or "—")
    instruction_id = str(row.get("instruction_id") or "—")
    status = str(row.get("status") or "—")
    creator = str(row.get("creator_display") or "—")
    approver = str(row.get("approver_display") or "").strip()
    if not approver:
        approver = "— (not yet approved)"

    table = format_markdown_table(
        ["Field", "Value"],
        [
            ["Payment id", f"`{payment_id}`"],
            ["Instruction", f"`{instruction_id}`"],
            ["Status", f"**{status}**"],
            ["Amount", f"**{_payment_amount_cell(row)}**"],
            ["Value date", str(row.get("value_date") or "—")],
            ["Owning LOB", f"**{row.get('owning_lob') or '—'}**"],
            ["Creator", creator],
            ["Approver", approver],
        ],
    )
    created_at = row.get("created_at")
    approved_at = row.get("approved_at")
    extra: list[str] = []
    if created_at:
        extra.append(f"Created at: {created_at}")
    if approved_at:
        extra.append(f"Approved at: {approved_at}")
    footer = ("\n\n" + "\n".join(extra)) if extra else ""
    return f"### Payment `{payment_id}`\n\n{table}{footer}"


def format_instruction_detail_by_id(question: str, rows: list[dict[str, Any]]) -> str | None:
    """Full instruction card for “show me instruction …” — CURRENT version only."""
    row = _first_row(rows)
    if row is None:
        return "No instruction with that ID was found in the graph."

    instruction_id = str(row.get("instruction_id") or "—")
    status = str(row.get("status") or "—")
    creator = str(row.get("creator_display") or "—").strip() or "—"
    approver = str(row.get("approver_display") or "").strip()
    if not approver:
        approver = "— (not yet approved)"

    creditor = str(row.get("creditor_name") or "").strip()
    if not creditor or creditor.lower() in {"none", "null"}:
        creditor = "—"
    account = str(row.get("creditor_account") or "").strip()
    if account and account.lower() not in {"none", "null"}:
        creditor = f"{creditor} (`{account}`)" if creditor != "—" else f"`{account}`"

    version = row.get("version_number")
    version_cell = str(version) if version is not None and str(version).strip() else "—"

    table = format_markdown_table(
        ["Field", "Value"],
        [
            ["Instruction id", f"`{instruction_id}`"],
            ["Status", f"**{status}**"],
            ["Type", str(row.get("instruction_type") or "—")],
            ["Owning LOB", f"**{row.get('owning_lob') or '—'}**"],
            ["Currency", str(row.get("currency") or "—")],
            ["Wire scope", str(row.get("wire_scope") or "—")],
            ["Creditor", creditor],
            ["Effective", str(row.get("effective_date") or "—")],
            ["End", str(row.get("end_date") or "—")],
            ["Current version", version_cell],
            ["Creator", creator],
            ["Approver", approver],
        ],
    )
    extra: list[str] = []
    created_at = row.get("created_at")
    approved_at = row.get("approved_at")
    if created_at:
        extra.append(f"Created at: {created_at}")
    if approved_at:
        extra.append(f"Approved at: {approved_at}")
    footer = ("\n\n" + "\n".join(extra)) if extra else ""
    return f"### Instruction `{instruction_id}`\n\n{table}{footer}"


def format_instruction_status_by_id(question: str, rows: list[dict[str, Any]]) -> str | None:
    row = _first_row(rows)
    if row is None:
        return "No instruction with that ID was found in the graph."
    instruction_id = row.get("instruction_id") or "unknown"
    status = row.get("status") or "unknown"
    lob = row.get("owning_lob")
    suffix = f" (LOB {lob})" if lob else ""
    return f"Instruction {instruction_id} has status {status}{suffix}."


def format_instruction_creator_and_approver_by_id(
    question: str, rows: list[dict[str, Any]]
) -> str | None:
    row = _first_row(rows)
    if row is None:
        return "No instruction with that ID was found in the graph."
    instruction_id = row.get("instruction_id") or "unknown"
    creator = row.get("creator_display") or "—"
    approver = row.get("approver_display") or "—"
    lines = [
        f"Instruction: {instruction_id}",
        f"Creator: {creator}",
        f"Approver: {approver}",
    ]
    approved_at = row.get("approved_at")
    if approved_at:
        lines.append(f"Approved at: {approved_at}")
    return "\n".join(lines)


def format_approval_lookup_answer(row: dict[str, Any], *, entity_noun: str = "payment") -> str:
    """WHO/WHEN/WHY for an approval, or a short not-approved status line."""
    payment_id = row.get("payment_id")
    instruction_id = row.get("instruction_id")
    if entity_noun == "instruction" or (instruction_id and not payment_id):
        noun = "instruction"
        entity_id = instruction_id or "unknown"
        display_noun = "Instruction"
    else:
        noun = "payment"
        entity_id = payment_id or "unknown"
        display_noun = "Payment"

    if not _row_has_approval(row):
        status = str(row.get("status") or "").strip()
        if status:
            return f"{display_noun} {entity_id} was not approved. Its status is {status}."
        return f"No approval record was found for that {noun} in the graph."

    approver = row.get("approver_display") or "unknown"
    when = row.get("approved_at") or row.get("v.approved_at")
    summary = row.get("v.authorization_summary") or row.get("authorization_summary")
    basis = parse_authorization_basis(
        row.get("v.authorization_basis") or row.get("authorization_basis")
    )
    lines = [f"WHO: {approver}"]
    if when:
        lines.append(f"WHEN: {when}")
    lines.extend(format_approval_auth_lines(summary=str(summary) if summary else None, basis=basis))
    return "\n".join(lines)


def _row_has_approval(row: dict[str, Any]) -> bool:
    flag = row.get("has_approval")
    if isinstance(flag, bool):
        return flag
    if flag is not None and str(flag).strip().lower() in {"true", "false"}:
        return str(flag).strip().lower() == "true"
    approver = str(row.get("approver_display") or "").strip()
    if not approver or approver.lower() in {"unknown", "—", "-", "none", "null"}:
        return False
    return True


def format_instruction_approver_by_id(question: str, rows: list[dict[str, Any]]) -> str | None:
    row = _first_row(rows)
    if row is None:
        return "No instruction with that ID was found in the graph."
    return format_approval_lookup_answer(row, entity_noun="instruction")


def format_payment_approver_by_id(question: str, rows: list[dict[str, Any]]) -> str | None:
    row = _first_row(rows)
    if row is None:
        return "No payment with that ID was found in the graph."
    return format_approval_lookup_answer(row, entity_noun="payment")


def format_instruction_inventory_table(question: str, rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return "No matching instructions were found in the graph."
    table_rows = [
        [
            row.get("instruction_id"),
            row.get("status") or "—",
            row.get("owning_lob") or "—",
            row.get("currency") or "—",
            row.get("creator_display") or "—",
            row.get("approver_display") or "—",
        ]
        for row in rows
    ]
    return (
        f"Found {len(table_rows)} instruction(s).\n\n"
        f"{format_markdown_table(['Instruction ID', 'Status', 'LOB', 'Currency', 'Creator', 'Approver'], table_rows)}"
    )


def format_cross_entity_reciprocal_approval(
    question: str, rows: list[dict[str, Any]]
) -> str | None:
    if not rows:
        return (
            "No cross-entity reciprocal approval cases were found in the graph "
            "(instruction approval in one direction and payment approval on the same "
            "instruction route in the other)."
        )
    table_rows = [
        [
            row.get("instruction_creator_display"),
            row.get("instruction_approver_display"),
            row.get("payment_creator_display"),
            row.get("payment_approver_display"),
            row.get("instruction_id"),
            row.get("payment_id"),
            row.get("owning_lob") or "—",
        ]
        for row in rows
    ]
    return (
        f"Found {len(table_rows)} cross-entity reciprocal approval case(s).\n\n"
        f"{format_markdown_table(
            [
                'Instruction creator',
                'Instruction approver',
                'Payment creator',
                'Payment approver',
                'Instruction ID',
                'Payment ID',
                'LOB',
            ],
            table_rows,
        )}"
    )


def format_instruction_mutual_approval(question: str, rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return "No mutual approval cases were found in the graph."
    table_rows = [
        [
            row.get("user_a_display"),
            row.get("user_b_display"),
            row.get("approved_by_a"),
            row.get("approved_by_b"),
        ]
        for row in rows
    ]
    return (
        f"Found {len(table_rows)} mutual approval case(s).\n\n"
        f"{format_markdown_table(
            ['User A', 'User B', 'B created, A approved', 'A created, B approved'],
            table_rows,
        )}"
    )


def format_instruction_compliance_table(question: str, rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return "No matching compliance cases were found in the graph."
    if rows[0].get("creator_display") and rows[0].get("approver_display"):
        table_rows = [
            [
                row.get("instruction_id"),
                row.get("owning_lob") or "—",
                row.get("status") or "—",
                row.get("creator_display") or "—",
                row.get("approver_display") or "—",
            ]
            for row in rows
        ]
        headers = ["Instruction ID", "LOB", "Status", "Creator", "Approver"]
    else:
        table_rows = [
            [
                row.get("instruction_id"),
                row.get("owning_lob") or "—",
                row.get("status") or "—",
                row.get("creator_display") or "—",
            ]
            for row in rows
        ]
        headers = ["Instruction ID", "LOB", "Status", "Creator"]
    return (
        f"Found {len(table_rows)} matching instruction(s).\n\n"
        f"{format_markdown_table(headers, table_rows)}"
    )


def format_instruction_conflict_table(question: str, rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return "No duplicate settlement routes (CONFLICTS_WITH) were found in the graph."
    table_rows = [
        [
            row.get("instruction_id_a"),
            row.get("instruction_id_b"),
            row.get("owning_lob") or "—",
            row.get("currency") or "—",
            row.get("creditor_account") or "—",
        ]
        for row in rows
    ]
    return (
        f"Found {len(table_rows)} conflicting instruction pair(s).\n\n"
        f"{format_markdown_table(['Instruction A', 'Instruction B', 'LOB', 'Currency', 'Creditor Account'], table_rows)}"
    )


def format_security_event_timeline(question: str, rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return "No security events were found for that instruction in the graph."
    deduped: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()
    for row in sorted(rows, key=lambda item: str(item.get("timestamp") or "")):
        event_id = str(row.get("event_id") or "")
        if event_id and event_id in seen_event_ids:
            continue
        if event_id:
            seen_event_ids.add(event_id)
        deduped.append(row)
    table_rows = [
        [
            row.get("timestamp") or "—",
            row.get("action") or "—",
            row.get("severity") or "—",
            row.get("outcome") or "—",
            row.get("actor_display") or "—",
            row.get("event_id") or "—",
        ]
        for row in deduped
    ]
    return (
        f"Security event timeline ({len(table_rows)} event(s)):\n\n"
        f"{format_markdown_table(['Timestamp', 'Action', 'Severity', 'Outcome', 'Actor', 'Event ID'], table_rows)}"
    )


def format_alert_count_today(question: str, rows: list[dict[str, Any]]) -> str | None:
    total = int(rows[0].get("total") or 0) if rows else 0
    if total == 1:
        return "There was 1 ALERT event today."
    return f"There were {total} ALERT events today."


def format_security_event_alert_list(question: str, rows: list[dict[str, Any]]) -> str | None:
    detail_rows = [row for row in rows if row.get("event_id")]
    if not detail_rows:
        if is_approval_denial_alert_list_question(question):
            return "No approval-denial ALERT security events were found in the graph."
        return "No ALERT security events were found in the graph."

    table_rows = [
        [
            row.get("event_id") or "—",
            row.get("timestamp") or "—",
            row.get("entity_type") or "—",
            row.get("entity_id") or "—",
            row.get("actor_display") or "—",
            row.get("action") or "—",
        ]
        for row in detail_rows
    ]
    title = (
        "Approval denial ALERT security events"
        if is_approval_denial_alert_list_question(question)
        else "ALERT security events"
    )
    return (
        f"{title} ({len(table_rows)}):\n\n"
        f"{format_markdown_table(['Event ID', 'Event Time', 'Entity Type', 'Entity ID', 'Actor', 'Action'], table_rows)}"
    )


def format_instructions_without_payments_table(
    question: str, rows: list[dict[str, Any]]
) -> str | None:
    if not rows:
        return "No instructions without payments were found in the graph."
    table_rows = [
        [
            row.get("instruction_id") or "—",
            row.get("status") or "—",
            row.get("owning_lob") or "—",
        ]
        for row in rows
    ]
    return (
        f"Instructions without payments ({len(table_rows)}):\n\n"
        f"{format_markdown_table(['Instruction ID', 'Status', 'LOB'], table_rows)}"
    )


def format_instruction_payment_counts_table(question: str, rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return "No instructions were found in the graph."
    table_rows = [
        [
            row.get("instruction_id") or "—",
            row.get("status") or "—",
            row.get("owning_lob") or "—",
            row.get("payment_count", 0),
        ]
        for row in rows
    ]
    return (
        f"Instruction payment counts ({len(table_rows)}):\n\n"
        f"{format_markdown_table(['Instruction ID', 'Status', 'LOB', 'Payments'], table_rows)}"
    )


def format_instruction_versions_table(question: str, rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return "No instruction versions were found in the graph."
    instruction_id = rows[0].get("instruction_id") or "unknown"
    table_rows = [
        [
            row.get("version_number") or "—",
            row.get("status") or "—",
            row.get("action") or "—",
            row.get("created_at") or "—",
            row.get("creator_display") or "—",
            row.get("approver_display") or "—",
        ]
        for row in rows
    ]
    return (
        f"Instruction {instruction_id} versions ({len(table_rows)}):\n\n"
        f"{format_markdown_table(['Ver', 'Status', 'Action', 'Created At', 'Creator', 'Approver'], table_rows)}"
    )


def format_payment_versions_table(question: str, rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return "No payment versions were found in the graph."
    payment_id = rows[0].get("payment_id") or "unknown"
    table_rows = [
        [
            row.get("version_number") or "—",
            row.get("status") or "—",
            row.get("action") or "—",
            row.get("amount") or "—",
            row.get("currency") or "—",
            row.get("created_at") or "—",
            row.get("creator_display") or "—",
            row.get("approver_display") or "—",
        ]
        for row in rows
    ]
    return (
        f"Payment {payment_id} versions ({len(table_rows)}):\n\n"
        f"{format_markdown_table(['Ver', 'Status', 'Action', 'Amount', 'Currency', 'Created At', 'Creator', 'Approver'], table_rows)}"
    )


FORMATTERS: dict[str, Formatter] = {
    "instruction_creator_by_id": format_instruction_creator_by_id,
    "instruction_status_by_id": format_instruction_status_by_id,
    "instruction_creator_and_approver_by_id": format_instruction_creator_and_approver_by_id,
    "instruction_approver_by_id": format_instruction_approver_by_id,
    "payment_approver_by_id": format_payment_approver_by_id,
    "payment_creator_by_id": format_payment_creator_by_id,
    "payment_status_by_id": format_payment_status_by_id,
    "payment_creator_and_approver_by_id": format_payment_creator_and_approver_by_id,
    "payment_detail_by_id": format_payment_detail_by_id,
    "instruction_detail_by_id": format_instruction_detail_by_id,
    "instruction_inventory_table": format_instruction_inventory_table,
    "instruction_mutual_approval": format_instruction_mutual_approval,
    "cross_entity_reciprocal_approval": format_cross_entity_reciprocal_approval,
    "instruction_compliance_table": format_instruction_compliance_table,
    "instruction_conflict_table": format_instruction_conflict_table,
    "security_event_timeline": format_security_event_timeline,
    "alert_count_today": format_alert_count_today,
    "security_event_alert_list": format_security_event_alert_list,
    "instruction_versions_table": format_instruction_versions_table,
    "payment_versions_table": format_payment_versions_table,
}
