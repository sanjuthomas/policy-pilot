from __future__ import annotations

from etl.multimodal_write import MultimodalWrite, multimodal_upsert_params


def test_multimodal_upsert_params_denormalizes_fields():
    write = MultimodalWrite(
        document_id="doc-1",
        search_text="hello",
        payload={
            "source": "payment_fact",
            "payment_id": "pay-1",
            "action": "APPROVE",
            "outcome": "success",
        },
        dense_vector=[0.1, 0.2],
    )
    params = multimodal_upsert_params(write)
    assert params["document_id"] == "doc-1"
    assert params["payment_id"] == "pay-1"
    assert params["action"] == "APPROVE"
    assert params["embedding"] == [0.1, 0.2]
