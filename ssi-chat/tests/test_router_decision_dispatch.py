"""Hermetic RouterDecision → lane dispatch for skill / eligibility / policy paths."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from chat_application.auth.capabilities import ChatCapabilities
from chat_application.models import ChatResponse
from chat_application.pipeline.handlers.base import HandlerContext
from chat_application.pipeline.handlers.denial import DenialHandler
from chat_application.pipeline.handlers.policy_tools import PolicyToolsHandler
from chat_application.pipeline.handlers.registry import (
    resolve_and_handle,
    resolve_handler,
)
from chat_application.pipeline.handlers.skill import CreatePaymentSkillHandler
from chat_application.pipeline.models import RouterDecision


def _caps(
    *,
    compliance: bool = False,
    creator: bool = False,
    approver: bool = False,
    canceller: bool = False,
) -> ChatCapabilities:
    return ChatCapabilities(
        is_compliance=compliance,
        can_create_payment=creator,
        can_approve_payment=approver,
        can_cancel_payment=canceller,
        is_instruction_analyst=False,
    )


def _ctx(
    *,
    path: str,
    strategy: str | None = None,
    mode: str,
    caps: ChatCapabilities,
    subject: object | None = MagicMock(),
    bearer_token: str | None = "token",
) -> HandlerContext:
    # RouterDecision.strategy is only for retrieval paths; tool/skill paths leave it unset.
    retrieval_strategies = {"eligibility", "graph", "vector", "hybrid"}
    resolved_strategy = strategy
    if resolved_strategy is None and path in retrieval_strategies:
        resolved_strategy = path if path != "hybrid" else "hybrid"
    if resolved_strategy is not None and resolved_strategy not in retrieval_strategies:
        resolved_strategy = None
    decision = RouterDecision(
        path=path,  # type: ignore[arg-type]
        strategy=resolved_strategy,  # type: ignore[arg-type]
    )
    return HandlerContext(
        service=MagicMock(),
        message="test question",
        history=[],
        mode=mode,  # type: ignore[arg-type]
        decision=decision,
        subject=subject,  # type: ignore[arg-type]
        capabilities=caps,
        bearer_token=bearer_token,
        session_id="sess",
        started=time.perf_counter(),
    )


class TestRouterDecisionDispatch:
    def test_skill_path_resolves_to_skill_handler(self) -> None:
        handler = resolve_handler(
            _ctx(path="skill", strategy="skill", mode="payments", caps=_caps(creator=True))
        )
        assert isinstance(handler, CreatePaymentSkillHandler)

    def test_eligibility_path_resolves_to_policy_tools(self) -> None:
        handler = resolve_handler(
            _ctx(
                path="eligibility",
                strategy="eligibility",
                mode="policies",
                caps=_caps(compliance=True),
            )
        )
        assert isinstance(handler, PolicyToolsHandler)

    def test_policy_directory_path_resolves_to_policy_tools(self) -> None:
        handler = resolve_handler(
            _ctx(
                path="policy_directory",
                strategy="policy_directory",
                mode="policies",
                caps=_caps(compliance=True),
            )
        )
        assert isinstance(handler, PolicyToolsHandler)

    def test_policy_summary_path_resolves_to_policy_tools(self) -> None:
        handler = resolve_handler(
            _ctx(
                path="policy_summary",
                mode="policies",
                caps=_caps(compliance=True),
            )
        )
        assert isinstance(handler, PolicyToolsHandler)

    def test_skill_path_allowed_for_approver(self) -> None:
        handler = resolve_handler(
            _ctx(
                path="skill",
                strategy="skill",
                mode="payments",
                caps=_caps(approver=True),
            )
        )
        assert isinstance(handler, CreatePaymentSkillHandler)

    def test_skill_path_denied_without_operational_role(self) -> None:
        handler = resolve_handler(
            _ctx(
                path="skill",
                strategy="skill",
                mode="payments",
                caps=_caps(),
            )
        )
        assert isinstance(handler, DenialHandler)

    @pytest.mark.asyncio
    async def test_resolve_and_handle_runs_skill_lane(self) -> None:
        ctx = _ctx(
            path="skill",
            strategy="skill",
            mode="payments",
            caps=_caps(creator=True),
        )
        expected = ChatResponse(answer="ok", sources=[])
        with patch(
            "chat_application.pipeline.handlers.registry._skill.handle",
            new=AsyncMock(return_value=expected),
        ) as handle:
            response = await resolve_and_handle(ctx)
        assert response is expected
        handle.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_resolve_and_handle_runs_eligibility_tools_lane(self) -> None:
        ctx = _ctx(
            path="eligibility",
            strategy="eligibility",
            mode="policies",
            caps=_caps(compliance=True),
        )
        expected = ChatResponse(answer="eligible", sources=[])
        with patch(
            "chat_application.pipeline.handlers.registry._tools.handle",
            new=AsyncMock(return_value=expected),
        ) as handle:
            response = await resolve_and_handle(ctx)
        assert response is expected
        handle.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_resolve_and_handle_runs_policy_directory_tools_lane(self) -> None:
        ctx = _ctx(
            path="policy_directory",
            strategy="policy_directory",
            mode="policies",
            caps=_caps(compliance=True),
        )
        expected = ChatResponse(answer="directory", sources=[])
        with patch(
            "chat_application.pipeline.handlers.registry._tools.handle",
            new=AsyncMock(return_value=expected),
        ) as handle:
            response = await resolve_and_handle(ctx)
        assert response is expected
        handle.assert_awaited_once()
