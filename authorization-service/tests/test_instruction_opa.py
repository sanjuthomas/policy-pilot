from __future__ import annotations

from authz.instruction_opa import build_instruction_opa_context


def test_build_instruction_opa_context_maps_instruction_document() -> None:
    instruction, account = build_instruction_opa_context(
        {
            "status": "SUBMITTED",
            "instruction_type": "STANDING",
            "owning_lob": "FICC",
            "effective_date": "2026-01-01T00:00:00",
            "end_date": "2027-01-01T00:00:00",
            "created_by": {
                "user_id": "ficc-101",
                "title": "Analyst",
                "supervisor_id": "ficc-201",
            },
            "suspended_by": None,
            "funding_account": {"owning_lob": "FICC"},
        }
    )

    assert instruction["status"] == "SUBMITTED"
    assert instruction["type"] == "STANDING"
    assert instruction["created_by"]["title"] == "Analyst"
    assert instruction["effective_date"].endswith("Z")
    assert account["owning_lob"] == "FICC"
