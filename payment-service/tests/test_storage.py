from datetime import datetime

from ps.constants import PAYMENT_CURRENT_OUT
from ps.models.payment import Payment
from ps.storage import (
    document_to_versioned_payment,
    payment_document_key,
    payment_id_from_document_key,
    versioned_payment_to_document,
)


def test_versioned_payment_round_trip(payment: Payment) -> None:
    valid_in = datetime(2025, 1, 15, 10, 30, 0)
    valid_out = "2025-06-01T00:00:00Z"

    doc = versioned_payment_to_document(
        payment,
        version_number=2,
        valid_in=valid_in,
        valid_out=valid_out,
    )
    assert doc["_id"] == payment_document_key(payment.payment_id, 2)
    assert "payment_id" not in doc
    assert doc["version_number"] == 2
    assert doc["instruction_id"] == payment.instruction_id
    assert "payment_id" not in doc["payload"]

    restored = document_to_versioned_payment(doc)
    assert restored.version_number == 2
    assert restored.payment.payment_id == payment.payment_id


def test_versioned_payment_current_out_sentinel(payment: Payment) -> None:
    valid_in = datetime(2025, 3, 1, 12, 0, 0)
    doc = versioned_payment_to_document(
        payment,
        version_number=1,
        valid_in=valid_in,
    )
    assert doc["out"] == PAYMENT_CURRENT_OUT

    restored = document_to_versioned_payment(doc)
    assert restored.valid_out is None


def test_payment_id_from_document_key() -> None:
    assert payment_id_from_document_key("20260701-CORP-P-1|3") == "20260701-CORP-P-1"
