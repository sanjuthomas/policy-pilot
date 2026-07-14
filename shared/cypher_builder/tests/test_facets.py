from __future__ import annotations

import pytest
from cypher_builder.facets import (
    FacetEntity,
    build_facet_aggregate_cypher,
    facet_aggregate_queries,
    format_facet_aggregate_answer,
    is_analytics_question,
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
        assert is_analytics_question(question, mode=mode) is True

    def test_plain_count_is_not_facet(self) -> None:
        assert is_analytics_question(
            "How many instructions are there?",
            mode="instructions",
        ) is False

    def test_superlative_is_analytics(self) -> None:
        assert is_analytics_question(
            "Who created the most payments?",
            mode="payments",
        )


class TestRegressionFacetBaselines:
    """Guard rails for facet behavior shipped in the prior release."""

    @pytest.mark.parametrize(
        "question,mode",
        [
            ("Can you group instructions by status?", "instructions"),
            ("Group payments by status", "payments"),
            ("Break down instructions by LOB", "instructions"),
            ("How many instructions exist per LOB?", "instructions"),
        ],
    )
    def test_existing_facet_questions_still_parse(self, question: str, mode: str) -> None:
        spec = parse_facet_aggregate(question, mode=mode)
        assert spec is not None
        assert spec.return_mode == "table"
        assert spec.limit == 50
        planned = facet_aggregate_queries(question, mode=mode)
        assert planned is not None
        validate_read_only_cypher(planned[0][1])


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


class TestSuperlativeAnalytics:
    def test_who_created_most_payments(self) -> None:
        spec = parse_facet_aggregate(
            "Who created the most payments?",
            mode="payments",
        )
        assert spec is not None
        assert spec.dimension.key == "creator"
        assert spec.limit == 1
        assert spec.return_mode == "single_winner"
        cypher = build_facet_aggregate_cypher(spec)
        assert "LIMIT 1" in cypher
        assert "count(DISTINCT pay.payment_id)" in cypher

    def test_who_approved_most_payments(self) -> None:
        spec = parse_facet_aggregate(
            "Who approved most payments?",
            mode="payments",
        )
        assert spec is not None
        assert spec.dimension.key == "approver"

    def test_extreme_payment_not_superlative(self) -> None:
        assert parse_facet_aggregate(
            "Who created the payment with the maximum dollar value?",
            mode="payments",
        ) is None

    def test_formats_single_winner(self) -> None:
        answer = format_facet_aggregate_answer(
            "Who created the most payments?",
            [{"bucket": "Bergmann, Thomas (pay-300)", "total": 355}],
            mode="payments",
        )
        assert answer is not None
        assert "Bergmann" in answer
        assert "355" in answer
        assert "created the most payments" in answer


class TestMultiMetricAnalytics:
    def test_avg_approval_time_metric(self) -> None:
        spec = parse_facet_aggregate(
            "Can you group payments by approvers and include the average time "
            "they have taken to approve them?",
            mode="payments",
        )
        assert spec is not None
        assert spec.dimension.key == "approver"
        assert "avg_approval_time" in spec.metrics
        cypher = build_facet_aggregate_cypher(spec)
        assert "avg_approval_hours" in cypher
        assert "approved_at" in cypher

    def test_formats_multi_metric_table(self) -> None:
        answer = format_facet_aggregate_answer(
            "Group payments by approver with average approval time",
            [
                {
                    "bucket": "Osei, Victoria (pay-400)",
                    "total": 460,
                    "avg_approval_hours": 2.5,
                }
            ],
            mode="payments",
        )
        assert answer is not None
        assert "Avg approval time" in answer
        assert "2.5 hours" in answer

    def test_unsupported_median_note(self) -> None:
        spec = parse_facet_aggregate(
            "Group payments by approver with median approval time",
            mode="payments",
        )
        assert spec is not None
        assert "median" in spec.unsupported_requests
        answer = format_facet_aggregate_answer(
            "Group payments by approver with median approval time",
            [{"bucket": "A", "total": 1}],
            mode="payments",
        )
        assert answer is not None
        assert "median is not supported" in answer


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
