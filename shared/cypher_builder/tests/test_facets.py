from __future__ import annotations

import pytest
from cypher_builder.facets import (
    FacetEntity,
    build_facet_aggregate_cypher,
    facet_aggregate_queries,
    format_facet_aggregate_answer,
    is_facet_aggregate_question,
    parse_facet_aggregate,
    resolve_facet_dimension,
)
from cypher_builder import plan_graph_queries, validate_read_only_cypher


class TestFacetDetection:
    @pytest.mark.parametrize(
        "question",
        [
            "Can you group instructions by status?",
            "Group payments by status",
            "Break down instructions by LOB",
            "How many instructions exist per LOB?",
            "Payment count per creator",
        ],
    )
    def test_detects_facet_questions(self, question: str) -> None:
        mode = "payments" if "payment" in question.lower() else "instructions"
        assert is_facet_aggregate_question(question, mode=mode) is True

    def test_plain_count_is_not_facet(self) -> None:
        assert is_facet_aggregate_question(
            "How many instructions are there?",
            mode="instructions",
        ) is False


class TestFacetParsing:
    def test_instruction_group_by_status(self) -> None:
        spec = parse_facet_aggregate(
            "Can you group instructions by status?",
            mode="instructions",
        )
        assert spec is not None
        assert spec.entity == FacetEntity.INSTRUCTION
        assert spec.dimension.key == "status"

    def test_payment_group_by_lob(self) -> None:
        spec = parse_facet_aggregate(
            "Break down payments by line of business",
            mode="payments",
        )
        assert spec is not None
        assert spec.entity == FacetEntity.PAYMENT
        assert spec.dimension.key == "owning_lob"

    def test_payment_group_by_creator(self) -> None:
        spec = parse_facet_aggregate(
            "Group payments by creator",
            mode="payments",
        )
        assert spec is not None
        assert spec.dimension.key == "creator"
        assert "creator:User" in build_facet_aggregate_cypher(spec)

    def test_payment_value_date_range(self) -> None:
        spec = parse_facet_aggregate(
            "Group payments by status for value dates from 2026-01-01 to 2026-06-30",
            mode="payments",
        )
        assert spec is not None
        assert spec.date_range is not None
        cypher = build_facet_aggregate_cypher(spec)
        assert "p.value_date >= '2026-01-01'" in cypher
        assert "p.value_date <= '2026-06-30'" in cypher

    def test_instruction_last_n_days_filter(self) -> None:
        spec = parse_facet_aggregate(
            "Group instructions by status in the last 14 days",
            mode="instructions",
        )
        assert spec is not None
        assert spec.date_range is not None
        assert "P14D" in build_facet_aggregate_cypher(spec)


class TestFacetCypher:
    def test_instruction_status_uses_distinct_instruction_id(self) -> None:
        planned = facet_aggregate_queries(
            "Group instructions by status",
            mode="instructions",
        )
        assert planned is not None
        assert planned[0][0] == "facet_aggregate"
        cypher = planned[0][1]
        validate_read_only_cypher(cypher)
        assert "count(DISTINCT i.instruction_id)" in cypher
        assert "bucket" in cypher

    def test_payment_status_uses_distinct_payment_id(self) -> None:
        planned = facet_aggregate_queries(
            "Group payments by status",
            mode="payments",
        )
        assert planned is not None
        cypher = planned[0][1]
        validate_read_only_cypher(cypher)
        assert "count(DISTINCT pay.payment_id)" in cypher

    def test_plan_graph_queries_routes_to_facet(self) -> None:
        planned = plan_graph_queries(
            "Can you group them by status?",
            mode="instructions",
        )
        assert planned is not None
        assert planned[0][0] == "facet_aggregate"


class TestFacetFormatting:
    def test_formats_status_table(self) -> None:
        answer = format_facet_aggregate_answer(
            "Group instructions by status",
            [
                {"bucket": "APPROVED", "total": 823},
                {"bucket": "DRAFT", "total": 50},
            ],
            mode="instructions",
        )
        assert answer is not None
        assert "823" in answer
        assert "APPROVED" in answer
        assert "| Status |" in answer

    def test_resolves_dimension_aliases(self) -> None:
        dim = resolve_facet_dimension("line of business", FacetEntity.PAYMENT)
        assert dim is not None
        assert dim.key == "owning_lob"
