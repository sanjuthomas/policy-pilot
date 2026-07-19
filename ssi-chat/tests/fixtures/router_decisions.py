"""Production-shaped ``RouterDecision`` fixtures for hermetic CI.

Happy-path unit tests must inject these (or equivalents) via ``route_query``.
Do **not** use ``heuristic_router_decision`` as a stand-in for Gemini routing;
heuristics are only the ``route.py`` failure fallback.

Fixtures are schema-valid ``RouterDecision`` instances — the same contract
``PolicyPilotMlClient.route_query`` returns in production.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from chat_application.pipeline.models import RouterDecision

# ── Canonical path matrix (extend when adding regression bank cases) ─────────

GRAPH = RouterDecision(
    path="graph",
    strategy="graph",
    reasoning="fixture: structured graph/count/list question",
)
VECTOR = RouterDecision(
    path="vector",
    strategy="vector",
    reasoning="fixture: open narrative / explanatory question",
)
HYBRID = RouterDecision(
    path="hybrid",
    strategy="hybrid",
    reasoning="fixture: hybrid retrieval",
)
ELIGIBILITY_PAYMENT = RouterDecision(
    path="eligibility",
    strategy="eligibility",
    eligibility_target="payment",
    reasoning="fixture: payment eligible actors",
)
ELIGIBILITY_INSTRUCTION = RouterDecision(
    path="eligibility",
    strategy="eligibility",
    eligibility_target="instruction",
    reasoning="fixture: instruction eligible actors",
)
POLICY_DIRECTORY = RouterDecision(
    path="policy_directory",
    reasoning="fixture: who covers LOB / directory",
)
POLICY_SUMMARY = RouterDecision(
    path="policy_summary",
    policy_domain="payment",
    policy_action="APPROVE",
    reasoning="fixture: policy summary",
)
PERSON_PERMISSIONS = RouterDecision(
    path="person_permissions",
    person_query="pay-101",
    reasoning="fixture: person permissions",
)
ME_WHO_AM_I = RouterDecision(
    path="me",
    me_kind="who_am_i",
    reasoning="fixture: who am I",
)
SKILL_CREATE_PAYMENT = RouterDecision(
    path="skill",
    skill="create_payment",
    reasoning="fixture: create payment skill",
)
SKILL_APPROVE_PAYMENT = RouterDecision(
    path="skill",
    skill="approve_payment",
    reasoning="fixture: approve payment skill",
)


def set_router_decision(ml_client, decision: RouterDecision) -> RouterDecision:
    """Wire ``ml_client.route_query`` to return a fixed production-shaped decision."""
    ml_client.route_query = AsyncMock(return_value=decision)
    return decision


# Paths that must stay fixture-covered in unit tests (issue #13).
REQUIRED_PATH_FIXTURES: tuple[RouterDecision, ...] = (
    GRAPH,
    VECTOR,
    HYBRID,
    ELIGIBILITY_PAYMENT,
    ELIGIBILITY_INSTRUCTION,
    POLICY_DIRECTORY,
    POLICY_SUMMARY,
    PERSON_PERMISSIONS,
    ME_WHO_AM_I,
    SKILL_CREATE_PAYMENT,
)
