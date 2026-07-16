"""Capability × mode fence and handler-registry tests."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from chat_application.auth.capabilities import ChatCapabilities
from chat_application.pipeline.handlers.base import HandlerContext
from chat_application.pipeline.handlers.denial import DenialHandler
from chat_application.pipeline.handlers.gates import (
    DenialReason,
    HandlerLane,
    resolve_lane_access,
)
from chat_application.pipeline.handlers.investigate import InvestigateHandler
from chat_application.pipeline.handlers.me import MeIntentHandler
from chat_application.pipeline.handlers.policy_tools import PolicyToolsHandler
from chat_application.pipeline.handlers.registry import resolve_handler
from chat_application.pipeline.handlers.skill import CreatePaymentSkillHandler
from chat_application.pipeline.models import RouterDecision


def _caps(
    *,
    compliance: bool = False,
    creator: bool = False,
    approver: bool = False,
) -> ChatCapabilities:
    return ChatCapabilities(
        is_compliance=compliance,
        can_create_payment=creator,
        can_approve_payment=approver,
    )


def _ctx(
    *,
    path: str | None,
    mode: str,
    caps: ChatCapabilities,
) -> HandlerContext:
    decision = RouterDecision(path=path, strategy="graph" if path in {None, "graph"} else None)
    if path in {"vector", "hybrid", "eligibility"}:
        decision = RouterDecision(path=path, strategy=path if path != "eligibility" else "eligibility")
    return HandlerContext(
        service=MagicMock(),
        message="test",
        history=[],
        mode=mode,  # type: ignore[arg-type]
        decision=decision,
        subject=None,
        capabilities=caps,
        bearer_token=None,
        session_id=None,
        started=time.perf_counter(),
    )


class TestLaneAccess:
    def test_skill_requires_payments_mode_and_creator_or_approver(self) -> None:
        denied_mode = resolve_lane_access(
            path="skill", mode="events", capabilities=_caps(creator=True)
        )
        assert not denied_mode.allowed
        assert denied_mode.denial == DenialReason.SKILL_WRONG_MODE

        denied_role = resolve_lane_access(
            path="skill", mode="payments", capabilities=_caps(compliance=True)
        )
        assert not denied_role.allowed
        assert denied_role.denial == DenialReason.SKILL_NOT_CREATOR

        ok_creator = resolve_lane_access(
            path="skill", mode="payments", capabilities=_caps(creator=True)
        )
        assert ok_creator.allowed
        assert ok_creator.lane == HandlerLane.SKILL

        ok_approver = resolve_lane_access(
            path="skill", mode="payments", capabilities=_caps(approver=True)
        )
        assert ok_approver.allowed
        assert ok_approver.lane == HandlerLane.SKILL

    def test_tools_require_policies_mode_and_compliance(self) -> None:
        denied_mode = resolve_lane_access(
            path="policy_summary",
            mode="payments",
            capabilities=_caps(compliance=True),
        )
        assert not denied_mode.allowed
        assert denied_mode.denial == DenialReason.TOOLS_WRONG_MODE

        denied_role = resolve_lane_access(
            path="eligibility",
            mode="policies",
            capabilities=_caps(creator=True),
        )
        assert not denied_role.allowed
        assert denied_role.denial == DenialReason.TOOLS_NOT_COMPLIANCE

        ok = resolve_lane_access(
            path="policy_directory",
            mode="policies",
            capabilities=_caps(compliance=True),
        )
        assert ok.allowed
        assert ok.lane == HandlerLane.TOOLS

    def test_investigate_blocked_in_policies_for_operational(self) -> None:
        access = resolve_lane_access(
            path="graph", mode="policies", capabilities=_caps(creator=True)
        )
        assert not access.allowed
        assert access.denial == DenialReason.POLICIES_MODE_OPERATIONAL

    def test_investigate_ok_in_events(self) -> None:
        access = resolve_lane_access(
            path="graph", mode="events", capabilities=_caps(creator=True)
        )
        assert access.allowed
        assert access.lane == HandlerLane.INVESTIGATE

    def test_me_allowed_in_any_mode(self) -> None:
        access = resolve_lane_access(
            path="me", mode="events", capabilities=_caps(approver=True)
        )
        assert access.allowed
        assert access.lane == HandlerLane.ME


class TestResolveHandler:
    def test_skill_lane_returns_skill_handler(self) -> None:
        handler = resolve_handler(
            _ctx(path="skill", mode="payments", caps=_caps(creator=True))
        )
        assert isinstance(handler, CreatePaymentSkillHandler)

    def test_denied_skill_returns_denial_handler(self) -> None:
        handler = resolve_handler(
            _ctx(path="skill", mode="events", caps=_caps(creator=True))
        )
        assert isinstance(handler, DenialHandler)

    def test_tools_lane_returns_policy_handler(self) -> None:
        handler = resolve_handler(
            _ctx(path="eligibility", mode="policies", caps=_caps(compliance=True))
        )
        assert isinstance(handler, PolicyToolsHandler)

    def test_investigate_lane(self) -> None:
        handler = resolve_handler(
            _ctx(path="hybrid", mode="events", caps=_caps(compliance=True))
        )
        assert isinstance(handler, InvestigateHandler)

    def test_me_lane(self) -> None:
        handler = resolve_handler(
            _ctx(path="me", mode="payments", caps=_caps(creator=True))
        )
        assert isinstance(handler, MeIntentHandler)
