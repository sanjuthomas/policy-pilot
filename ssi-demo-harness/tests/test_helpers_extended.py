from __future__ import annotations

from unittest.mock import MagicMock, patch

from harness.helpers import (
    PaymentOperation,
    _count_payment_security_events,
    _count_security_events,
    build_payment_scenario,
    build_seed_plan,
    payment_submitter_for_lob,
)


def test_build_seed_plan_length() -> None:
    assert len(build_seed_plan(3)) == 3


def test_build_payment_scenario_non_empty() -> None:
    scenario = build_payment_scenario()
    assert scenario
    assert scenario[0][0] == PaymentOperation.CREATE_PAYMENT


def test_payment_submitter_for_lob() -> None:
    assert payment_submitter_for_lob("FICC").startswith("fo-ficc")


def test_count_security_events_with_mock_mongo() -> None:
    from harness.config import Settings

    settings = Settings()
    mock_collection = MagicMock()
    mock_collection.count_documents.return_value = 42
    mock_client = MagicMock()
    mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

    with patch("pymongo.MongoClient", return_value=mock_client):
        assert _count_security_events(settings) == 42


def test_count_payment_security_events_with_mock_mongo() -> None:
    from harness.config import Settings

    settings = Settings()
    mock_collection = MagicMock()
    mock_collection.count_documents.return_value = 7
    mock_client = MagicMock()
    mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

    with patch("pymongo.MongoClient", return_value=mock_client):
        assert _count_payment_security_events(settings) == 7
