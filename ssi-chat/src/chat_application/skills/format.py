from __future__ import annotations

from typing import Any

from chat_application.skills.models import ConfirmationCard


def _party_name(party: dict[str, Any] | None) -> str:
    if not party:
        return "—"
    return str(party.get("name") or "—")


def _account_id(account: dict[str, Any] | None) -> str:
    if not account:
        return "—"
    scheme = account.get("identification_scheme") or ""
    ident = account.get("identification") or "—"
    if scheme:
        return f"{scheme}:{ident}"
    return str(ident)


def _intermediary_lines(instruction: dict[str, Any]) -> list[str]:
    hops = instruction.get("intermediary_agents") or []
    lines: list[str] = []
    for index, hop in enumerate(hops, start=1):
        agent = (hop or {}).get("agent") or {}
        fi = agent.get("financial_institution") or agent
        name = fi.get("name") or agent.get("name") or f"Intermediary {index}"
        bic = fi.get("identification") or fi.get("bic") or ""
        account = _account_id((hop or {}).get("account"))
        if bic:
            lines.append(f"{index}. {name} ({bic}) — acct {account}")
        else:
            lines.append(f"{index}. {name} — acct {account}")
    return lines


def confirmation_card_from_instruction(
    instruction: dict[str, Any],
    *,
    amount: float,
    value_date: str,
) -> ConfirmationCard:
    return ConfirmationCard(
        instruction_id=str(instruction.get("instruction_id") or ""),
        amount=amount,
        currency=str(instruction.get("currency") or ""),
        value_date=value_date,
        owning_lob=str(instruction.get("owning_lob") or ""),
        instruction_status=str(instruction.get("status") or ""),
        debtor_name=_party_name(instruction.get("debtor")),
        debtor_account=_account_id(instruction.get("debtor_account")),
        creditor_name=_party_name(instruction.get("creditor")),
        creditor_account=_account_id(instruction.get("creditor_account")),
        intermediaries=_intermediary_lines(instruction),
    )


def format_amount(amount: float, currency: str) -> str:
    if amount >= 1_000_000 and amount == int(amount):
        return f"{currency} {amount:,.0f}"
    return f"{currency} {amount:,.2f}"


def format_created_payment_report(
    payment: dict[str, Any],
    *,
    card: ConfirmationCard,
    approvers_section: str | None,
) -> str:
    payment_id = payment.get("payment_id") or "—"
    lines = [
        "### Payment created (DRAFT)",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Payment id | `{payment_id}` |",
        f"| Instruction | `{card.instruction_id}` |",
        f"| Value date | {card.value_date} |",
        f"| Amount | {format_amount(float(payment.get('amount') or card.amount), str(payment.get('currency') or card.currency))} |",
        f"| Owning LOB | **{payment.get('owning_lob') or card.owning_lob}** |",
        f"| Status | {payment.get('status') or 'DRAFT'} |",
        "",
    ]
    if approvers_section:
        lines.extend([approvers_section, ""])
    else:
        lines.extend(
            [
                "I couldn't load eligible approvers automatically. "
                f"Ask: “Who can approve payment {payment_id}?” "
                "(compliance users get the live eligibility path).",
                "",
            ]
        )
    return "\n".join(lines)
