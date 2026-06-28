"""Shared test fixtures for ssi-indexer tests."""

from __future__ import annotations


def sample_event() -> dict:
    return {
        "event_id": "evt-1",
        "timestamp": "2024-01-01T00:00:00Z",
        "severity": "ALERT",
        "message": "access denied",
        "actor": {
            "user_id": "u1",
            "given_name": "Jane",
            "family_name": "Doe",
            "title": "Analyst",
            "roles": ["viewer"],
            "lob": "LOB-A",
            "supervisor_id": "sup1",
        },
        "resource": {
            "id": "instr-1",
            "version_number": 2,
            "owning_lob": "LOB-A",
            "status": "ACTIVE",
            "instruction_type": "WIRE",
        },
        "event": {
            "action": "READ",
            "outcome": "DENY",
            "reason": "not authorized",
        },
        "details": {
            "authorization": {
                "summary": "denied by policy",
                "decision": "DENY",
                "allow_basis": [],
                "violations": ["missing role"],
            }
        },
    }


def sample_instruction() -> dict:
    return {
        "instruction_id": "instr-1",
        "version_number": 3,
        "instruction_type": "WIRE",
        "wire_scope": "DOMESTIC",
        "owning_lob": "LOB-A",
        "status": "ACTIVE",
        "currency": "USD",
        "effective_date": "2024-01-01",
        "end_date": "2024-12-31",
        "usage_count": 5,
        "creditor": {"name": "Creditor Inc"},
        "debtor": {"name": "Debtor LLC"},
        "creditor_account": {"identification": "ACC-1", "identification_scheme": "IBAN"},
        "debtor_account": {"identification": "ACC-2"},
        "creditor_agent": {"financial_institution": {"identification": "BIC123"}},
        "created_by": {
            "user_id": "c1",
            "given_name": "Creator",
            "family_name": "One",
            "title": "Mgr",
            "lob": "LOB-A",
            "supervisor_id": "cs1",
        },
        "approved_by": {
            "user_id": "a1",
            "given_name": "Approver",
            "family_name": "Two",
            "title": "Dir",
            "lob": "LOB-A",
            "supervisor_id": "as1",
        },
        "rejected_by": {
            "user_id": "r1",
            "given_name": "Rejector",
            "family_name": "Three",
            "title": "VP",
            "lob": "LOB-B",
            "supervisor_id": "rs1",
        },
    }
