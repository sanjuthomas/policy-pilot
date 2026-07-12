from __future__ import annotations

import re
from datetime import date, timedelta

from chat_application.cypher import extract_entity_ids, extract_instruction_ids
from chat_application.skills.models import CreatePaymentParams

_CREATE_PAYMENT = re.compile(
    r"\b("
    r"(please\s+)?(create|draft)\s+(a\s+)?payment|"
    r"can\s+you\s+create\s+(a\s+)?payment|"
    r"would\s+you\s+create\s+(a\s+)?payment|"
    r"create\s+me\s+(a\s+)?payment"
    r")\b",
    re.IGNORECASE,
)

_CAPABILITY_ONLY = re.compile(
    r"^\s*(can|may|do)\s+i\b|"
    r"^\s*am\s+i\s+(allowed|able|permitted)\b|"
    r"\b(permission|allowed)\s+to\s+create\b",
    re.IGNORECASE,
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
        # Prefer later matches (usually the explicit amount clause).
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

    # Soft fallbacks when value-date wording is loose but day is explicit.
    if re.search(r"\btomorrow\b", message, re.IGNORECASE):
        return (date.today() + timedelta(days=1)).isoformat()
    if re.search(r"\btoday\b", message, re.IGNORECASE):
        return date.today().isoformat()
    return None


def _pick_instruction_id(message: str) -> str | None:
    ids = extract_instruction_ids(message)
    if ids:
        return ids[0]
    # Fall back to generic entity ids that look like instruction sequence ids.
    for entity_id in extract_entity_ids(message):
        if re.search(r"-I-\d+$", entity_id, re.IGNORECASE) or "instruction" in message.lower():
            return entity_id
    return None


def detect_create_payment_skill(message: str) -> CreatePaymentParams | None:
    """Detect an actionable create-payment skill (not a capability question)."""
    text = message.strip()
    if not text or not _CREATE_PAYMENT.search(text):
        return None
    # "Can I create a payment?" is a me-intent, not a mutation skill.
    if _CAPABILITY_ONLY.search(text) and "you" not in text.lower()[:40]:
        if not re.search(r"\binstruction\b", text, re.IGNORECASE):
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
        raw_message=text,
    )
