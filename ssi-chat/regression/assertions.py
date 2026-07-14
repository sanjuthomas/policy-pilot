from __future__ import annotations

import re
from typing import Any

from regression.models import ExpectConfig


def evaluate_expectations(
    expect: ExpectConfig,
    *,
    answer: str,
    sources: list[Any],
    graph_rows: list[Any],
    cypher: str | None,
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

    return True, "ok"
