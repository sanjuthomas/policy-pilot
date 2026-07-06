from __future__ import annotations

import re

from chat_application.cypher import (
    is_alert_ranking_question,
    is_analytics_question,
    is_count_question,
    is_cross_entity_reciprocal_approval_question,
    is_instruction_count_aggregate_question,
    is_instruction_mutual_approval_question,
    is_instruction_payment_count_list_question,
    is_instruction_versions_list_question,
    is_instructions_without_payments_question,
    is_max_payments_per_instruction_question,
    is_payment_count_aggregate_question,
    is_payment_list_by_status_question,
    is_payment_total_amount_question,
    is_payment_versions_list_question,
    is_payments_for_instruction_question,
    is_security_event_alert_count_question,
    is_security_event_alert_list_question,
    is_security_event_count_aggregate_question,
    is_security_event_group_by_lob_question,
)
from chat_application.pipeline.models import (
    EligibilityTarget,
    ExecutionStrategy,
    RouterDecision,
)

_ELIGIBILITY_PATTERN = re.compile(
    r"\bwho\b.+\b(approve|authorized|authorize|eligible|green[- ]?light)\b",
    re.IGNORECASE,
)


def resolve_eligibility_target(message: str, *, mode: str) -> EligibilityTarget | None:
    """Resolve payment vs instruction for eligibility without phrase lists."""
    upper = message.upper()
    if "-P-" in upper:
        return "payment"
    if "-I-" in upper:
        return "instruction"

    lowered = message.lower()
    mentions_payment = "payment" in lowered
    mentions_instruction = "instruction" in lowered or "ssi" in lowered

    if mentions_payment and not mentions_instruction:
        return "payment"
    if mentions_instruction and not mentions_payment:
        return "instruction"
    if mode == "instructions":
        return "instruction"
    if mode == "payments":
        return "payment"
    if mentions_payment:
        return "payment"
    if mentions_instruction:
        return "instruction"
    return None


def is_eligibility_question_heuristic(message: str) -> bool:
    """Fallback only — used when the LLM router is unavailable."""
    return _ELIGIBILITY_PATTERN.search(message) is not None


def is_graph_structured_question(question: str, *, mode: str) -> bool:
    """True when the question is primarily answered by structured graph data."""
    if is_count_question(question):
        return True
    if is_analytics_question(question, mode=mode):
        return True
    if is_payment_count_aggregate_question(question):
        return True
    if is_payment_total_amount_question(question):
        return True
    if is_instruction_count_aggregate_question(question):
        return True
    if is_instruction_versions_list_question(question, mode=mode):
        return True
    if is_payment_versions_list_question(question, mode=mode):
        return True
    if is_security_event_count_aggregate_question(question, mode=mode):
        return True
    if is_security_event_alert_count_question(question, mode=mode):
        return True
    if is_security_event_alert_list_question(question, mode=mode):
        return True
    if is_security_event_group_by_lob_question(question, mode=mode):
        return True
    if is_instruction_mutual_approval_question(question):
        return True
    if is_cross_entity_reciprocal_approval_question(question):
        return True
    if is_instruction_payment_count_list_question(question, mode=mode):
        return True
    if is_instructions_without_payments_question(question, mode=mode):
        return True
    if is_payment_list_by_status_question(question, mode=mode):
        return True
    if is_alert_ranking_question(question, mode=mode):
        return True
    if is_max_payments_per_instruction_question(question):
        return True
    if is_payments_for_instruction_question(question):
        return True
    if re.search(r"\bwho approved\b", question, re.IGNORECASE):
        return True
    if re.search(r"\bwhen (was|did)\b.+\bapprov", question, re.IGNORECASE):
        return True
    return False


def is_vector_semantic_question(question: str, *, mode: str) -> bool:
    """True when semantic retrieval is the primary signal."""
    lowered = question.lower()
    if "why" in lowered and not is_graph_structured_question(question, mode=mode):
        return True
    if re.search(r"\bexplain\b|\bpolicy\b|\bdenied because\b", lowered):
        return True
    return False


def infer_execution_strategy_heuristic(question: str, *, mode: str) -> ExecutionStrategy:
    if is_eligibility_question_heuristic(question):
        return "eligibility"
    if is_graph_structured_question(question, mode=mode):
        return "graph"
    if is_vector_semantic_question(question, mode=mode):
        return "vector"
    return "hybrid"


def heuristic_router_decision(question: str, *, mode: str) -> RouterDecision:
    strategy = infer_execution_strategy_heuristic(question, mode=mode)
    target = resolve_eligibility_target(question, mode=mode) if strategy == "eligibility" else None
    return RouterDecision(
        strategy=strategy,
        eligibility_target=target,
        reasoning="heuristic fallback",
    )
