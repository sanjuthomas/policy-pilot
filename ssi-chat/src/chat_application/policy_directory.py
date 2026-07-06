from __future__ import annotations

import re

from chat_application.cypher import (
    extract_payment_ids,
    lob_filter_from_question,
    payment_amount_threshold_from_question,
)

_AMOUNT_CLUB_PATTERN = re.compile(
    r"\b(UP_TO_\d+_(?:MILLION|BILLION)_CLUB)\b",
    re.IGNORECASE,
)

_CLUB_CEILINGS: tuple[tuple[str, float], ...] = (
    ("UP_TO_100_MILLION_CLUB", 100_000_000.0),
    ("UP_TO_1_BILLION_CLUB", 1_000_000_000.0),
    ("UP_TO_100_BILLION_CLUB", 100_000_000_000.0),
)

ABSOLUTE_PAYMENT_LIMIT = 100_000_000_000.0


def is_payment_approval_directory_question(message: str) -> bool:
    """Policy directory lookup — who may approve by amount club (no specific payment id)."""
    if extract_payment_ids(message):
        return False
    lowered = message.lower()
    if "payment" not in lowered:
        return False
    if not re.search(r"\b(who|which\s+users?|list|members?)\b", lowered):
        return False
    if not re.search(
        r"\b(permission|authorized|authorize|eligible|approv\w*|members?|group|club)\b",
        lowered,
    ):
        return False
    if _AMOUNT_CLUB_PATTERN.search(message):
        return True
    if payment_amount_threshold_from_question(message) is not None:
        return True
    return bool(re.search(r"\bworth\b", lowered) and re.search(r"\b(million|billion|\$)\b", lowered))


def payment_approval_group_from_question(message: str) -> tuple[str | None, float | None]:
    """Resolve amount-limit club and optional threshold amount from the question."""
    club_match = _AMOUNT_CLUB_PATTERN.search(message)
    amount = payment_amount_threshold_from_question(message)
    if club_match:
        return club_match.group(1).upper(), amount
    if amount is None:
        return None, None
    return payment_approval_club_for_amount(amount), amount


def payment_approval_club_for_amount(amount: float) -> str | None:
    if amount <= 0 or amount > ABSOLUTE_PAYMENT_LIMIT:
        return None
    for club, ceiling in _CLUB_CEILINGS:
        if amount <= ceiling:
            return club
    return None


def covering_lob_filter_from_question(message: str) -> str | None:
    return lob_filter_from_question(message)
