"""Subject LOB scope for deterministic / planned Cypher (issue #63 phase 2).

When a retrieval request runs under ``retrieval_lob_scope(allowed)``:
- ``None`` — compliance / admin: no subject LOB restriction (question LOB still applies)
- empty frozenset — deny all rows
- non-empty — constrain ``alias.owning_lob`` to that set (intersected with question LOB)

Outside an active scope (unit tests of builders), behavior matches the historical
question-only LOB filter.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_SCOPE_ACTIVE: ContextVar[bool] = ContextVar("cypher_lob_scope_active", default=False)
_ALLOWED_LOBS: ContextVar[frozenset[str] | None] = ContextVar(
    "cypher_allowed_retrieval_lobs", default=None
)

_ALIAS_TOKEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LOB_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
_LOB_FILTER = re.compile(
    r"\b(?:lob\s+|desk\s+lob\s+|for\s+|payments?\s+for\s+)?"
    r"(FICC|FX|DESK_[A-Z][A-Z0-9_]*)\b",
    re.IGNORECASE,
)


def _escape_lob(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _named_lob_from_question(question: str) -> str | None:
    match = _LOB_FILTER.search(question)
    return match.group(1).upper() if match else None


@contextmanager
def retrieval_lob_scope(allowed_lobs: frozenset[str] | None) -> Iterator[None]:
    """Bind subject-allowed LOBs for the duration of Cypher planning/building."""
    active_token = _SCOPE_ACTIVE.set(True)
    allowed_token = _ALLOWED_LOBS.set(allowed_lobs)
    try:
        yield
    finally:
        _ALLOWED_LOBS.reset(allowed_token)
        _SCOPE_ACTIVE.reset(active_token)


def get_allowed_retrieval_lobs() -> frozenset[str] | None:
    """Return allowed LOBs when scope is active; ``None`` means unscoped."""
    if not _SCOPE_ACTIVE.get():
        return None
    return _ALLOWED_LOBS.get()


def owning_lob_and_clause(
    *,
    alias: str,
    question: str | None = None,
    explicit_lob: str | None = None,
) -> str:
    """Return a Cypher ``AND …`` fragment constraining ``alias.owning_lob``."""
    if not _ALIAS_TOKEN.match(alias):
        raise ValueError(f"invalid Cypher alias for LOB scope: {alias!r}")

    named = explicit_lob
    if named is None and question:
        named = _named_lob_from_question(question)
    if named is not None:
        named = named.strip().upper()
        if not _LOB_NAME.match(named):
            return " AND false"

    allowed = get_allowed_retrieval_lobs()

    if allowed is None:
        if named:
            return f" AND {alias}.owning_lob = '{_escape_lob(named)}'"
        return ""

    if not allowed:
        return " AND false"

    if named is not None:
        if named not in allowed:
            return " AND false"
        return f" AND {alias}.owning_lob = '{_escape_lob(named)}'"

    ordered = sorted(lob for lob in allowed if _LOB_NAME.match(lob))
    if not ordered:
        return " AND false"
    if len(ordered) == 1:
        return f" AND {alias}.owning_lob = '{_escape_lob(ordered[0])}'"
    listed = ", ".join(f"'{_escape_lob(lob)}'" for lob in ordered)
    return f" AND {alias}.owning_lob IN [{listed}]"


__all__ = [
    "get_allowed_retrieval_lobs",
    "owning_lob_and_clause",
    "retrieval_lob_scope",
]
