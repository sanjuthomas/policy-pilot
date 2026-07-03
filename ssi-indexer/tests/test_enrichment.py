"""Tests for etl.enrichment."""

from __future__ import annotations

from helpers import sample_event as _sample_event
from helpers import sample_instruction as _sample_instruction

from etl.enrichment import (
    EnrichedSecurityEventDocument,
    build_merged_context,
    build_search_text,
    enrich_document,
)


def test_build_merged_context_with_instruction():
    event = _sample_event()
    instruction = _sample_instruction()
    merged = build_merged_context(event, instruction)

    assert merged["actor_user_id"] == "u1"
    assert merged["actor_display"] == "Doe, Jane (u1)"
    assert merged["instruction_id"] == "instr-1"
    assert merged["version_number"] == 2  # resource takes precedence
    assert merged["creditor_name"] == "Creditor Inc"
    assert merged["creditor_agent_bic"] == "BIC123"
    assert merged["creator_display"] == "One, Creator (c1)"
    assert merged["approver_display"] == "Two, Approver (a1)"
    assert merged["authorization_decision"] == "DENY"


def test_build_merged_context_uses_instruction_snapshot():
    event = _sample_event()
    event["instruction_snapshot"] = {
        "instruction_id": "snap-id",
        "version_number": 9,
        "status": "PENDING",
        "created_by": {"user_id": "snap-creator"},
    }
    merged = build_merged_context(event, None)
    assert merged["instruction_id"] == "instr-1"  # resource id still used
    assert merged["status"] == "PENDING"
    assert merged["creator_user_id"] == "snap-creator"


def test_build_merged_context_display_name_user_id_only():
    event = {"actor": {"user_id": "only-id"}}
    merged = build_merged_context(event, None)
    assert merged["actor_display"] == "only-id"


def test_build_search_text_includes_key_fields():
    event = _sample_event()
    instruction = _sample_instruction()
    text = build_search_text(event, instruction)
    assert "access denied" in text
    assert "ALERT" in text
    assert "READ" in text
    assert "DENY" in text
    assert "u1" in text
    assert "Creditor Inc" in text
    assert "denied by policy" in text


def test_build_search_text_with_prebuilt_merged():
    event = _sample_event()
    merged = build_merged_context(event, None)
    text = build_search_text(event, None, merged)
    assert "access denied" in text


def test_enrich_document():
    event = _sample_event()
    instruction = _sample_instruction()
    doc = enrich_document(event, instruction)

    assert isinstance(doc, EnrichedSecurityEventDocument)
    assert doc.event_id == "evt-1"
    assert doc.instruction_id == "instr-1"
    assert doc.version_number == 3  # instruction overrides resource
    assert doc.instruction == instruction
    assert doc.merged
    assert doc.search_text
    assert "access denied" in doc.search_text


def test_enrich_document_without_instruction():
    event = _sample_event()
    doc = enrich_document(event, None)
    assert doc.version_number == 2
    assert doc.instruction is None
