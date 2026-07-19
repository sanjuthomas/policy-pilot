"""Chat retrieval LOB scope derived from the logged-in subject (issue #63)."""

from __future__ import annotations

from typing import Any

from chat_application.auth.capabilities import COMPLIANCE_ROLES
from chat_application.auth.subject import Subject

_LOB_KEYS = ("owning_lob", "lob", "instruction_owning_lob")


def allowed_retrieval_lobs(subject: Subject | None) -> frozenset[str] | None:
    """LOBs the subject may see in graph/direct retrieval.

    Returns:
        ``None`` — unscoped (compliance / platform admin / missing subject)
        empty frozenset — no LOB entitlement
        non-empty frozenset — FO desk lob or MO covering_lobs
    """
    if subject is None:
        return None

    roles = set(subject.roles)
    groups = set(subject.groups)
    if roles & COMPLIANCE_ROLES or "COMPLIANCE" in groups:
        return None

    if "MIDDLE_OFFICE" in groups:
        return frozenset(
            lob.strip().upper()
            for lob in subject.covering_lobs
            if isinstance(lob, str) and lob.strip()
        )

    if subject.lob and str(subject.lob).strip():
        return frozenset({str(subject.lob).strip().upper()})

    return frozenset()


def row_owning_lob(row: dict[str, Any]) -> str | None:
    for key in _LOB_KEYS:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None


def filter_rows_by_retrieval_lobs(
    rows: list[dict[str, Any]],
    allowed_lobs: frozenset[str] | None,
) -> list[dict[str, Any]]:
    """Drop detail rows whose owning_lob is outside the subject scope.

    Aggregate rows without an owning_lob column are kept (Cypher should already
    have applied the subject filter for counts).
    """
    if allowed_lobs is None:
        return rows
    kept: list[dict[str, Any]] = []
    for row in rows:
        lob = row_owning_lob(row)
        if lob is None or lob in allowed_lobs:
            kept.append(row)
    return kept


__all__ = [
    "allowed_retrieval_lobs",
    "filter_rows_by_retrieval_lobs",
    "row_owning_lob",
]
