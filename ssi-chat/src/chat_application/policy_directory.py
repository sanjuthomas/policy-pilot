from __future__ import annotations

import re
from typing import Any

from chat_application.cypher import (
    extract_payment_ids,
    lob_filter_from_question,
    payment_amount_threshold_from_question,
)

_AMOUNT_CLUB_PATTERN = re.compile(
    r"\b(UP_TO_\d+_(?:MILLION|BILLION)_CLUB)\b",
    re.IGNORECASE,
)

_STRICT_AMOUNT_COMPARISON = re.compile(
    r"(?:>|greater\s+than|more\s+than|over|above|exceeding)\b",
    re.IGNORECASE,
)

_INCLUSIVE_AMOUNT_COMPARISON = re.compile(
    r"\bat\s+least\b",
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


def is_strict_payment_amount_threshold(message: str) -> bool:
    """True when the question asks for payments strictly above the threshold (>, exceeding, …)."""
    if _INCLUSIVE_AMOUNT_COMPARISON.search(message):
        return False
    if _STRICT_AMOUNT_COMPARISON.search(message):
        return True
    return bool(re.search(r"\bworth\s+more\s+than\b", message, re.IGNORECASE))


def payment_approval_clubs_for_amount(amount: float, *, strict: bool) -> list[str]:
    """Return amount-limit clubs whose members may approve payments at the given threshold."""
    if amount <= 0 or amount > ABSOLUTE_PAYMENT_LIMIT:
        return []
    clubs: list[str] = []
    for club, ceiling in _CLUB_CEILINGS:
        if strict:
            if ceiling > amount:
                clubs.append(club)
        elif ceiling >= amount:
            clubs.append(club)
    return clubs


def payment_approval_club_for_amount(amount: float) -> str | None:
    """Smallest club whose ceiling covers ``amount`` (inclusive)."""
    clubs = payment_approval_clubs_for_amount(amount, strict=False)
    return clubs[0] if clubs else None


def payment_approval_clubs_from_question(
    message: str,
) -> tuple[list[str], float | None, bool]:
    """Resolve amount-limit clubs, threshold amount, and comparison strictness."""
    club_match = _AMOUNT_CLUB_PATTERN.search(message)
    amount = payment_amount_threshold_from_question(message)
    if club_match:
        return [club_match.group(1).upper()], amount, is_strict_payment_amount_threshold(message)
    if amount is None:
        return [], None, True
    strict = is_strict_payment_amount_threshold(message)
    return payment_approval_clubs_for_amount(amount, strict=strict), amount, strict


def payment_approval_group_from_question(message: str) -> tuple[str | None, float | None]:
    """Resolve a single club (legacy) — prefer :func:`payment_approval_clubs_from_question`."""
    clubs, amount, _strict = payment_approval_clubs_from_question(message)
    if not clubs:
        return None, amount
    return clubs[0], amount


def merge_group_member_rows(members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate group-member rows by ``user_id`` (union across clubs)."""
    by_id: dict[str, dict[str, Any]] = {}
    for row in members:
        user_id = row.get("user_id")
        if not user_id:
            continue
        if user_id not in by_id:
            by_id[user_id] = dict(row)
            continue
        existing = by_id[user_id]
        for key in ("groups", "covering_lobs", "roles"):
            merged = sorted({*(existing.get(key) or []), *(row.get(key) or [])})
            existing[key] = merged
    return sorted(by_id.values(), key=lambda row: str(row.get("user_id") or ""))


def covering_lob_filter_from_question(message: str) -> str | None:
    return lob_filter_from_question(message)
