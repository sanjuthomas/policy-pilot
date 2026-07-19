"""Tests for sequence entity-id parse / story utility."""

from __future__ import annotations

from datetime import date

import pytest

from cypher_builder.entity_id import (
    ParsedEntityId,
    find_entity_ids,
    normalize_sequence_entity_id,
    parse_entity_id,
)
from cypher_builder.query_engine import (
    extract_entity_ids,
    extract_instruction_ids,
    extract_payment_ids,
)


class TestParseEntityId:
    def test_instruction_id_story(self) -> None:
        parsed = parse_entity_id("20260719-FICC-I-14")
        assert parsed is not None
        assert parsed.entity_code == "I"
        assert parsed.entity_type == "instruction"
        assert parsed.is_instruction
        assert not parsed.is_payment
        assert parsed.business_date == date(2026, 7, 19)
        assert parsed.owning_lob == "FICC"
        assert parsed.sequence_number == 14
        assert parsed.normalized == "20260719-FICC-I-14"
        assert parsed.counter_key == "20260719-FICC-I"
        assert "instruction" in parsed.story()
        assert "FICC" in parsed.story()
        assert "2026-07-19" in parsed.story()

    def test_payment_id_story(self) -> None:
        parsed = parse_entity_id("20260712-FICC-P-2")
        assert parsed is not None
        assert parsed.entity_code == "P"
        assert parsed.entity_type == "payment"
        assert parsed.is_payment
        assert parsed.sequence_number == 2
        assert parsed.counter_key == "20260712-FICC-P"

    def test_lob_with_underscores(self) -> None:
        parsed = parse_entity_id("20260705-DESK_RATES-I-3")
        assert parsed is not None
        assert parsed.owning_lob == "DESK_RATES"
        assert parsed.entity_type == "instruction"

    def test_normalizes_case_and_strips(self) -> None:
        parsed = parse_entity_id("  20260719-ficc-i-14  ")
        assert parsed is not None
        assert parsed.normalized == "20260719-FICC-I-14"
        assert parsed.raw == "20260719-ficc-i-14"

    def test_repairs_seven_digit_date_typo(self) -> None:
        parsed = parse_entity_id("0260704-FICC-P-1")
        assert parsed is not None
        assert parsed.normalized == "20260704-FICC-P-1"
        assert parsed.business_date == date(2026, 7, 4)

    def test_rejects_impossible_date(self) -> None:
        assert parse_entity_id("20261399-FICC-I-1") is None

    def test_rejects_uuid(self) -> None:
        assert parse_entity_id("550e8400-e29b-41d4-a716-446655440000") is None

    def test_rejects_security_event_id(self) -> None:
        assert parse_entity_id("20260719-FICC-I-14-SE-7") is None

    def test_rejects_empty(self) -> None:
        assert parse_entity_id("") is None
        assert parse_entity_id("   ") is None

    def test_as_dict_includes_story(self) -> None:
        payload = parse_entity_id("20260719-FICC-I-14").as_dict()  # type: ignore[union-attr]
        assert payload["entity_type"] == "instruction"
        assert payload["business_date"] == "2026-07-19"
        assert payload["counter_key"] == "20260719-FICC-I"
        assert "instruction" in payload["story"]


class TestFindEntityIds:
    def test_finds_both_kinds_in_order(self) -> None:
        text = "Compare 20260719-FICC-I-14 with payment 20260712-FICC-P-2 please"
        found = find_entity_ids(text)
        assert [p.normalized for p in found] == [
            "20260719-FICC-I-14",
            "20260712-FICC-P-2",
        ]
        assert found[0].is_instruction
        assert found[1].is_payment

    def test_dedupes_repeated_ids(self) -> None:
        text = "Show 20260719-FICC-I-14 again: 20260719-FICC-I-14"
        found = find_entity_ids(text)
        assert len(found) == 1

    def test_bare_show_me_question(self) -> None:
        found = find_entity_ids("Can you show me 20260719-FICC-I-14?")
        assert len(found) == 1
        assert found[0].entity_type == "instruction"
        assert found[0].owning_lob == "FICC"

    def test_no_ids(self) -> None:
        assert find_entity_ids("How many alerts today?") == []


class TestNormalizeAndExtractors:
    def test_normalize_wrapper(self) -> None:
        assert normalize_sequence_entity_id("20260719-ficc-i-14") == "20260719-FICC-I-14"
        assert normalize_sequence_entity_id("not-an-id") == "not-an-id"

    def test_extract_instruction_and_payment(self) -> None:
        text = "Show me 20260719-FICC-I-14 and 20260712-FICC-P-2"
        assert extract_instruction_ids(text) == ["20260719-FICC-I-14"]
        assert extract_payment_ids(text) == ["20260712-FICC-P-2"]

    def test_extract_entity_ids_prefers_sequence(self) -> None:
        text = "Look up 20260719-FICC-I-14"
        assert extract_entity_ids(text) == ["20260719-FICC-I-14"]

    @pytest.mark.parametrize(
        ("value", "entity_type"),
        [
            ("20260719-FICC-I-14", "instruction"),
            ("20260712-FX-P-9", "payment"),
            ("20260101-DESK_RATES-I-100", "instruction"),
        ],
    )
    def test_round_trip_type_from_code(self, value: str, entity_type: str) -> None:
        parsed = parse_entity_id(value)
        assert parsed is not None
        assert parsed.entity_type == entity_type
        assert isinstance(parsed, ParsedEntityId)
