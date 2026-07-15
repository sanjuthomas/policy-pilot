from __future__ import annotations

from chat_application.pipeline.handlers.base import ChatHandler, HandlerContext
from chat_application.pipeline.handlers.denial import DenialHandler
from chat_application.pipeline.handlers.gates import (
    DenialReason,
    HandlerLane,
    resolve_lane_access,
)
from chat_application.pipeline.handlers.investigate import InvestigateHandler
from chat_application.pipeline.handlers.me import MeIntentHandler
from chat_application.pipeline.handlers.neo4j_direct import Neo4jDirectHandler
from chat_application.pipeline.handlers.policy_tools import PolicyToolsHandler
from chat_application.pipeline.handlers.skill import CreatePaymentSkillHandler

_skill = CreatePaymentSkillHandler()
_me = MeIntentHandler()
_tools = PolicyToolsHandler()
_direct = Neo4jDirectHandler()
_investigate = InvestigateHandler()


class _ChainHandler:
    """Try handlers in order; first non-None response wins."""

    def __init__(self, *handlers: ChatHandler) -> None:
        self._handlers = handlers

    async def handle(self, ctx: HandlerContext):
        for handler in self._handlers:
            response = await handler.handle(ctx)
            if response is not None:
                return response
        return None


async def resolve_and_handle(ctx: HandlerContext):
    """Capability × mode fence, then lane handler (no orchestrator switchboard)."""
    access = resolve_lane_access(
        path=ctx.path,
        mode=ctx.mode,
        capabilities=ctx.capabilities,
    )
    if not access.allowed:
        assert access.denial is not None
        return await DenialHandler(access.denial).handle(ctx)

    if access.lane == HandlerLane.SKILL:
        response = await _skill.handle(ctx)
        if response is not None:
            return response
        return await DenialHandler(DenialReason.SKILL_WRONG_MODE).handle(ctx)

    if access.lane == HandlerLane.ME:
        response = await _me.handle(ctx)
        if response is not None:
            return response
        if ctx.mode == "policies":
            if ctx.capabilities.is_compliance:
                return await _tools.handle(ctx)
            return await DenialHandler(DenialReason.POLICIES_MODE_OPERATIONAL).handle(ctx)
        return await _ChainHandler(_direct, _investigate).handle(ctx)

    if access.lane == HandlerLane.TOOLS:
        return await _tools.handle(ctx)

    return await _ChainHandler(_direct, _investigate).handle(ctx)


def resolve_handler(ctx: HandlerContext):
    """Test helper: return the primary handler for the fenced lane (no I/O)."""
    access = resolve_lane_access(
        path=ctx.path,
        mode=ctx.mode,
        capabilities=ctx.capabilities,
    )
    if not access.allowed:
        return DenialHandler(access.denial)  # type: ignore[arg-type]
    if access.lane == HandlerLane.SKILL:
        return _skill
    if access.lane == HandlerLane.ME:
        return _me
    if access.lane == HandlerLane.TOOLS:
        return _tools
    return _investigate
