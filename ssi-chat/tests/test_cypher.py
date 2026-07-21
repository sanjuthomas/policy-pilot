from __future__ import annotations

from types import SimpleNamespace

import pytest
from chat_application.graph.cypher import (
    extract_entity_ids,
    extract_uuids,
    instruction_count_filters_from_question,
    instruction_id_from_list_payments_question,
    is_alert_ranking_question,
    is_approval_denial_alert_list_question,
    is_count_question,
    is_cross_entity_reciprocal_approval_question,
    is_instruction_mutual_approval_question,
    is_instruction_payment_count_list_question,
    is_instructions_without_payments_question,
    is_largest_payment_question,
    is_max_payments_per_instruction_question,
    is_payment_amount_threshold_question,
    is_payment_id_lookup_for_instruction_question,
    is_payment_list_by_status_question,
    is_payments_for_instruction_question,
    lob_filter_from_question,
    normalize_read_only_cypher,
    payment_amount_threshold_from_question,
    payment_status_filter_from_question,
    plan_graph_queries,
    ranking_period_label,
    records_to_rows,
    row_summary,
    validate_read_only_cypher,
)

VALID_QUERY = """MATCH (e:SecurityEvent)
RETURN e.event_id
LIMIT 10"""


class TestValidateReadOnlyCypher:
    def test_accepts_valid_query(self) -> None:
        validate_read_only_cypher(VALID_QUERY)

    def test_rejects_empty_query(self) -> None:
        with pytest.raises(ValueError, match="empty query"):
            validate_read_only_cypher("   ")

    def test_rejects_oversized_query(self) -> None:
        huge = "MATCH (n) RETURN n LIMIT 1 /* " + ("x" * 5000) + " */"
        with pytest.raises(ValueError, match="exceeds"):
            validate_read_only_cypher(huge)

    def test_rejects_multi_statement(self) -> None:
        with pytest.raises(ValueError, match="multiple statements"):
            validate_read_only_cypher("MATCH (n) RETURN n LIMIT 1; MATCH (m) RETURN m LIMIT 1")

    def test_rejects_non_read_start(self) -> None:
        with pytest.raises(ValueError, match="must begin with"):
            validate_read_only_cypher("CALL db.labels() YIELD label RETURN label LIMIT 1")

    def test_rejects_write_keywords(self) -> None:
        with pytest.raises(ValueError, match="disallowed write keyword 'CREATE'"):
            validate_read_only_cypher("MATCH (n) CREATE (m:Node) RETURN n LIMIT 1")

    def test_ignores_keywords_inside_string_literals(self) -> None:
        query = """MATCH (n {name: 'DELETE me'})
RETURN n.name
LIMIT 1"""
        validate_read_only_cypher(query)

    def test_strips_line_comments(self) -> None:
        query = """// CREATE would be bad if not a comment
MATCH (n)
RETURN n
LIMIT 1"""
        validate_read_only_cypher(query)

    def test_rejects_write_procedures(self) -> None:
        query = (
            'MATCH (n) CALL apoc.periodic.iterate("MATCH (m) RETURN m", '
            '"SET m.x=1", {}) YIELD batches RETURN n LIMIT 1'
        )
        with pytest.raises(ValueError, match="write-capable procedure"):
            validate_read_only_cypher(query)

    def test_requires_limit_clause(self) -> None:
        with pytest.raises(ValueError, match="must include a LIMIT"):
            validate_read_only_cypher("MATCH (n) RETURN n")


class TestNormalizeReadOnlyCypher:
    def test_empty_returns_empty(self) -> None:
        assert normalize_read_only_cypher("") == ""

    def test_leaves_query_with_limit_unchanged(self) -> None:
        assert normalize_read_only_cypher(VALID_QUERY) == VALID_QUERY

    def test_appends_limit_to_aggregate_without_limit(self) -> None:
        query = "MATCH (e:SecurityEvent) RETURN count(e) AS total"
        result = normalize_read_only_cypher(query)
        assert result.endswith("LIMIT 1")
        assert "count(e)" in result

    def test_strips_trailing_semicolon_before_limit(self) -> None:
        query = "MATCH (e) RETURN count(e) AS total;"
        result = normalize_read_only_cypher(query)
        assert result.endswith("LIMIT 1")
        assert ";" not in result.rstrip("LIMIT 1")


class TestPlanGraphQueries:
    def test_count_alerts_today(self) -> None:
        planned = plan_graph_queries("How many alerts today?", mode="events")
        assert planned is not None
        labels = [label for label, _ in planned]
        assert "count" in labels
        assert "details" in labels
        assert "date()" in planned[0][1]

    def test_count_instruction_policy_denials_week(self) -> None:
        planned = plan_graph_queries(
            "How many instruction policy denials happened this week?",
            mode="events",
        )
        assert planned is not None
        assert planned[0][0] == "count"
        assert "e.payment_id IS NULL" in planned[0][1]
        assert "e.severity = 'ALERT'" in planned[0][1]
        assert "P7D" in planned[0][1]

    def test_count_total_security_events(self) -> None:
        planned = plan_graph_queries(
            "How many security events are there in the system?",
            mode="events",
        )
        assert planned is not None
        assert planned[0][0] == "security_event_count"
        assert "alert_count" in planned[0][1]
        assert "info_count" in planned[0][1]
        assert "severity: 'ALERT'" not in planned[0][1]

    def test_summarize_all_alerts_list(self) -> None:
        planned = plan_graph_queries(
            "Can you summarize all alerts with actor and action for me?",
            mode="events",
        )
        assert planned is not None
        assert planned[0][0] == "security_event_alert_list"
        assert "entity_id" in planned[0][1]

    def test_group_alerts_by_lob(self) -> None:
        planned = plan_graph_queries(
            "Can you group alerts by LOB?",
            mode="events",
        )
        assert planned is not None
        assert planned[0][0] == "security_event_alert_group_by_lob"
        assert "INVOLVES_LOB" in planned[0][1]

    def test_group_security_events_by_lob(self) -> None:
        planned = plan_graph_queries(
            "Can you group security events by LOB?",
            mode="events",
        )
        assert planned is not None
        assert planned[0][0] == "security_event_group_by_lob"
        assert "INVOLVES_LOB" in planned[0][1]
        assert "event_count" in planned[0][1]

    def test_list_instruction_versions(self) -> None:
        planned = plan_graph_queries(
            "Can you list all versions of 20260704-DESK_RATES-I-84?",
            mode="instructions",
        )
        assert planned is not None
        assert planned[0][0] == "instruction_versions"
        assert "HAS_VERSION" in planned[0][1]

    def test_count_payment_alerts_this_week(self) -> None:
        planned = plan_graph_queries(
            "How many payment alerts in the past 7 days?",
            mode="events",
        )
        assert planned is not None
        assert "payment_id IS NOT NULL" in planned[0][1]
        assert "P7D" in planned[0][1]

    def test_ranking_denial_alerts(self) -> None:
        planned = plan_graph_queries(
            "Which users had the most policy denial alerts?",
            mode="events",
        )
        assert planned is not None
        assert planned[0][0] == "ranking"
        assert "alert_count" in planned[0][1]

    def test_instruction_subordinate_approver(self) -> None:
        planned = plan_graph_queries(
            "Does the approver directly report to the instruction creator?",
            mode="instructions",
        )
        assert planned is not None
        assert planned[0][0] == "hierarchy_violations"
        assert "REPORTS_TO" in planned[0][1]

    def test_instruction_approval_lookup_by_uuid(self) -> None:
        iid = "2846a7c0-4734-4626-bb58-13a966f935a1"
        planned = plan_graph_queries(
            f"Who approved instruction {iid}?",
            mode="instructions",
        )
        assert planned is not None
        assert planned[0][0] == "approval_lookup"
        assert iid in planned[0][1]
        assert "approveEvent.authorization_basis" in planned[0][1]

    def test_payment_approval_lookup_by_uuid(self) -> None:
        pid = "9b3251c9-d28e-4ad5-9bf4-dbc3c4fc13d8"
        planned = plan_graph_queries(
            f"Who approved the payment {pid}?",
            mode="payments",
        )
        assert planned is not None
        assert planned[0][0] == "payment_approval_lookup"
        assert pid in planned[0][1]
        assert "APPROVE" in planned[0][1]
        assert "APPROVE_PAYMENT" in planned[0][1]
        assert "has_approval" in planned[0][1]
        assert "Payment" in planned[0][1]
        assert f"PaymentVersion {{payment_id: '{pid}'}}" in planned[0][1]
        assert "approverUser" in planned[0][1]
        assert "approver_user_id IS NOT NULL" in planned[0][1]

    def test_payment_approval_lookup_bare_sequence_id(self) -> None:
        pid = "20260720-FICC-P-19"
        planned = plan_graph_queries(
            f"Who approved {pid}?",
            mode="events",
        )
        assert planned is not None
        assert planned[0][0] == "payment_approval_lookup"
        assert pid in planned[0][1]

    def test_instruction_approver_via_payment(self) -> None:
        pid = "20260629-FICC-P-1"
        question = (
            f"Can you tell me the approver of the instruction used by payment {pid}?"
        )
        planned = plan_graph_queries(question, mode="payments")
        assert planned is not None
        assert planned[0][0] == "instruction_approver_via_payment"
        assert pid in planned[0][1]
        assert "HAS_PAYMENT" in planned[0][1]
        assert "approver_display" in planned[0][1]
        assert "APPROVE_PAYMENT" not in planned[0][1]

        assert plan_graph_queries(question, mode="events") is not None
        assert plan_graph_queries(question, mode="events")[0][0] == "instruction_approver_via_payment"

    def test_max_payments_per_instruction(self) -> None:
        planned = plan_graph_queries(
            "Which instruction has the maximum number of payments?",
            mode="payments",
        )
        assert planned is not None
        assert planned[0][0] == "max_payments_per_instruction"
        assert "HAS_PAYMENT" in planned[0][1]
        assert "count(DISTINCT pay.payment_id)" in planned[0][1]
        assert "collect(DISTINCT pay)" in planned[0][1]
        assert "creator_display" in planned[0][1]

    def test_payments_for_instruction(self) -> None:
        iid = "3bcb9b9a-9415-44ce-b707-4cc4c8281bb9"
        planned = plan_graph_queries(
            f"Can you list the payments for instruction {iid}?",
            mode="payments",
        )
        assert planned is not None
        assert planned[0][0] == "payments_for_instruction"
        assert iid in planned[0][1]
        assert "HAS_PAYMENT" in planned[0][1]

    def test_payment_id_for_used_instruction_with_typo(self) -> None:
        question = (
            "Can you give me the payment ID associated with a used instruction 0260704-FICC-I-1?"
        )
        assert is_payments_for_instruction_question(question)
        assert is_payment_id_lookup_for_instruction_question(question)
        iid = instruction_id_from_list_payments_question(question)
        assert iid == "20260704-FICC-I-1"
        planned = plan_graph_queries(question, mode="payments")
        assert planned is not None
        assert planned[0][0] == "payments_for_instruction"
        assert "20260704-FICC-I-1" in planned[0][1]

    def test_payments_for_instruction_approved_filter(self) -> None:
        iid = "3bcb9b9a-9415-44ce-b707-4cc4c8281bb9"
        planned = plan_graph_queries(
            f"List all APPROVED payments for instruction {iid}.",
            mode="payments",
        )
        assert planned is not None
        assert "p.status = 'APPROVED'" in planned[0][1]

    def test_largest_payment_today(self) -> None:
        question = "What was the largest payment today?"
        assert is_largest_payment_question(question)
        planned = plan_graph_queries(question, mode="payments")
        assert planned is not None
        assert planned[0][0] == "largest_payment"
        assert "max(pv.version_number)" in planned[0][1]
        assert "ORDER BY p.amount DESC" in planned[0][1]
        assert "date(datetime(p.updated_at)) = date()" in planned[0][1]

    def test_payments_above_amount_threshold(self) -> None:
        question = "do we have any payments with >$25M amount?"
        assert is_payment_amount_threshold_question(question)
        assert payment_amount_threshold_from_question(question) == 25_000_000
        planned = plan_graph_queries(question, mode="payments")
        assert planned is not None
        assert planned[0][0] == "payments_above_amount"
        assert "p.amount > 25000000" in planned[0][1]
        assert "max(pv.version_number)" in planned[0][1]

    def test_payment_total_amount_ficc_today(self) -> None:
        planned = plan_graph_queries(
            "What is the total approved payment amount for FICC today?",
            mode="payments",
        )
        assert planned is not None
        assert planned[0][0] == "payment_total_amount"
        query = planned[0][1]
        assert "p.status = 'APPROVED'" in query
        assert "p.owning_lob = 'FICC'" in query
        assert "sum(p.amount)" in query
        assert "count(DISTINCT pay.payment_id)" in query
        assert "date(datetime(p.updated_at)) = date()" in query

    def test_payment_count_all_payments(self) -> None:
        planned = plan_graph_queries(
            "How many payments do we have?",
            mode="payments",
        )
        assert planned is not None
        assert planned[0][0] == "payment_count"
        assert "count(DISTINCT pay.payment_id) AS total" in planned[0][1]
        assert "count(DISTINCT pay) AS total" not in planned[0][1]

    def test_payment_group_by_status(self) -> None:
        planned = plan_graph_queries(
            "Can you group payments by status?",
            mode="payments",
        )
        assert planned is not None
        assert planned[0][0] == "facet_aggregate"
        query = planned[0][1]
        assert "count(DISTINCT pay.payment_id) AS total" in query
        assert "RETURN bucket, total" in query

    def test_payment_group_them_by_status(self) -> None:
        planned = plan_graph_queries(
            "can you group them by status?",
            mode="payments",
        )
        assert planned is not None
        assert planned[0][0] == "facet_aggregate"

    def test_payment_count_approved_ficc_today(self) -> None:
        planned = plan_graph_queries(
            "How many payments were approved today for FICC?",
            mode="payments",
        )
        assert planned is not None
        assert planned[0][0] == "payment_count"
        query = planned[0][1]
        assert "p.status = 'APPROVED'" in query
        assert "p.owning_lob = 'FICC'" in query
        assert "date(datetime(p.updated_at)) = date()" in query
        assert "value_date" not in query.split("WHERE", 1)[1].split("RETURN", 1)[0]

    def test_payment_count_todays_value_date(self) -> None:
        planned = plan_graph_queries(
            "How many payments do we have in the system with today's value date?",
            mode="payments",
        )
        assert planned is not None
        assert planned[0][0] == "payment_count"
        query = planned[0][1]
        assert "value_date STARTS WITH toString(date())" in query
        assert "updated_at" not in query
        assert "count(DISTINCT pay.payment_id) AS total" in query

    def test_instruction_count_in_store(self) -> None:
        planned = plan_graph_queries(
            "How many instructions are there in the store?",
            mode="instructions",
        )
        assert planned is not None
        assert planned[0][0] == "count"
        assert "count(DISTINCT i.instruction_id)" in planned[0][1]
        assert "HAS_VERSION" in planned[0][1]
        assert "max(iv.version_number)" in planned[0][1]

    def test_instruction_group_by_status(self) -> None:
        planned = plan_graph_queries(
            "Can you group instructions by status?",
            mode="instructions",
        )
        assert planned is not None
        assert planned[0][0] == "facet_aggregate"
        query = planned[0][1]
        assert "count(DISTINCT i.instruction_id) AS total" in query
        assert "RETURN bucket, total" in query
        assert "LIMIT 200" not in query

    def test_instruction_group_them_by_status(self) -> None:
        planned = plan_graph_queries(
            "can you group them by status?",
            mode="instructions",
        )
        assert planned is not None
        assert planned[0][0] == "facet_aggregate"

    def test_instruction_count_submitted(self) -> None:
        planned = plan_graph_queries(
            "How many instructions are submitted?",
            mode="instructions",
        )
        assert planned is not None
        assert "v.status = 'SUBMITTED'" in planned[0][1]

    def test_instruction_count_single_use_natural_language(self) -> None:
        assert instruction_count_filters_from_question(
            "How many single use instructions are there?"
        ) == (None, "SINGLE_USE")
        planned = plan_graph_queries(
            "How many single use instructions are there?",
            mode="instructions",
        )
        assert planned is not None
        assert "v.instruction_type = 'SINGLE_USE'" in planned[0][1]
        assert "v.status = 'SINGLE_USE'" not in planned[0][1]

    def test_instruction_count_single_use_by_type(self) -> None:
        assert instruction_count_filters_from_question(
            "How many single use instructions were created?"
        ) == (None, "SINGLE_USE")
        planned = plan_graph_queries(
            "How many single use instructions were created?",
            mode="instructions",
        )
        assert planned is not None
        assert "v.instruction_type = 'SINGLE_USE'" in planned[0][1]
        assert "v.status = 'SINGLE_USE'" not in planned[0][1]

    def test_instruction_count_per_lob(self) -> None:
        planned = plan_graph_queries(
            "How many instructions exist per LOB?",
            mode="instructions",
        )
        assert planned is not None
        assert planned[0][0] == "facet_aggregate"
        assert "count(DISTINCT i.instruction_id)" in planned[0][1]

    def test_lob_filter_for_ficc_phrase(self) -> None:
        assert lob_filter_from_question(
            "What is the total approved payment amount for FICC today?"
        ) == "FICC"

    def test_lob_filter_desk_rates(self) -> None:
        assert lob_filter_from_question(
            "Who can create payments for DESK_RATES?"
        ) == "DESK_RATES"
        assert lob_filter_from_question("Who covers LOB DESK_RATES?") == "DESK_RATES"

    def test_non_count_question_returns_none(self) -> None:
        assert plan_graph_queries("List recent events", mode="events") is None


class TestExtractUuids:
    def test_extracts_unique_in_order(self) -> None:
        u1 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        u2 = "11111111-2222-3333-4444-555555555555"
        text = f"event {u1} and again {u1} then {u2}"
        assert extract_uuids(text) == [u1, u2]

    def test_empty_when_no_uuids(self) -> None:
        assert extract_uuids("no ids here") == []


class TestIsCountQuestion:
    @pytest.mark.parametrize(
        "question",
        [
            "How many alerts today?",
            "What is the number of denials?",
            "Count of payment events",
            "Total number of instructions",
        ],
    )
    def test_detects_count_phrases(self, question: str) -> None:
        assert is_count_question(question) is True

    def test_non_count_question(self) -> None:
        assert is_count_question("Who approved this instruction?") is False


class TestIsPaymentAmountThresholdQuestion:
    def test_detects_gt_dollar_million(self) -> None:
        question = "do we have any payments with >$25M amount?"
        assert is_payment_amount_threshold_question(question)
        assert payment_amount_threshold_from_question(question) == 25_000_000

    def test_detects_over_million_phrase(self) -> None:
        question = "Show payments over $10M approved this week."
        assert is_payment_amount_threshold_question(question)
        assert payment_amount_threshold_from_question(question) == 10_000_000

    def test_excludes_total_amount(self) -> None:
        assert not is_payment_amount_threshold_question(
            "What is the total approved payment amount for FICC today?"
        )


class TestIsLargestPaymentQuestion:
    def test_detects_largest_payment_today(self) -> None:
        assert is_largest_payment_question("What was the largest payment today?")

    def test_detects_largest_approved_week_by_lob(self) -> None:
        assert is_largest_payment_question(
            "What are the largest approved payments this week by LOB?"
        )

    def test_excludes_max_payments_per_instruction(self) -> None:
        assert not is_largest_payment_question(
            "Which instruction has the maximum number of payments?"
        )

    def test_excludes_payment_total(self) -> None:
        assert not is_largest_payment_question(
            "What is the total approved payment amount for FICC today?"
        )

    def test_excludes_user_ranking(self) -> None:
        assert not is_largest_payment_question("Which user has the most payments?")

    def test_allows_who_created_max_amount(self) -> None:
        assert is_largest_payment_question(
            "Who created the payment with the maximum dollar value?"
        )
        planned = plan_graph_queries(
            "Who created the payment with the maximum dollar value?",
            mode="payments",
        )
        assert planned is not None
        assert planned[0][0] == "largest_payment"

    def test_superlative_routes_to_facet(self) -> None:
        planned = plan_graph_queries(
            "Who created the most payments?",
            mode="payments",
        )
        assert planned is not None
        assert planned[0][0] == "facet_aggregate"
        assert "LIMIT 1" in planned[0][1]


class TestIsMaxPaymentsPerInstructionQuestion:
    def test_detects_max_payments_question(self) -> None:
        assert is_max_payments_per_instruction_question(
            "Which instruction has the maximum number of payments?"
        )

    def test_requires_instruction_and_payment(self) -> None:
        assert not is_max_payments_per_instruction_question("Which user has the most payments?")


class TestIsPaymentsForInstructionQuestion:
    def test_detects_list_payments_question(self) -> None:
        iid = "3bcb9b9a-9415-44ce-b707-4cc4c8281bb9"
        assert is_payments_for_instruction_question(
            f"Can you list the payments for instruction {iid}?"
        )

    def test_extracts_instruction_uuid(self) -> None:
        iid = "3bcb9b9a-9415-44ce-b707-4cc4c8281bb9"
        assert instruction_id_from_list_payments_question(
            f"List payments for instruction {iid}"
        ) == iid

    def test_extracts_sequence_instruction_id(self) -> None:
        iid = "20260627-FICC-I-1"
        assert instruction_id_from_list_payments_question(
            f"List payments for instruction {iid}"
        ) == iid
        assert is_payments_for_instruction_question(
            f"Can you list the payments for instruction {iid}?"
        )

    def test_normalizes_seven_digit_instruction_id_typo(self) -> None:
        typo = "0260704-FICC-I-1"
        expected = "20260704-FICC-I-1"
        question = f"payment ID for instruction {typo}"
        assert instruction_id_from_list_payments_question(question) == expected
        assert extract_entity_ids(question) == [expected]

    def test_extract_entity_ids_includes_sequence_and_uuid(self) -> None:
        seq = "20260627-FX-P-2"
        uid = "3bcb9b9a-9415-44ce-b707-4cc4c8281bb9"
        text = f"payment {seq} and instruction {uid}"
        assert extract_entity_ids(text) == [seq, uid]

    def test_payment_status_filter(self) -> None:
        assert payment_status_filter_from_question("List APPROVED payments") == "APPROVED"
        assert payment_status_filter_from_question("List payments") is None


class TestIsAlertRankingQuestion:
    def test_detects_top_denial_user_question(self) -> None:
        assert is_alert_ranking_question(
            "Which user triggered the most policy denial alerts this week?",
            mode="events",
        )

    def test_not_in_payments_mode(self) -> None:
        assert not is_alert_ranking_question(
            "Which user triggered the most policy denial alerts this week?",
            mode="payments",
        )

    def test_ranking_period_label(self) -> None:
        assert ranking_period_label("How many alerts today?") == "today"
        assert ranking_period_label("Most alerts this week?") == "this week"
        assert ranking_period_label("Most alerts ever?") == "all time"


class TestRecordsToRows:
    def test_converts_neo4j_like_records(self) -> None:
        node = SimpleNamespace(items=lambda: [("event_id", "evt-1"), ("action", "APPROVE")])

        class Record:
            def keys(self):
                return ["event", "instruction_id"]

            def __getitem__(self, key):
                return {"event": node, "instruction_id": "inst-1"}[key]

        rows = records_to_rows([Record()])
        assert rows == [{"event": {"event_id": "evt-1", "action": "APPROVE"}, "instruction_id": "inst-1"}]

    def test_handles_list_of_nodes(self) -> None:
        child = SimpleNamespace(items=lambda: [("user_id", "u-1")])

        class Record:
            def keys(self):
                return ["users"]

            def __getitem__(self, key):
                return {"users": [child]}[key]

        rows = records_to_rows([Record()])
        assert rows[0]["users"] == [{"user_id": "u-1"}]


class TestRowSummary:
    def test_summarizes_nested_event_node(self) -> None:
        row = {
            "event": {
                "event_id": "evt-1",
                "action": "APPROVE",
                "severity": "INFO",
                "message": "Approved",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        }
        summary = row_summary(row)
        assert "APPROVE" in summary
        assert "Approved" in summary

    def test_fallback_key_value_summary(self) -> None:
        summary = row_summary({"user_id": "fx-201", "alert_count": 5})
        assert "user_id=fx-201" in summary
        assert "alert_count=5" in summary


class TestDownvoteRegressionQueries:
    def test_approval_denial_alert_list_filters_approve_actions(self) -> None:
        question = "Can you list all approval denial alerts?"
        assert is_approval_denial_alert_list_question(question)
        planned = plan_graph_queries(question, mode="events")
        assert planned is not None
        assert planned[0][0] == "security_event_alert_list"
        assert "e.action IN ['APPROVE', 'APPROVE_PAYMENT']" in planned[0][1]

    def test_payment_list_submitted_state(self) -> None:
        question = "Can you list payments in SUBMITTED state?"
        assert is_payment_list_by_status_question(question, mode="payments")
        planned = plan_graph_queries(question, mode="payments")
        assert planned is not None
        assert planned[0][0] == "payment_list"
        assert "SUBMITTED" in planned[0][1]

    def test_payment_list_without_status(self) -> None:
        from cypher_builder import is_payment_list_question

        question = "Can you list those payments created this week?"
        assert is_payment_list_question(question, mode="payments")
        planned = plan_graph_queries(question, mode="payments")
        assert planned is not None
        assert planned[0][0] == "payment_list"
        assert "duration('P7D')" in planned[0][1]

    def test_instruction_payment_count_list(self) -> None:
        question = "Can you list instructions and count of payments for each instruction?"
        assert is_instruction_payment_count_list_question(question, mode="instructions")
        planned = plan_graph_queries(question, mode="instructions")
        assert planned is not None
        assert planned[0][0] == "instruction_payment_counts"

    def test_instructions_without_payments_count(self) -> None:
        question = "How many instructions have no payment?"
        assert is_instructions_without_payments_question(question, mode="instructions")
        planned = plan_graph_queries(question, mode="instructions")
        assert planned is not None
        assert planned[0][0] == "instructions_without_payments"
        assert "count(i) AS total" in planned[0][1]

    def test_instructions_without_payments_list(self) -> None:
        question = "Can you list all instructions without any payments?"
        assert is_instructions_without_payments_question(question, mode="instructions")
        planned = plan_graph_queries(question, mode="instructions")
        assert planned is not None
        assert planned[0][0] == "instructions_without_payments_list"
        assert "instruction_id AS instruction_id" in planned[0][1]
        assert "HAS_PAYMENT" in planned[0][1]

    def test_mutual_approval_planned_graph(self) -> None:
        question = "Are there users approving each other's instructions?"
        assert is_instruction_mutual_approval_question(question)
        planned = plan_graph_queries(question, mode="instructions")
        assert planned is not None
        assert planned[0][0] == "mutual_approval"

    def test_cross_entity_reciprocal_approval_planned_graph(self) -> None:
        question = (
            "Are there cases where one user approved another user's instruction, "
            "and that same other user created a payment on that instruction that "
            "the first user then approved?"
        )
        assert is_cross_entity_reciprocal_approval_question(question)
        assert not is_instruction_mutual_approval_question(question)
        planned = plan_graph_queries(question, mode="instructions")
        assert planned is not None
        assert planned[0][0] == "cross_entity_reciprocal_approval"
        assert "i.instruction_id AS instruction_id" in planned[0][1]
        assert "pay.payment_id AS payment_id" in planned[0][1]

    def test_cross_entity_reciprocal_approval_events_mode(self) -> None:
        question = (
            "Are there cases where one user approved another user's instruction, "
            "and that same other user created a payment on that instruction that "
            "the first user then approved?"
        )
        planned = plan_graph_queries(question, mode="events")
        assert planned is not None
        assert planned[0][0] == "cross_entity_reciprocal_approval"

