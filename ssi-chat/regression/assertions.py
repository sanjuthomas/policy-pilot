from __future__ import annotations

import re
from typing import Any

from regression.models import ConfirmStep, ExpectConfig


def evaluate_expectations(
    expect: ExpectConfig,
    *,
    answer: str,
    sources: list[Any],
    graph_rows: list[Any],
    cypher: str | None,
    intent_id: str | None = None,
    skill_confirmation: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    if len(answer.strip()) < expect.min_answer_length:
        return False, f"answer shorter than min_answer_length={expect.min_answer_length}"

    lowered = answer.lower()

    for token in expect.answer_not_contains:
        if token.lower() in lowered:
            return False, f"answer unexpectedly contains {token!r}"

    if expect.answer_contains_all:
        missing = [token for token in expect.answer_contains_all if token.lower() not in lowered]
        if missing:
            return False, f"answer missing required tokens: {missing}"

    if expect.answer_contains_any:
        if not any(token.lower() in lowered for token in expect.answer_contains_any):
            return False, f"answer matched none of {expect.answer_contains_any!r}"

    if expect.answer_has_number and not re.search(r"\d", answer):
        return False, "answer has no numeric digit"

    if len(sources) < expect.min_sources:
        return False, f"sources={len(sources)} < min_sources={expect.min_sources}"

    if len(graph_rows) < expect.min_graph_rows:
        return False, f"graph_rows={len(graph_rows)} < min_graph_rows={expect.min_graph_rows}"

    if expect.exact_graph_rows is not None and len(graph_rows) != expect.exact_graph_rows:
        return (
            False,
            f"graph_rows={len(graph_rows)} != exact_graph_rows={expect.exact_graph_rows}",
        )

    if expect.requires_cypher and not (cypher or "").strip():
        return False, "expected cypher query but none was generated"

    if expect.intent_id is not None:
        actual = intent_id or ""
        if actual != expect.intent_id:
            return False, f"intent_id={actual!r} != expected {expect.intent_id!r}"

    if expect.require_skill_confirmation:
        if not isinstance(skill_confirmation, dict) or not skill_confirmation.get("pending_id"):
            return False, "expected skill_confirmation.pending_id"
        if expect.skill_name is not None:
            actual_skill = skill_confirmation.get("skill") or ""
            if actual_skill != expect.skill_name:
                return (
                    False,
                    f"skill_confirmation.skill={actual_skill!r} != expected {expect.skill_name!r}",
                )

    if expect.forbid_skill_confirmation and skill_confirmation is not None:
        return False, "did not expect skill_confirmation"

    return True, "ok"


def evaluate_confirm_expectations(
    confirm: ConfirmStep,
    *,
    answer: str,
    intent_id: str | None = None,
) -> tuple[bool, str]:
    if len(answer.strip()) < confirm.min_answer_length:
        return False, f"confirm answer shorter than min_answer_length={confirm.min_answer_length}"

    lowered = answer.lower()
    for token in confirm.answer_not_contains:
        if token.lower() in lowered:
            return False, f"confirm answer unexpectedly contains {token!r}"

    if confirm.answer_contains_all:
        missing = [
            token for token in confirm.answer_contains_all if token.lower() not in lowered
        ]
        if missing:
            return False, f"confirm answer missing required tokens: {missing}"

    if confirm.answer_contains_any:
        if not any(token.lower() in lowered for token in confirm.answer_contains_any):
            return False, f"confirm answer matched none of {confirm.answer_contains_any!r}"

    if confirm.intent_id is not None:
        actual = intent_id or ""
        if actual != confirm.intent_id:
            return False, f"confirm intent_id={actual!r} != expected {confirm.intent_id!r}"

    return True, "ok"
