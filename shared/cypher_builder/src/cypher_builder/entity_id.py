"""Parse Policy Pilot sequence business IDs into a structured story.

Canonical format (see sequence-service README)::

    {YYYYMMDD}-{OWNING_LOB}-{I|P}-{sequence}

Examples:
  ``20260719-FICC-I-14`` → instruction, LOB FICC, date 2026-07-19, seq 14
  ``20260712-FICC-P-2``  → payment, LOB FICC, date 2026-07-12, seq 2

The ``I`` / ``P`` code alone distinguishes instruction vs payment — callers should
not require the English noun when an id is present. Use :func:`parse_entity_id`
for a single token and :func:`find_entity_ids` when scanning natural-language text.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Literal

EntityCode = Literal["I", "P"]
EntityTypeName = Literal["instruction", "payment"]

_ENTITY_TYPE_BY_CODE: dict[str, EntityTypeName] = {
    "I": "instruction",
    "P": "payment",
}

# 7-digit dates are accepted so normalize can repair common typos (0260704 → 20260704).
_SEQUENCE_ID = re.compile(
    r"^(?P<date>\d{7,8})-(?P<lob>[A-Z0-9_]+)-(?P<code>[IP])-(?P<seq>\d+)$",
    re.IGNORECASE,
)
_SEQUENCE_ID_IN_TEXT = re.compile(
    r"\d{7,8}-[A-Z0-9_]+-[IP]-\d+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedEntityId:
    """Structured story for a sequence instruction or payment id."""

    raw: str
    normalized: str
    entity_code: EntityCode
    entity_type: EntityTypeName
    business_date: date
    owning_lob: str
    sequence_number: int

    @property
    def counter_key(self) -> str:
        """Key shape used by sequence-service counters (date-LOB-code)."""
        return (
            f"{self.business_date.strftime('%Y%m%d')}-"
            f"{self.owning_lob}-{self.entity_code}"
        )

    @property
    def is_instruction(self) -> bool:
        return self.entity_code == "I"

    @property
    def is_payment(self) -> bool:
        return self.entity_code == "P"

    def story(self) -> str:
        """Human-readable one-liner for logs / LLM slot context."""
        return (
            f"{self.entity_type} `{self.normalized}`: "
            f"business_date={self.business_date.isoformat()}, "
            f"owning_lob={self.owning_lob}, "
            f"sequence={self.sequence_number}"
        )

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["business_date"] = self.business_date.isoformat()
        payload["counter_key"] = self.counter_key
        payload["story"] = self.story()
        return payload


def _normalize_date_digits(date_part: str) -> str | None:
    if len(date_part) == 8:
        return date_part
    if len(date_part) == 7 and date_part.startswith("0"):
        return f"2{date_part}"
    return None


def _parse_business_date(date_part: str) -> date | None:
    normalized = _normalize_date_digits(date_part)
    if normalized is None:
        return None
    try:
        return datetime.strptime(normalized, "%Y%m%d").date()
    except ValueError:
        return None


def parse_entity_id(value: str) -> ParsedEntityId | None:
    """Parse one sequence id token into :class:`ParsedEntityId`, or ``None``."""
    raw = value.strip()
    match = _SEQUENCE_ID.match(raw)
    if not match:
        return None
    date_part, lob, code, seq = (
        match.group("date"),
        match.group("lob"),
        match.group("code").upper(),
        match.group("seq"),
    )
    business_date = _parse_business_date(date_part)
    if business_date is None or code not in _ENTITY_TYPE_BY_CODE:
        return None
    entity_code: EntityCode = "I" if code == "I" else "P"
    normalized = (
        f"{business_date.strftime('%Y%m%d')}-"
        f"{lob.upper()}-{entity_code}-{int(seq)}"
    )
    return ParsedEntityId(
        raw=raw,
        normalized=normalized,
        entity_code=entity_code,
        entity_type=_ENTITY_TYPE_BY_CODE[entity_code],
        business_date=business_date,
        owning_lob=lob.upper(),
        sequence_number=int(seq),
    )


def find_entity_ids(text: str) -> list[ParsedEntityId]:
    """Return unique parsed sequence ids in order of first appearance in ``text``."""
    found: list[ParsedEntityId] = []
    seen: set[str] = set()
    for match in _SEQUENCE_ID_IN_TEXT.finditer(text or ""):
        parsed = parse_entity_id(match.group(0))
        if parsed is None or parsed.normalized in seen:
            continue
        seen.add(parsed.normalized)
        found.append(parsed)
    return found


def normalize_sequence_entity_id(entity_id: str) -> str:
    """Normalize a sequence id; return stripped input when not parseable."""
    parsed = parse_entity_id(entity_id)
    return parsed.normalized if parsed else entity_id.strip()
