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


def test_plans_from_graph_query_rejects_low_confidence() -> None:
    from cypher_builder import MIN_GRAPH_QUERY_PLAN_CONFIDENCE

    plan = GraphQueryPlan(
        intent=GraphIntent.SECURITY_EVENT_AGGREGATE,
        operation="count",
        time_window="today",
        confidence=0.1,
    )
    assert plan.confidence < MIN_GRAPH_QUERY_PLAN_CONFIDENCE
    assert plans_from_graph_query(plan, mode="events", question="???") is None


def test_plans_from_graph_query_accepts_high_confidence() -> None:
    plan = GraphQueryPlan(
        intent=GraphIntent.SECURITY_EVENT_AGGREGATE,
        operation="count",
        time_window="today",
        domain="payments",
        severity="ALERT",
        denial=True,
        confidence=0.95,
    )
    planned = plans_from_graph_query(plan, mode="events", question="payment alerts today")
    assert planned is not None
    assert "count(e)" in planned[0][1]


def test_plans_from_graph_query_allows_missing_confidence() -> None:
    """Legacy/manual plans without confidence still render Cypher."""
    plan = GraphQueryPlan(
        intent=GraphIntent.SECURITY_EVENT_AGGREGATE,
        operation="count",
        domain="all",
        confidence=None,
    )
    assert plans_from_graph_query(plan, mode="events") is not None


def test_instruction_type_synonym_taxonomy() -> None:
    from cypher_builder import (
        canonicalize_instruction_type,
        instruction_type_filter_from_question,
        plan_graph_queries,
    )

    for phrase in (
        "SINGLE_USE",
        "single use",
        "single-use",
        "single_use",
        "singleuse",
        "one time use",
        "one-time",
        "onetime use",
    ):
        assert instruction_type_filter_from_question(phrase) == "SINGLE_USE"
        assert canonicalize_instruction_type(phrase) == "SINGLE_USE"

    for phrase in (
        "STANDING",
        "standing",
        "recurring",
        "open-ended",
        "evergreen",
        "ever green",
        "ever-green",
    ):
        assert instruction_type_filter_from_question(phrase) == "STANDING"
        assert canonicalize_instruction_type(phrase) == "STANDING"

    planned = plan_graph_queries(
        "Can you show me the approved SINGLE USE instructions in the system?",
        mode="instructions",
    )
    assert planned is not None
    assert planned[0][0] == "instruction_inventory"
    assert "instruction_type: 'SINGLE_USE'" in planned[0][1]


def test_plans_from_lookup_without_id_remaps_to_inventory() -> None:
    """Gemini mislabels list questions as instruction_lookup; still build inventory Cypher."""
    plan = GraphQueryPlan(
        intent=GraphIntent.INSTRUCTION_LOOKUP,
        operation="list",
        domain="instructions",
        status="APPROVED",
        instruction_type="SINGLE_USE",
        confidence=1.0,
    )
    planned = plans_from_graph_query(
        plan,
        mode="instructions",
        question="Can you show me the approved single-use instructions in the system?",
    )
    assert planned is not None
    assert planned[0][0] == "instruction_inventory"
    assert "instruction_type: 'SINGLE_USE'" in planned[0][1]


def test_plans_from_lookup_without_filters_still_none() -> None:
    plan = GraphQueryPlan(
        intent=GraphIntent.INSTRUCTION_LOOKUP,
        operation="list",
        domain="instructions",
    )
    assert plans_from_graph_query(plan, mode="instructions", question="show me something") is None


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
    assert "[:FOR]->(v:InstructionVersion)" in planned[0][1]
    assert "e.instruction_id" in planned[0][1]
    assert "actor_display" in planned[0][1]


def test_alert_list_filters_domain_and_time_from_question() -> None:
    from cypher_builder import (
        security_event_domain_from_question,
        security_event_time_filter_from_question,
    )

    assert security_event_domain_from_question("alerts for payments") == "payments"
    assert security_event_domain_from_question("alerts for instructions") == "instructions"
    assert "P7D" in security_event_time_filter_from_question("denial events this week")

    payments = plan_graph_queries(
        "can you list all alerts for payments?",
        mode="events",
    )
    assert payments is not None
    assert "AND e.payment_id IS NOT NULL" in payments[0][1]
    assert "AND e.payment_id IS NULL" not in payments[0][1]

    instructions = plan_graph_queries(
        "can you list all alerts for instructions?",
        mode="events",
    )
    assert instructions is not None
    assert "AND e.payment_id IS NULL" in instructions[0][1]

    denials = plan_graph_queries(
        "Can you list all instruction denial events for this week?",
        mode="instructions",
    )
    assert denials is not None
    assert denials[0][0] == "security_event_alert_list"
    assert "AND e.payment_id IS NULL" in denials[0][1]
    assert "P7D" in denials[0][1]


def test_instruction_policy_denial_count_plans_alert_cypher() -> None:
    """'denials' without the word 'alert' must still plan instruction ALERT counts."""
    planned = plan_graph_queries(
        "How many instruction policy denials happened this week?",
        mode="events",
    )
    assert planned is not None
    assert planned[0][0] == "count"
    assert "e.severity = 'ALERT'" in planned[0][1]
    assert "e.payment_id IS NULL" in planned[0][1]
    assert "P7D" in planned[0][1]


def test_alert_list_entity_id_prefers_security_event_property() -> None:
    """ALERT list must resolve entity id from SecurityEvent even without FOR."""
    from cypher_builder.query_engine import _ALERT_LIST_ENTITY_ID, _security_event_alert_list_queries

    assert "e.instruction_id" in _ALERT_LIST_ENTITY_ID
    queries = _security_event_alert_list_queries(time_filter="", domain="all")
    assert queries[0][0] == "security_event_alert_list"
    assert "e.instruction_id" in queries[0][1]


def test_plan_graph_queries_alert_group_by_lob() -> None:
    planned = plan_graph_queries(
        "Can you group alerts by LOB?",
        mode="events",
    )
    assert planned is not None
    assert planned[0][0] == "security_event_alert_group_by_lob"
    validate_read_only_cypher(planned[0][1])
    assert "INVOLVES_LOB" in planned[0][1]
    assert "alert_count" in planned[0][1]
    assert "severity: 'ALERT'" in planned[0][1]


def test_plan_graph_queries_security_events_group_by_lob() -> None:
    planned = plan_graph_queries(
        "Can you group security events by LOB?",
        mode="events",
    )
    assert planned is not None
    assert planned[0][0] == "security_event_group_by_lob"
    validate_read_only_cypher(planned[0][1])
    assert "INVOLVES_LOB" in planned[0][1]
    assert "event_count" in planned[0][1]
    assert "severity: 'ALERT'" not in planned[0][1]


def test_plan_graph_queries_instruction_versions_list() -> None:
    planned = plan_graph_queries(
        "Can you list all versions of 20260704-DESK_RATES-I-84?",
        mode="instructions",
    )
    assert planned is not None
    assert planned[0][0] == "instruction_versions"
    validate_read_only_cypher(planned[0][1])
    assert "HAS_VERSION" in planned[0][1]
    assert "CURRENT" not in planned[0][1]
    assert "20260704-DESK_RATES-I-84" in planned[0][1]


def test_plan_graph_queries_payment_versions_list() -> None:
    planned = plan_graph_queries(
        "Show version history for 20260704-FICC-P-1",
        mode="payments",
    )
    assert planned is not None
    assert planned[0][0] == "payment_versions"
    validate_read_only_cypher(planned[0][1])
    assert "HAS_VERSION" in planned[0][1]
    assert "CREATED_PV" in planned[0][1]


def test_validate_read_only_cypher_rejects_writes() -> None:
    with pytest.raises(ValueError, match="disallowed write keyword"):
        validate_read_only_cypher("MATCH (n) CREATE (m) RETURN n LIMIT 1")


def test_payment_detail_query_includes_creator_and_approver() -> None:
    from cypher_builder.builder import CypherQueryBuilder

    planned = CypherQueryBuilder().payment_detail("20260704-FICC-P-1")
    assert planned[0][0] == "payment_detail"
    query = planned[0][1]
    assert "payment_id: '20260704-FICC-P-1'" in query
    assert "CREATED_PV" in query
    assert "APPROVED_PV" in query
    assert "creator_display" in query


def test_lookup_queries_escape_cypher_literals() -> None:
    from cypher_builder.builder import CypherQueryBuilder

    builder = CypherQueryBuilder()
    nasty_instruction = "2026-O'Brien-I-1"
    nasty_payment = "2026-O'Brien-P-1"
    nasty_status = "APPROVED' OR '1'='1"

    approval = builder.instruction_approval_lookup(nasty_instruction)[0][1]
    assert "instruction_id: '2026-O\\'Brien-I-1'" in approval

    via_payment = builder.instruction_approver_via_payment(nasty_payment)[0][1]
    assert "payment_id: '2026-O\\'Brien-P-1'" in via_payment

    payments = builder.payments_for_instruction(
        nasty_instruction, status=nasty_status
    )[0][1]
    assert "instruction_id: '2026-O\\'Brien-I-1'" in payments
    assert "p.status = 'APPROVED\\' OR \\'1\\'=\\'1'" in payments
    validate_read_only_cypher(approval)
    validate_read_only_cypher(via_payment)
    validate_read_only_cypher(payments)


def test_instruction_mutual_approval_query_deduplicates_pairs() -> None:
    from cypher_builder.builder import CypherQueryBuilder

    query = CypherQueryBuilder().instruction_mutual_approval()[0][1]
    assert "a.user_id < b.user_id" in query
    assert "a.user_id <> b.user_id" not in query
