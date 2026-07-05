from __future__ import annotations

import pytest
from cypher_builder import (
    GraphIntent,
    GraphQueryPlan,
    parse_graph_query_plan,
    plan_graph_queries,
    plans_from_graph_query,
    validate_read_only_cypher,
)


def test_plan_graph_queries_alerts_today() -> None:
    planned = plan_graph_queries("How many ALERT events happened today?", mode="events")
    assert planned is not None
    assert any(label == "count" for label, _ in planned)


def test_plan_graph_queries_payment_alerts_today() -> None:
    planned = plan_graph_queries(
        "How many payment ALERT events happened today?",
        mode="events",
    )
    assert planned is not None
    assert planned[0][0] == "count"
    assert "e.payment_id IS NOT NULL" in planned[0][1]
    assert "severity = 'ALERT'" in planned[0][1]


def test_parse_graph_query_plan_from_json() -> None:
    plan = parse_graph_query_plan(
        '{"intent":"payment_aggregate","operation":"sum","domain":"payments","owning_lob":"FICC"}'
    )
    assert plan.intent == GraphIntent.PAYMENT_AGGREGATE
    assert plan.operation == "sum"
    assert plan.owning_lob == "FICC"


def test_plans_from_graph_query_security_event_aggregate() -> None:
    plan = GraphQueryPlan(
        intent=GraphIntent.SECURITY_EVENT_AGGREGATE,
        operation="count",
        time_window="today",
        domain="payments",
        severity="ALERT",
        denial=True,
    )
    planned = plans_from_graph_query(plan, mode="events", question="payment alerts today")
    assert planned is not None
    assert "count(e)" in planned[0][1]
    assert "severity = 'ALERT'" in planned[0][1] or "severity: 'ALERT'" in planned[0][1]


def test_plans_from_graph_query_security_event_total_count() -> None:
    plan = GraphQueryPlan(
        intent=GraphIntent.SECURITY_EVENT_AGGREGATE,
        operation="count",
        domain="all",
    )
    planned = plans_from_graph_query(
        plan,
        mode="events",
        question="How many security events are there in the system?",
    )
    assert planned is not None
    assert planned[0][0] == "security_event_count"
    assert "alert_count" in planned[0][1]
    assert "severity: 'ALERT'" not in planned[0][1]


def test_plan_graph_queries_total_security_events() -> None:
    planned = plan_graph_queries(
        "How many security events are there in the system?",
        mode="events",
    )
    assert planned is not None
    assert planned[0][0] == "security_event_count"
    assert "alert_count" in planned[0][1]
    assert "info_count" in planned[0][1]


def test_plan_graph_queries_instruction_group_by_status() -> None:
    planned = plan_graph_queries(
        "can you group them by status?",
        mode="instructions",
    )
    assert planned is not None
    assert planned[0][0] == "facet_aggregate"
    validate_read_only_cypher(planned[0][1])
    assert "count(DISTINCT i.instruction_id)" in planned[0][1]


def test_plan_graph_queries_payment_group_by_status() -> None:
    planned = plan_graph_queries(
        "Can you group payments by status?",
        mode="payments",
    )
    assert planned is not None
    assert planned[0][0] == "facet_aggregate"
    validate_read_only_cypher(planned[0][1])
    assert "count(DISTINCT pay.payment_id)" in planned[0][1]


def test_plan_graph_queries_alert_list() -> None:
    planned = plan_graph_queries(
        "Can you summarize all alerts with actor and action for me?",
        mode="events",
    )
    assert planned is not None
    assert planned[0][0] == "security_event_alert_list"
    assert "severity: 'ALERT'" in planned[0][1]
    assert "entity_type" in planned[0][1]
    assert "TARGETS]->(i:Instruction)" in planned[0][1]
    assert "actor_display" in planned[0][1]


def test_validate_read_only_cypher_rejects_writes() -> None:
    with pytest.raises(ValueError, match="disallowed write keyword"):
        validate_read_only_cypher("MATCH (n) CREATE (m) RETURN n LIMIT 1")


def test_payment_detail_query_includes_creator_and_approver() -> None:
    from cypher_builder.builder import CypherQueryBuilder

    planned = CypherQueryBuilder().payment_detail("20260704-FICC-P-1")
    assert planned[0][0] == "payment_detail"
    query = planned[0][1]
    assert "payment_id: '20260704-FICC-P-1'" in query
    assert "CREATED_PAYMENT" in query
    assert "APPROVED_PAYMENT" in query
    assert "creator_display" in query
