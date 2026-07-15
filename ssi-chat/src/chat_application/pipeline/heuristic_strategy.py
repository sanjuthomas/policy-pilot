"""Heuristic / regex helpers used beside LLM semantic routing.

Open-ended intent is decided by Gemini structured output (``RouterDecision``).
This module is *not* primary NLU — it exists for three narrower reasons:

1. **Resilience fallback** — ``route_question()`` calls ``heuristic_router_decision()``
   only when the LLM router fails (network, schema error, etc.). Chat should
   degrade to coarse routing rather than hard-fail.
2. **Slot / structural parsing** — ID shape (``-P-`` / ``-I-``), UI search mode, and
   shared graph detectors from ``cypher_builder`` (counts, lists, rankings). These
   fill fields the LLM may omit (e.g. ``eligibility_target``) and classify
   structured graph questions; they are not synonym dictionaries for intent.
3. **Policies-mode guardrails** — cheap eligibility-pattern checks so Policies does
   not always hit live OPA when the router path is loose.

Keep phrase-list growth out of the happy path. Synonyms like "green-light" belong
to the LLM router; extend this file only for fallback resilience and slot parsing.
See docs/intent-determination.md.
"""

from __future__ import annotations

import re

from chat_application.graph.cypher import (
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
    is_payment_list_question,
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

_CREATE_PAYMENT_SKILL = re.compile(
    r"\b("
    r"(please\s+)?(create|draft)\s+(a\s+)?payment|"
    r"can\s+you\s+create\s+(a\s+)?payment|"
    r"would\s+you\s+create\s+(a\s+)?payment|"
    r"create\s+me\s+(a\s+)?payment"
    r")\b",
    re.IGNORECASE,
)

_SUBMIT_PAYMENT_SKILL = re.compile(
    r"\b("
    r"(please\s+)?submit\s+(a\s+|the\s+|this\s+)?payment|"
    r"can\s+you\s+submit\s+(a\s+|the\s+|this\s+)?payment|"
    r"submit\s+(it\s+)?for\s+approval|"
    r"send\s+(the\s+|this\s+)?payment\s+for\s+approval"
    r")\b",
    re.IGNORECASE,
)

_CAPABILITY_ONLY = re.compile(
    r"^\s*(can|may|do)\s+i\b|"
    r"^\s*am\s+i\s+(allowed|able|permitted)\b|"
    r"\b(permission|allowed)\s+to\s+(create|submit)\b",
    re.IGNORECASE,
)


def resolve_eligibility_target(message: str, *, mode: str) -> EligibilityTarget | None:
    """Resolve payment vs instruction for eligibility (slot / id heuristics)."""
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
    if mode == "policies":
        return "payment"
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
    if is_payment_list_question(question, mode=mode):
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
    if mode == "policies":
        if is_eligibility_question_heuristic(question):
            return "eligibility"
        return "hybrid"
    if is_eligibility_question_heuristic(question):
        return "eligibility"
    if is_graph_structured_question(question, mode=mode):
        return "graph"
    if is_vector_semantic_question(question, mode=mode):
        return "vector"
    return "hybrid"


def _looks_like_submit_payment_skill(message: str) -> bool:
    text = message.strip()
    if not text or not _SUBMIT_PAYMENT_SKILL.search(text):
        return False
    if _CAPABILITY_ONLY.search(text) and "you" not in text.lower()[:40]:
        return False
    from chat_application.skills.detect import parse_submit_payment_params

    return parse_submit_payment_params(text) is not None


def _looks_like_create_payment_skill(message: str) -> bool:
    text = message.strip()
    if not text or not _CREATE_PAYMENT_SKILL.search(text):
        return False
    if _CAPABILITY_ONLY.search(text) and "you" not in text.lower()[:40]:
        if "instruction" not in text.lower():
            return False
    from chat_application.skills.detect import parse_create_payment_params

    return parse_create_payment_params(text) is not None


def heuristic_router_decision(question: str, *, mode: str) -> RouterDecision:
    """Resilience fallback when Gemini routing fails — not primary NLU."""
    from chat_application.me.detect import detect_me_intent_heuristic
    from chat_application.policy.directory import is_payment_approval_directory_question
    from chat_application.policy.person import extract_person_name_heuristic
    from chat_application.policy.summary import detect_policy_summary_question

    if _looks_like_submit_payment_skill(question):
        return RouterDecision(
            path="skill",
            skill="submit_payment",
            reasoning="heuristic fallback: submit_payment skill",
        )

    if _looks_like_create_payment_skill(question):
        return RouterDecision(
            path="skill",
            skill="create_payment",
            reasoning="heuristic fallback: create_payment skill",
        )

    me = detect_me_intent_heuristic(question)
    if me is not None:
        return RouterDecision(
            path="me",
            me_kind=me.kind,
            me_action=me.action,
            me_entity_type=me.entity_type,
            reasoning="heuristic fallback: me intent",
        )

    person = extract_person_name_heuristic(question)
    if person is not None:
        return RouterDecision(
            path="person_permissions",
            person_query=person,
            reasoning="heuristic fallback: person permissions",
        )

    policy = detect_policy_summary_question(question, mode=mode)
    if policy is not None:
        domain, action = policy
        return RouterDecision(
            path="policy_summary",
            policy_domain=domain,  # type: ignore[arg-type]
            policy_action=action,  # type: ignore[arg-type]
            reasoning="heuristic fallback: policy summary",
        )

    if is_payment_approval_directory_question(question):
        return RouterDecision(
            path="policy_directory",
            reasoning="heuristic fallback: policy directory",
        )

    strategy = infer_execution_strategy_heuristic(question, mode=mode)
    target = resolve_eligibility_target(question, mode=mode) if strategy == "eligibility" else None
    return RouterDecision(
        path=strategy,
        strategy=strategy,
        eligibility_target=target,
        reasoning="heuristic fallback",
    )
