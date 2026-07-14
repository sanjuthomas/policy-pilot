"""Shared detector → formatter dispatch for Neo4j-direct and full-RAG synthesize.

Both paths must use this module so the same planned labels + question produce
the same deterministic answer when graph rows match (see issue #12).
"""

from __future__ import annotations

from typing import Any

from chat_application.graph.cypher import (
    format_facet_aggregate_answer,
    instruction_id_from_list_payments_question,
    is_alert_ranking_question,
    is_analytics_question,
    is_count_question,
    is_cross_entity_reciprocal_approval_question,
    is_instruction_count_aggregate_question,
    is_instruction_mutual_approval_question,
    is_instruction_payment_count_list_question,
    is_instruction_versions_list_question,
    is_instructions_without_payments_question,
    is_largest_payment_question,
    is_max_payments_per_instruction_question,
    is_payment_amount_threshold_question,
    is_payment_count_aggregate_question,
    is_payment_list_question,
    is_payment_total_amount_question,
    is_payment_versions_list_question,
    is_payments_for_instruction_question,
    is_security_event_alert_count_question,
    is_security_event_alert_list_question,
    is_security_event_count_aggregate_question,
    is_security_event_group_by_lob_question,
)
from chat_application.models import SearchMode


def format_planned_graph_answer(
    question: str,
    *,
    mode: SearchMode,
    planned: list[tuple[str, str]],
    rows: list[dict[str, Any]],
) -> str | None:
    """Map planned Cypher labels + detectors onto deterministic formatters."""
    labels = {label for label, _ in planned}

    if "ranking" in labels and is_alert_ranking_question(question, mode=mode):
        from chat_application.rag import _format_alert_ranking_answer

        return _format_alert_ranking_answer(question, rows)

    if "facet_aggregate" in labels and is_analytics_question(question, mode=mode):
        return format_facet_aggregate_answer(question, rows, mode=mode)

    if "count" in labels and is_instruction_count_aggregate_question(question):
        from chat_application.rag import _format_instruction_count_aggregate_answer

        return _format_instruction_count_aggregate_answer(question, rows)

    if "payment_count" in labels and is_payment_count_aggregate_question(question):
        from chat_application.rag import _format_payment_count_aggregate_answer

        return _format_payment_count_aggregate_answer(question, rows)

    if "payment_total_amount" in labels and is_payment_total_amount_question(question):
        from chat_application.rag import _format_payment_total_amount_answer

        return _format_payment_total_amount_answer(question, rows)

    if "payment_list" in labels and is_payment_list_question(question, mode=mode):
        from chat_application.rag import _format_payment_list_answer

        return _format_payment_list_answer(question, rows)

    if "instruction_payment_counts" in labels and is_instruction_payment_count_list_question(
        question, mode=mode
    ):
        from chat_application.formatting.neo4j import (
            format_instruction_payment_counts_table,
        )

        return format_instruction_payment_counts_table(question, rows)

    if "instructions_without_payments_list" in labels and is_instructions_without_payments_question(
        question, mode=mode
    ):
        from chat_application.formatting.neo4j import (
            format_instructions_without_payments_table,
        )

        return format_instructions_without_payments_table(question, rows)

    if "instructions_without_payments" in labels and is_instructions_without_payments_question(
        question, mode=mode
    ):
        total = int(rows[0].get("total") or 0) if rows else 0
        return f"There are {total} instruction(s) with no payments."

    if "cross_entity_reciprocal_approval" in labels and is_cross_entity_reciprocal_approval_question(
        question
    ):
        from chat_application.formatting.neo4j import (
            format_cross_entity_reciprocal_approval,
        )

        return format_cross_entity_reciprocal_approval(question, rows)

    if "mutual_approval" in labels and is_instruction_mutual_approval_question(question):
        from chat_application.formatting.neo4j import format_instruction_mutual_approval

        return format_instruction_mutual_approval(question, rows)

    if "max_payments_per_instruction" in labels and is_max_payments_per_instruction_question(
        question
    ):
        from chat_application.rag import _format_max_payments_per_instruction_answer

        return _format_max_payments_per_instruction_answer(rows)

    if "largest_payment" in labels and is_largest_payment_question(question):
        from chat_application.rag import _format_largest_payment_answer

        return _format_largest_payment_answer(question, rows)

    if "payments_above_amount" in labels and is_payment_amount_threshold_question(question):
        from chat_application.rag import _format_payments_above_amount_answer

        return _format_payments_above_amount_answer(question, rows)

    if "payments_for_instruction" in labels and is_payments_for_instruction_question(question):
        from chat_application.rag import _format_payments_for_instruction_answer

        instruction_id = instruction_id_from_list_payments_question(question)
        if instruction_id:
            return _format_payments_for_instruction_answer(instruction_id, rows, question=question)

    if "instruction_versions" in labels and is_instruction_versions_list_question(
        question, mode=mode
    ):
        from chat_application.formatting.neo4j import format_instruction_versions_table

        return format_instruction_versions_table(question, rows)

    # Inventory lists from LLM or predefined plans — format by label, not wording.
    if "instruction_inventory" in labels or "instructions_by_creator" in labels:
        from chat_application.formatting.neo4j import format_instruction_inventory_table

        return format_instruction_inventory_table(question, rows)

    if "payment_versions" in labels and is_payment_versions_list_question(question, mode=mode):
        from chat_application.formatting.neo4j import format_payment_versions_table

        return format_payment_versions_table(question, rows)

    if "payment_detail" in labels:
        from chat_application.formatting.neo4j import format_payment_detail_by_id

        return format_payment_detail_by_id(question, rows)

    if "approval_lookup" in labels or "payment_approval_lookup" in labels:
        from chat_application.formatting.neo4j import format_approval_lookup_answer

        row = rows[0] if rows else None
        if not row:
            return None
        return format_approval_lookup_answer(row)

    if "security_event_count" in labels and is_security_event_count_aggregate_question(
        question, mode=mode
    ):
        from chat_application.rag import _format_security_event_count_aggregate_answer

        count_rows = [
            row
            for row in rows
            if row.get("total") is not None and row.get("alert_count") is not None
        ]
        return _format_security_event_count_aggregate_answer(question, count_rows or rows)

    if "security_event_alert_list" in labels and is_security_event_alert_list_question(
        question, mode=mode
    ):
        from chat_application.formatting.neo4j import format_security_event_alert_list

        return format_security_event_alert_list(question, rows)

    if (
        (
            "security_event_alert_group_by_lob" in labels
            or "security_event_group_by_lob" in labels
        )
        and is_security_event_group_by_lob_question(question, mode=mode)
    ):
        from chat_application.rag import _format_security_event_group_by_lob_answer

        return _format_security_event_group_by_lob_answer(question, rows)

    if "count" in labels and is_security_event_alert_count_question(question, mode=mode):
        from chat_application.rag import _format_security_event_alert_count_answer

        count_rows = [row for row in rows if row.get("total") is not None]
        return _format_security_event_alert_count_answer(question, count_rows or rows)

    if "count" in labels and is_count_question(question):
        total = int(rows[0].get("total") or 0) if rows else 0
        return f"The count is {total}."

    return None
