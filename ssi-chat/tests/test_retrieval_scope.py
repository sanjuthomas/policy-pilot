"""Unit tests for chat retrieval LOB scope (issue #63 phase 2a)."""

from __future__ import annotations

from chat_application.auth.retrieval_scope import (
    allowed_retrieval_lobs,
    filter_rows_by_retrieval_lobs,
)
from chat_application.auth.subject import Subject


def _subject(**kwargs) -> Subject:
    base = {
        "user_id": "u-1",
        "given_name": "Test",
        "family_name": "User",
        "title": "Analyst",
        "lob": None,
        "roles": [],
        "groups": [],
        "covering_lobs": [],
    }
    base.update(kwargs)
    return Subject(**base)


def test_compliance_is_unscoped() -> None:
    assert (
        allowed_retrieval_lobs(
            _subject(roles=["COMPLIANCE_ANALYST"], user_id="comp-001")
        )
        is None
    )


def test_platform_admin_is_unscoped() -> None:
    assert (
        allowed_retrieval_lobs(_subject(roles=["PLATFORM_ADMIN"], user_id="admin-001"))
        is None
    )


def test_fo_desk_lob() -> None:
    assert allowed_retrieval_lobs(
        _subject(user_id="fo-ficc-101", lob="FICC", roles=["PAYMENT_CREATOR"])
    ) == frozenset({"FICC"})


def test_mo_covering_lobs() -> None:
    assert allowed_retrieval_lobs(
        _subject(
            user_id="pay-101",
            roles=["PAYMENT_CREATOR"],
            groups=["MIDDLE_OFFICE"],
            covering_lobs=["FICC", "FX"],
        )
    ) == frozenset({"FICC", "FX"})


def test_mo_empty_covering_denies_all() -> None:
    assert allowed_retrieval_lobs(
        _subject(
            user_id="pay-x",
            roles=["PAYMENT_CREATOR"],
            groups=["MIDDLE_OFFICE"],
            covering_lobs=[],
        )
    ) == frozenset()


def test_fo_without_lob_denies_all() -> None:
    assert allowed_retrieval_lobs(
        _subject(user_id="orphan", roles=["PAYMENT_CREATOR"], lob=None)
    ) == frozenset()


def test_filter_rows_keeps_aggregates_and_allowed_detail() -> None:
    rows = [
        {"total": 3},
        {"owning_lob": "FICC", "instruction_id": "I-1"},
        {"owning_lob": "FX", "instruction_id": "I-2"},
        {"lob": "FICC", "event_id": "E-1"},
    ]
    filtered = filter_rows_by_retrieval_lobs(rows, frozenset({"FICC"}))
    assert filtered == [
        {"total": 3},
        {"owning_lob": "FICC", "instruction_id": "I-1"},
        {"lob": "FICC", "event_id": "E-1"},
    ]


def test_filter_rows_unscoped_passthrough() -> None:
    rows = [{"owning_lob": "FX"}]
    assert filter_rows_by_retrieval_lobs(rows, None) == rows
