from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from chat_application.formatting.neo4j import (
    format_instruction_creator_by_id,
    format_instruction_detail_by_id,
    format_instruction_status_by_id,
    format_payment_creator_by_id,
    format_payment_detail_by_id,
)
from chat_application.graph.direct import (
    build_match_context,
    match_neo4j_direct_intent,
    try_neo4j_direct_answer,
)


class TestNeo4jDirectMatching:
    def test_matches_creator_by_instruction_id(self) -> None:
        question = "Who created 20260703-FICC-I-1?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.creator_by_id"
        assert match.formatter_name == "instruction_creator_by_id"
        assert "instruction_detail" in match.planned[0][0]

    def test_matches_creator_by_instruction_id_in_events_mode(self) -> None:
        question = "Who created 20260703-FICC-I-1?"
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is not None
        assert match.intent_id == "instruction.creator_by_id"

    def test_matches_creator_by_payment_id(self) -> None:
        question = "Who created 20260704-FICC-P-1?"
        match = match_neo4j_direct_intent(question, mode="payments")
        assert match is not None
        assert match.intent_id == "payment.creator_by_id"
        assert match.formatter_name == "payment_creator_by_id"
        assert "payment_detail" in match.planned[0][0]

    def test_matches_show_payment_by_id(self) -> None:
        question = "can you show me the payment 20260712-FICC-P-2?"
        match = match_neo4j_direct_intent(question, mode="payments")
        assert match is not None
        assert match.intent_id == "payment.show_by_id"
        assert match.formatter_name == "payment_detail_by_id"

    def test_matches_show_instruction_by_id(self) -> None:
        question = "Can you show me the instruction 20260717-FICC-I-19?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.show_by_id"
        assert match.formatter_name == "instruction_detail_by_id"
        assert "instruction_detail" in match.planned[0][0]
        assert "[:CURRENT]->" in match.planned[0][1]

    def test_matches_show_instruction_by_id_without_noun(self) -> None:
        """Bare 'show me <I-id>' is semantically the same as with 'the instruction'."""
        question = "Can you show me 20260719-FICC-I-14?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.show_by_id"
        assert match.formatter_name == "instruction_detail_by_id"

    def test_matches_show_payment_by_id_without_noun(self) -> None:
        question = "Can you show me 20260712-FICC-P-2?"
        match = match_neo4j_direct_intent(question, mode="payments")
        assert match is not None
        assert match.intent_id == "payment.show_by_id"
        assert match.formatter_name == "payment_detail_by_id"

    def test_matches_show_payment_by_id_without_noun_underscore_lob(self) -> None:
        """Bare show-me must accept OWNING_LOB tokens with underscores (e.g. DESK_RATES)."""
        question = "Can you show me 20260720-DESK_RATES-P-2?"
        match = match_neo4j_direct_intent(question, mode="payments")
        assert match is not None
        assert match.intent_id == "payment.show_by_id"
        assert match.formatter_name == "payment_detail_by_id"

    def test_matches_show_instruction_by_id_in_events_mode(self) -> None:
        question = "Can you show me instruction 20260717-FICC-I-19?"
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is not None
        assert match.intent_id == "instruction.show_by_id"

    def test_show_instruction_excludes_version_history(self) -> None:
        question = "Show me all versions of instruction 20260717-FICC-I-19"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.versions_by_id"

    def test_matches_creator_by_payment_id_in_events_mode(self) -> None:
        question = "Who created 20260704-FICC-P-1?"
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is not None
        assert match.intent_id == "payment.creator_by_id"

    def test_payment_creator_and_approver_beats_creator_only(self) -> None:
        question = "Who created 20260704-FICC-P-1 and who approved it?"
        match = match_neo4j_direct_intent(question, mode="payments")
        assert match is not None
        assert match.intent_id == "payment.creator_and_approver_by_id"

    def test_creator_and_approver_beats_creator_only(self) -> None:
        question = "Who created 20260703-FICC-I-1 and who approved it?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.creator_and_approver_by_id"

    def test_status_by_id(self) -> None:
        question = "What is the status of 20260703-FICC-I-1?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.status_by_id"

    def test_payment_status_by_id_any_ui_mode(self) -> None:
        question = "What is the status of 20260720-FICC-P-19?"
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is not None
        assert match.intent_id == "payment.status_by_id"

    def test_payment_approver_by_id_bare_id_any_ui_mode(self) -> None:
        question = "Who approved 20260720-FICC-P-19?"
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is not None
        assert match.intent_id == "payment.approver_by_id"
        assert match.formatter_name == "payment_approver_by_id"

    def test_mutual_approval(self) -> None:
        question = "Are there any mutual approval cases?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.mutual_approval"

    def test_list_single_use_spaced_synonym(self) -> None:
        question = "Can you show me the approved SINGLE USE instructions in the system?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.list_single_use"
        assert match.formatter_name == "instruction_inventory_table"
        cypher = match.planned[0][1]
        assert "instruction_type = 'SINGLE_USE'" in cypher
        assert "status = 'APPROVED'" in cypher

    def test_list_single_use_underscore_token(self) -> None:
        question = "Can you show me the approved SINGLE_USE instructions in the system?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.list_single_use"
        cypher = match.planned[0][1]
        assert "instruction_type = 'SINGLE_USE'" in cypher
        assert "status = 'APPROVED'" in cypher

    def test_list_single_use_one_time_synonym(self) -> None:
        question = "List one-time use instructions"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.list_single_use"

    def test_list_standing_instructions(self) -> None:
        question = "Can you show me the standing instructions in the system?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.list_standing"
        assert "instruction_type = 'STANDING'" in match.planned[0][1]

    def test_list_approved_instructions_by_status(self) -> None:
        question = "Can you list all approved instructions?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.list_by_status"
        assert match.formatter_name == "instruction_inventory_table"
        assert "[:CURRENT]->" in match.planned[0][1]
        assert "status = 'APPROVED'" in match.planned[0][1]

    def test_list_approved_standing_applies_both_filters(self) -> None:
        question = "can you list all approved standing instructions?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        cypher = match.planned[0][1]
        assert "status = 'APPROVED'" in cypher
        assert "instruction_type = 'STANDING'" in cypher

    def test_list_evergreen_instructions(self) -> None:
        question = "Can you show me the evergreen instructions in the system?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.list_standing"
        assert "instruction_type = 'STANDING'" in match.planned[0][1]

    def test_cross_entity_reciprocal_approval_events_mode(self) -> None:
        question = (
            "Are there cases where one user approved another user's instruction, "
            "and that same other user created a payment on that instruction that "
            "the first user then approved?"
        )
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is not None
        assert match.intent_id == "instruction.cross_entity_reciprocal_approval"
        assert match.planned[0][0] == "cross_entity_reciprocal_approval"
        assert "instruction_id AS instruction_id" in match.planned[0][1]

    def test_alerts_today_yaml_intent(self) -> None:
        question = "How many ALERT events happened today?"
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is not None
        assert match.intent_id == "events.alerts_today_count"

    def test_alert_list_payments_domain_filter(self) -> None:
        question = "can you list all alerts for payments?"
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is not None
        assert match.intent_id == "events.alert_list"
        assert "AND e.payment_id IS NOT NULL" in match.planned[0][1]
        assert "AND e.payment_id IS NULL" not in match.planned[0][1]

    def test_alert_list_instructions_domain_filter(self) -> None:
        question = "can you list all alerts for instructions?"
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is not None
        assert match.intent_id == "events.alert_list"
        assert "AND e.payment_id IS NULL" in match.planned[0][1]

    def test_instruction_denial_events_direct_in_instructions_mode(self) -> None:
        question = "Can you list all instruction denial events for this week?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "events.alert_list"
        assert "AND e.payment_id IS NULL" in match.planned[0][1]
        assert "P7D" in match.planned[0][1]

    def test_instruction_policy_denial_count_via_planned_direct(self) -> None:
        question = "How many instruction policy denials happened this week?"
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is None
        from chat_application.graph.direct import match_planned_graph_intent

        planned = match_planned_graph_intent(question, mode="events")
        assert planned is not None
        assert "e.payment_id IS NULL" in planned.planned[0][1]
        assert "e.severity = 'ALERT'" in planned.planned[0][1]
        assert "P7D" in planned.planned[0][1]

    def test_payment_alerts_today_uses_planned_graph_not_yaml(self) -> None:
        question = "How many payment ALERT events happened today?"
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is None
        from chat_application.graph.direct import match_planned_graph_intent

        planned = match_planned_graph_intent(question, mode="events")
        assert planned is not None
        assert "e.payment_id IS NOT NULL" in planned.planned[0][1]

    def test_planned_graph_count_single_use_via_direct_path(self) -> None:
        question = "How many single use instructions are there?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is None
        from chat_application.graph.direct import match_planned_graph_intent

        planned = match_planned_graph_intent(question, mode="instructions")
        assert planned is not None
        assert planned.intent_id == "planned_graph"
        assert "v.instruction_type = 'SINGLE_USE'" in planned.planned[0][1]
        assert "v.status = 'SINGLE_USE'" not in planned.planned[0][1]

    def test_planned_graph_group_by_status_via_direct_path(self) -> None:
        question = "Can you group instructions by status?"
        from chat_application.graph.direct import match_planned_graph_intent

        planned = match_planned_graph_intent(question, mode="instructions")
        assert planned is not None
        assert planned.intent_id == "planned_graph"
        assert planned.planned[0][0] == "facet_aggregate"

    def test_no_match_for_vague_question(self) -> None:
        assert match_neo4j_direct_intent("Tell me about instructions", mode="instructions") is None

    def test_build_match_context_extracts_instruction_id(self) -> None:
        context = build_match_context("Who created 20260703-FICC-I-1?")
        assert context["instruction_ids"] == ["20260703-FICC-I-1"]

    def test_build_match_context_extracts_payment_id(self) -> None:
        context = build_match_context("Who created 20260704-FICC-P-1?")
        assert context["payment_ids"] == ["20260704-FICC-P-1"]

    def test_build_match_context_extracts_user_id(self) -> None:
        context = build_match_context("Which instructions did mo-100 create?")
        assert context["user_id"] == "mo-100"


class TestNeo4jDirectFormatters:
    def test_format_creator_by_id(self) -> None:
        answer = format_instruction_creator_by_id(
            "Who created 20260703-FICC-I-1?",
            [{"instruction_id": "20260703-FICC-I-1", "creator_display": "Walsh, Patricia (mo-010)"}],
        )
        assert answer is not None
        assert "20260703-FICC-I-1" in answer
        assert "Walsh, Patricia (mo-010)" in answer

    def test_format_status_by_id(self) -> None:
        answer = format_instruction_status_by_id(
            "status?",
            [{"instruction_id": "20260703-FICC-I-1", "status": "DRAFT", "owning_lob": "FICC"}],
        )
        assert answer is not None
        assert "DRAFT" in answer
        assert "FICC" in answer

    def test_format_payment_creator_by_id(self) -> None:
        answer = format_payment_creator_by_id(
            "Who created 20260704-FICC-P-1?",
            [{"payment_id": "20260704-FICC-P-1", "creator_display": "Rodriguez, Emily (pay-101)"}],
        )
        assert answer is not None
        assert "20260704-FICC-P-1" in answer
        assert "Rodriguez, Emily (pay-101)" in answer

    def test_format_payment_detail_by_id(self) -> None:
        answer = format_payment_detail_by_id(
            "can you show me the payment 20260712-FICC-P-2?",
            [
                {
                    "payment_id": "20260712-FICC-P-2",
                    "instruction_id": "20260705-FICC-I-31",
                    "status": "DRAFT",
                    "amount": 15_000_000.0,
                    "currency": "USD",
                    "value_date": "2026-07-13",
                    "owning_lob": "FICC",
                    "creator_display": "Al-Rashid, Fatima (pay-205)",
                    "approver_display": "",
                }
            ],
        )
        assert answer is not None
        assert "### Payment `20260712-FICC-P-2`" in answer
        assert "USD 15,000,000" in answer
        assert "not yet approved" in answer
        assert "paymentid:" not in answer.lower()
        assert "| Field" in answer and "| Value" in answer

    def test_format_instruction_detail_by_id(self) -> None:
        answer = format_instruction_detail_by_id(
            "Can you show me the instruction 20260717-FICC-I-19?",
            [
                {
                    "instruction_id": "20260717-FICC-I-19",
                    "status": "APPROVED",
                    "instruction_type": "STANDING",
                    "owning_lob": "FICC",
                    "currency": "USD",
                    "wire_scope": "DOMESTIC",
                    "creditor_name": None,
                    "creditor_account": None,
                    "effective_date": "2026-07-17T00:00:00",
                    "end_date": "2027-07-17T00:00:00",
                    "version_number": 2,
                    "creator_display": "Okonkwo, David (mo-050)",
                    "approver_display": "Nguyen, Caroline (ficc-500)",
                    "approved_at": "2026-07-17T10:00:00",
                }
            ],
        )
        assert answer is not None
        assert "### Instruction `20260717-FICC-I-19`" in answer
        assert "**APPROVED**" in answer
        assert "STANDING" in answer
        assert "Okonkwo, David (mo-050)" in answer
        assert "Nguyen, Caroline (ficc-500)" in answer
        assert "Approved at: 2026-07-17T10:00:00" in answer
        assert "| Field" in answer and "| Value" in answer
        assert "instruction_id:" not in answer


class TestNeo4jDirectExecution:
    @pytest.mark.asyncio
    async def test_try_neo4j_direct_answer_creator(self) -> None:
        neo4j = AsyncMock()
        neo4j.run_cypher = AsyncMock(
            return_value=[
                {
                    "instruction_id": "20260703-FICC-I-1",
                    "creator_display": "Walsh, Patricia (mo-010)",
                }
            ]
        )
        result = await try_neo4j_direct_answer(
            neo4j,
            "Who created 20260703-FICC-I-1?",
            mode="instructions",
        )
        assert result is not None
        assert "Walsh, Patricia (mo-010)" in result.answer
        assert result.intent_id == "instruction.creator_by_id"
        neo4j.run_cypher.assert_awaited()

    @pytest.mark.asyncio
    async def test_try_neo4j_direct_answer_payment_creator(self) -> None:
        neo4j = AsyncMock()
        neo4j.run_cypher = AsyncMock(
            return_value=[
                {
                    "payment_id": "20260704-FICC-P-1",
                    "creator_display": "Rodriguez, Emily (pay-101)",
                }
            ]
        )
        result = await try_neo4j_direct_answer(
            neo4j,
            "Who created 20260704-FICC-P-1?",
            mode="payments",
        )
        assert result is not None
        assert "Rodriguez, Emily (pay-101)" in result.answer
        assert result.intent_id == "payment.creator_by_id"
        neo4j.run_cypher.assert_awaited()

    @pytest.mark.asyncio
    async def test_try_neo4j_direct_answer_single_use_count(self) -> None:
        neo4j = AsyncMock()
        neo4j.run_cypher = AsyncMock(return_value=[{"total": 2}])
        result = await try_neo4j_direct_answer(
            neo4j,
            "How many single use instructions are there?",
            mode="instructions",
        )
        assert result is not None
        assert "2" in result.answer
        assert "instruction" in result.answer.lower()
        assert "payment" not in result.answer.lower()
        assert result.intent_id == "planned_graph"
        neo4j.run_cypher.assert_awaited()
