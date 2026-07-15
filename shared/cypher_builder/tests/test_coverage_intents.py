from __future__ import annotations

from cypher_builder import (
    CypherQueryBuilder,
    GraphIntent,
    GraphQueryPlan,
    plans_from_graph_query,
)
from cypher_builder.facets import (
    FacetEntity,
    _date_range_clause,
    facet_aggregate_queries,
    facet_dimensions,
    format_facet_aggregate_answer,
    is_analytics_question,
    parse_facet_aggregate,
)


def test_plans_from_alert_count_today() -> None:
    plan = GraphQueryPlan(intent=GraphIntent.ALERT_COUNT_TODAY)
    planned = plans_from_graph_query(plan, mode="events")
    assert planned is not None
    assert planned[0][0]


def test_plans_lookup_and_approval_branches() -> None:
    assert (
        plans_from_graph_query(
            GraphQueryPlan(intent=GraphIntent.INSTRUCTION_APPROVER_VIA_PAYMENT),
            mode="payments",
        )
        is None
    )
    via = plans_from_graph_query(
        GraphQueryPlan(
            intent=GraphIntent.INSTRUCTION_APPROVER_VIA_PAYMENT,
            payment_id="20260712-FICC-P-2",
        ),
        mode="payments",
    )
    assert via is not None

    assert (
        plans_from_graph_query(
            GraphQueryPlan(intent=GraphIntent.INSTRUCTION_APPROVAL),
            mode="instructions",
        )
        is None
    )
    approval = plans_from_graph_query(
        GraphQueryPlan(
            intent=GraphIntent.INSTRUCTION_APPROVAL,
            instruction_id="20260705-FICC-I-31",
        ),
        mode="instructions",
    )
    assert approval is not None

    assert (
        plans_from_graph_query(
            GraphQueryPlan(intent=GraphIntent.PAYMENT_APPROVAL),
            mode="payments",
        )
        is None
    )
    pay_approval = plans_from_graph_query(
        GraphQueryPlan(
            intent=GraphIntent.PAYMENT_APPROVAL,
            payment_id="20260712-FICC-P-2",
        ),
        mode="payments",
    )
    assert pay_approval is not None

    detail = plans_from_graph_query(
        GraphQueryPlan(
            intent=GraphIntent.INSTRUCTION_LOOKUP,
            instruction_id="20260705-FICC-I-31",
        ),
        mode="instructions",
    )
    assert detail is not None


def test_plans_payments_for_instruction_and_max() -> None:
    assert (
        plans_from_graph_query(
            GraphQueryPlan(intent=GraphIntent.PAYMENTS_FOR_INSTRUCTION),
            mode="payments",
        )
        is None
    )
    listed = plans_from_graph_query(
        GraphQueryPlan(
            intent=GraphIntent.PAYMENTS_FOR_INSTRUCTION,
            instruction_id="20260705-FICC-I-31",
            status="DRAFT",
        ),
        mode="payments",
    )
    assert listed is not None
    maxed = plans_from_graph_query(
        GraphQueryPlan(intent=GraphIntent.MAX_PAYMENTS_PER_INSTRUCTION),
        mode="payments",
    )
    assert maxed is not None


def test_plans_compliance_patterns() -> None:
    for pattern in ("mutual", "self", "subordinate", "duplicate_routes"):
        planned = plans_from_graph_query(
            GraphQueryPlan(
                intent=GraphIntent.INSTRUCTION_COMPLIANCE,
                compliance_pattern=pattern,  # type: ignore[arg-type]
                owning_lob="FICC" if pattern == "duplicate_routes" else None,
            ),
            mode="instructions",
        )
        assert planned is not None
    assert (
        plans_from_graph_query(
            GraphQueryPlan(intent=GraphIntent.INSTRUCTION_COMPLIANCE),
            mode="instructions",
        )
        is None
    )


def test_plans_inventory_and_rank() -> None:
    inventory = plans_from_graph_query(
        GraphQueryPlan(
            intent=GraphIntent.INSTRUCTION_INVENTORY,
            status="APPROVED",
            instruction_type="SINGLE_USE",
            owning_lob="FICC",
        ),
        mode="instructions",
        question="list approved single-use instructions for FICC",
    )
    assert inventory is not None

    assert (
        plans_from_graph_query(
            GraphQueryPlan(intent=GraphIntent.SECURITY_EVENT_RANK),
            mode="payments",
        )
        is None
    )
    for domain in ("payments", "instructions", "all"):
        ranked = plans_from_graph_query(
            GraphQueryPlan(
                intent=GraphIntent.SECURITY_EVENT_RANK,
                domain=domain,  # type: ignore[arg-type]
                time_window="today",
            ),
            mode="events",
        )
        assert ranked is not None


def test_plans_payment_and_instruction_aggregate() -> None:
    assert (
        plans_from_graph_query(
            GraphQueryPlan(intent=GraphIntent.PAYMENT_AGGREGATE, operation="sum"),
            mode="instructions",
        )
        is None
    )
    summed = plans_from_graph_query(
        GraphQueryPlan(
            intent=GraphIntent.PAYMENT_AGGREGATE,
            operation="sum",
            owning_lob="FICC",
            status="APPROVED",
            time_window="today",
            use_value_date=True,
        ),
        mode="payments",
        question="total",
    )
    assert summed is not None

    counted = plans_from_graph_query(
        GraphQueryPlan(
            intent=GraphIntent.PAYMENT_AGGREGATE,
            operation="count",
            time_window="week",
        ),
        mode="all",
        question="how many",
    )
    assert counted is not None

    assert (
        plans_from_graph_query(
            GraphQueryPlan(intent=GraphIntent.INSTRUCTION_AGGREGATE, operation="count"),
            mode="events",
        )
        is None
    )
    inst = plans_from_graph_query(
        GraphQueryPlan(
            intent=GraphIntent.INSTRUCTION_AGGREGATE,
            operation="count",
            status="SUBMITTED",
            instruction_type="RECURRING",
            owning_lob="FX",
            time_window="week",
        ),
        mode="instructions",
        question="count",
    )
    assert inst is not None


def test_plans_security_event_domain_branches() -> None:
    for domain in ("payments", "instructions", "all"):
        alerts = plans_from_graph_query(
            GraphQueryPlan(
                intent=GraphIntent.SECURITY_EVENT_AGGREGATE,
                operation="count",
                domain=domain,  # type: ignore[arg-type]
                severity="ALERT",
            ),
            mode="events",
            question="ALERT events today",
        )
        assert alerts is not None
        totals = plans_from_graph_query(
            GraphQueryPlan(
                intent=GraphIntent.SECURITY_EVENT_AGGREGATE,
                operation="count",
                domain=domain,  # type: ignore[arg-type]
            ),
            mode="all",
            question="how many security events",
        )
        assert totals is not None


def test_builder_wrappers_delegate() -> None:
    builder = CypherQueryBuilder()
    assert builder.alert_count_today()
    assert builder.instruction_versions("20260705-FICC-I-31")
    assert builder.payment_versions("20260712-FICC-P-2")
    assert builder.cross_entity_reciprocal_approval()
    assert builder.instruction_security_event_timeline("20260705-FICC-I-31")
    assert builder.instructions_created_by_user("mo-100")
    assert builder.facet_aggregate("group payments by status", mode="payments")


def test_payment_value_date_range_facets() -> None:
    assert is_analytics_question("group payments by status", mode="payments")
    dims = facet_dimensions(FacetEntity.PAYMENT)
    value_date = dims["value_date"]

    for question in (
        "payments with value date between 2026-01-01 and 2026-01-31",
        "payments with value date since 2026-01-01",
        "payments value date today",
        "payments value date this week",
        "payments value date this month",
        "payments value date this year",
        "payments value date last 14 days",
        "payments value date from 2026-02-01 to 2026-02-28",
        "payments value date 2026-03-15",
    ):
        clause = _date_range_clause(
            question, entity=FacetEntity.PAYMENT, dimension=value_date
        )
        assert clause is not None, question
        assert "value_date" in clause.cypher_clause or clause.field_label == "value date"


def test_facet_aggregate_queries_and_format() -> None:
    planned = facet_aggregate_queries("Can you group payments by status?", mode="payments")
    assert planned is not None
    spec = parse_facet_aggregate("Can you group payments by status?", mode="payments")
    assert spec is not None
    answer = format_facet_aggregate_answer(
        "Can you group payments by status?",
        [{"bucket": "DRAFT", "total": 2}, {"bucket": "APPROVED", "total": 5}],
        mode="payments",
    )
    assert answer is not None
    assert "DRAFT" in answer or "APPROVED" in answer or "Payment" in answer
