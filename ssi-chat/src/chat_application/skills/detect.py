"""Create-payment slot parsing (not skill intent classification).

Whether to run the create-payment skill is decided by Gemini
(``RouterDecision.path=skill`` / ``skill=create_payment``), with a thin
heuristic only in ``pipeline/heuristic_strategy`` when the LLM router fails.

This module's job is **deterministic slot extraction** once that intent is
known: instruction id, amount (including k/m/b suffixes), and value date
(today/tomorrow/ISO). Those are structural fillers — the same class of
regex the project deliberately keeps for IDs, amounts, and dates — not a
growing phrase list for open-ended NLU.

``parse_create_payment_params`` returns ``None`` when required slots are
missing so the skill can ask for clarification or the fallback can
decline to claim create-payment. See docs/intent-determination.md and
docs/create-payment-skill.md.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from chat_application.graph.cypher import extract_entity_ids, extract_instruction_ids
from chat_application.skills.models import (
    ApprovePaymentParams,
    CreatePaymentParams,
    SubmitPaymentParams,
)

_AMOUNT = re.compile(
    r"(?:"
    r"amount\s*(?:of|=|:)?\s*"
    r"|for\s+"
    r")"
    r"\$?\s*([\d_,]+(?:\.\d+)?)\s*"
    r"(k|thousand|m|mm|million|b|bn|billion)?\b",
    re.IGNORECASE,
)

_AMOUNT_WITH_UNIT = re.compile(
    r"\$?\s*([\d_,]+(?:\.\d+)?)\s*"
    r"(k|thousand|m|mm|million|b|bn|billion)\b",
    re.IGNORECASE,
)

_VALUE_DATE_RELATIVE = re.compile(
    r"\b(?:value\s*date|valuedate|settle(?:ment)?\s*date)\b\s*(?:is|=|:)?\s*"
    r"(today|tomorrow)\b|"
    r"\b(today|tomorrow)\b.{0,24}\b(?:value\s*date|valuedate)\b",
    re.IGNORECASE,
)

_VALUE_DATE_ISO = re.compile(
    r"\b(?:value\s*date|valuedate)\s*(?:is|=|:)?\s*"
    r"(\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)


def _parse_amount(message: str) -> float | None:
    candidates: list[re.Match[str]] = list(_AMOUNT.finditer(message))
    candidates.extend(_AMOUNT_WITH_UNIT.finditer(message))
    if not candidates:
        return None

    def _score(match: re.Match[str]) -> tuple[int, int]:
        unit = (match.group(2) or "").lower()
        has_unit = 1 if unit else 0
        return (has_unit, match.start())

    chosen = max(candidates, key=_score)
    raw = chosen.group(1).replace(",", "").replace("_", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    unit = (chosen.group(2) or "").lower()
    if unit in {"k", "thousand"}:
        value *= 1_000
    elif unit in {"m", "mm", "million"}:
        value *= 1_000_000
    elif unit in {"b", "bn", "billion"}:
        value *= 1_000_000_000
    if value <= 0:
        return None
    return value


def _relative_day(token: str) -> date:
    token = token.lower()
    if token == "tomorrow":
        return date.today() + timedelta(days=1)
    return date.today()


def _parse_value_date(message: str) -> str | None:
    iso = _VALUE_DATE_ISO.search(message)
    if iso:
        return iso.group(1)

    relative = _VALUE_DATE_RELATIVE.search(message)
    if relative:
        token = relative.group(1) or relative.group(2)
        if token:
            return _relative_day(token).isoformat()

    if re.search(r"\btomorrow\b", message, re.IGNORECASE):
        return (date.today() + timedelta(days=1)).isoformat()
    if re.search(r"\btoday\b", message, re.IGNORECASE):
        return date.today().isoformat()
    return None


def _pick_instruction_id(message: str) -> str | None:
    ids = extract_instruction_ids(message)
    if ids:
        return ids[0]
    for entity_id in extract_entity_ids(message):
        if re.search(r"-I-\d+$", entity_id, re.IGNORECASE) or "instruction" in message.lower():
            return entity_id
    return None


def parse_create_payment_params(message: str) -> CreatePaymentParams | None:
    """Parse create-payment slots once intent is known (instruction, amount, value date)."""
    text = message.strip()
    if not text:
        return None

    instruction_id = _pick_instruction_id(text)
    if not instruction_id:
        return None

    amount = _parse_amount(text)
    value_date = _parse_value_date(text)
    if amount is None or value_date is None:
        return None

    return CreatePaymentParams(
        instruction_id=instruction_id,
        amount=amount,
        value_date=value_date,
    )


_PAYMENT_ID = re.compile(
    r"\b(\d{8}-[A-Za-z0-9_]+-P-\d+)\b",
)


def _pick_payment_id(message: str) -> str | None:
    match = _PAYMENT_ID.search(message)
    if match:
        return match.group(1)
    for entity_id in extract_entity_ids(message):
        if re.search(r"-P-\d+$", entity_id, re.IGNORECASE):
            return entity_id
    return None


def parse_submit_payment_params(message: str) -> SubmitPaymentParams | None:
    """Parse submit-payment slot once intent is known (payment id)."""
    text = message.strip()
    if not text:
        return None
    payment_id = _pick_payment_id(text)
    if not payment_id:
        return None
    return SubmitPaymentParams(payment_id=payment_id)


def parse_approve_payment_params(message: str) -> ApprovePaymentParams | None:
    """Parse approve-payment slot once intent is known (payment id)."""
    text = message.strip()
    if not text:
        return None
    payment_id = _pick_payment_id(text)
    if not payment_id:
        return None
    return ApprovePaymentParams(payment_id=payment_id)

