from etl.mongo_cdc import (
    normalize_instruction_message,
    normalize_payment_message,
    normalize_security_event,
    versioned_instruction_to_fact,
    versioned_payment_to_fact,
)


def test_normalize_security_event_adds_event_id_from_mongo_id() -> None:
    event = normalize_security_event(
        {
            "_id": "se-001",
            "severity": "INFO",
            "message": "ok",
        }
    )
    assert event["event_id"] == "se-001"
    assert event["_id"] == "se-001"


def test_normalize_security_event_preserves_existing_event_id() -> None:
    event = normalize_security_event({"_id": "se-001", "event_id": "legacy"})
    assert event["event_id"] == "legacy"


def test_versioned_instruction_to_fact_uses_lifecycle_actor() -> None:
    fact = versioned_instruction_to_fact(
        {
            "_id": "instr-001|2",
            "version_number": 2,
            "in": "2026-07-01T12:00:00Z",
            "out": "9999-12-31T23:59:59Z",
            "status": "STANDING",
            "owning_lob": "FICC",
            "wire_scope": "DOMESTIC",
            "payload": {
                "instruction_type": "SINGLE_USE",
                "currency": "USD",
                "created_by": {
                    "user_id": "creator-1",
                    "given_name": "C",
                    "family_name": "Creator",
                },
                "approved_by": {
                    "user_id": "approver-1",
                    "given_name": "A",
                    "family_name": "Approver",
                    "lob": "FICC",
                },
                "lifecycle_events": [
                    {"action": "APPROVE", "actor_user_id": "approver-1"},
                ],
            },
        }
    )
    assert fact is not None
    assert fact["action"] == "APPROVE"
    assert fact["actor_user_id"] == "approver-1"
    assert fact["actor_given_name"] == "A"
    assert fact["timestamp"] == "2026-07-01T12:00:00Z"


def test_versioned_payment_to_fact_sets_timestamp() -> None:
    fact = versioned_payment_to_fact(
        {
            "_id": "pay-001|3",
            "version_number": 3,
            "in": "2026-07-01T13:00:00Z",
            "status": "SUBMITTED",
            "instruction_id": "instr-001",
            "payload": {
                "amount": 1000.0,
                "currency": "USD",
                "instruction_version": 2,
                "created_by": {"user_id": "pay-101"},
            },
        }
    )
    assert fact is not None
    assert fact["timestamp"] == "2026-07-01T13:00:00Z"
    assert fact["instruction_version"] == 2


def test_versioned_instruction_search_text_from_cdc() -> None:
    from etl.instruction_pipeline import build_instruction_state_search_text

    fact = versioned_instruction_to_fact(
        {
            "_id": "instr-001|2",
            "version_number": 2,
            "in": "2026-07-01T12:00:00Z",
            "status": "PENDING",
            "owning_lob": "FICC",
            "wire_scope": "DOMESTIC",
            "payload": {
                "instruction_type": "WIRE",
                "currency": "USD",
                "rejection_reason": "duplicate route",
                "created_by": {"user_id": "c1", "given_name": "C", "family_name": "One"},
                "lifecycle_events": [{"action": "SUBMIT", "actor_user_id": "c1"}],
            },
        }
    )
    assert fact is not None
    text = build_instruction_state_search_text(fact)
    assert "instr-001" in text
    assert "duplicate route" in text
    assert "SUBMIT" in text
    assert "2026-07-01T12:00:00Z" in text


def test_versioned_instruction_to_fact() -> None:
    fact = versioned_instruction_to_fact(
        {
            "_id": "instr-001|2",
            "version_number": 2,
            "in": "2026-07-01T12:00:00Z",
            "out": "9999-12-31T23:59:59Z",
            "status": "PENDING",
            "owning_lob": "FICC",
            "wire_scope": "DOMESTIC",
            "payload": {
                "instruction_type": "SINGLE_USE",
                "currency": "USD",
                "created_by": {
                    "user_id": "alice.ficc",
                    "title": "VP",
                    "roles": ["INSTRUCTION_CREATOR"],
                },
                "lifecycle_events": [{"action": "SUBMIT", "actor_user_id": "alice.ficc"}],
            },
        }
    )
    assert fact is not None
    assert fact["instruction_id"] == "instr-001"
    assert fact["version_number"] == 2
    assert fact["action"] == "SUBMIT"
    assert fact["instruction_snapshot"]["status"] == "PENDING"
    assert fact["actor_user_id"] == "alice.ficc"


def test_normalize_instruction_message_accepts_legacy_fact() -> None:
    legacy = {"instruction_id": "instr-001", "version_number": 1}
    assert normalize_instruction_message(legacy) is legacy


def test_versioned_payment_to_fact() -> None:
    fact = versioned_payment_to_fact(
        {
            "_id": "pay-001|3",
            "version_number": 3,
            "in": "2026-07-01T12:00:00Z",
            "out": "9999-12-31T23:59:59Z",
            "status": "SUBMITTED",
            "owning_lob": "FICC",
            "instruction_id": "instr-001",
            "payload": {
                "amount": 1000.0,
                "currency": "USD",
                "created_by": {"user_id": "pay-101", "title": "MO"},
            },
        }
    )
    assert fact is not None
    assert fact["payment_id"] == "pay-001"
    assert fact["version_number"] == 3
    assert fact["status"] == "SUBMITTED"
    assert fact["amount"] == 1000.0


def test_normalize_payment_message_accepts_legacy_fact() -> None:
    legacy = {"payment_id": "pay-001", "status": "DRAFT"}
    assert normalize_payment_message(legacy) is legacy
