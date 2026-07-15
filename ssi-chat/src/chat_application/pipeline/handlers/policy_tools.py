from __future__ import annotations

from chat_application.graph.cypher import extract_entity_ids, extract_payment_ids
from chat_application.models import ChatResponse
from chat_application.observability.routing import finalize_chat_response
from chat_application.pipeline.handlers.base import HandlerContext
from chat_application.pipeline.heuristic_strategy import (
    is_eligibility_question_heuristic,
    resolve_eligibility_target,
)
from chat_application.policy.summary import policies_mode_guidance


class PolicyToolsHandler:
    """Policies-mode live tools: summary, directory, person permissions, eligibility."""

    async def handle(self, ctx: HandlerContext) -> ChatResponse | None:
        path = ctx.path

        if path == "policy_summary":
            response = await self._policy_summary(ctx)
            if response is not None:
                return response
        elif path == "policy_directory":
            response = await self._policy_directory(ctx)
            if response is not None:
                return response
        elif path == "person_permissions":
            response = await self._person_permissions(ctx)
            if response is not None:
                return response
        elif path == "eligibility":
            response = await self._eligibility(ctx, require_eligibility_path=True)
            if response is not None:
                return response

        response = await self._eligibility(ctx, require_eligibility_path=False)
        if response is not None:
            return response

        return finalize_chat_response(
            ctx.message,
            ctx.mode,
            answer=policies_mode_guidance(),
            retrieval_ms=0.0,
            generation_ms=ctx.elapsed_ms(),
            path="eligibility",
            cypher_provenance="none",
            answer_synthesis="eligibility_api",
        )

    async def _policy_summary(self, ctx: HandlerContext) -> ChatResponse | None:
        answer = await ctx.service._answer_policy_summary(
            ctx.message,
            mode=ctx.mode,
            bearer_token=ctx.bearer_token,
            session_id=ctx.session_id,
            domain=ctx.decision.policy_domain,
            action=ctx.decision.policy_action,
        )
        if answer is None:
            return None
        return finalize_chat_response(
            ctx.message,
            ctx.mode,
            answer=answer,
            retrieval_ms=0.0,
            generation_ms=ctx.elapsed_ms(),
            path="eligibility",
            cypher_provenance="none",
            answer_synthesis="eligibility_api",
        )

    async def _policy_directory(self, ctx: HandlerContext) -> ChatResponse | None:
        answer = await ctx.service._answer_payment_approval_directory(
            ctx.message,
            bearer_token=ctx.bearer_token,
            session_id=ctx.session_id,
            force=True,
        )
        if answer is None:
            return None
        return finalize_chat_response(
            ctx.message,
            ctx.mode,
            answer=answer,
            retrieval_ms=0.0,
            generation_ms=ctx.elapsed_ms(),
            path="policy_directory",
            cypher_provenance="none",
            answer_synthesis="policy_directory_api",
        )

    async def _person_permissions(self, ctx: HandlerContext) -> ChatResponse | None:
        answer = await ctx.service._answer_person_permission_summary(
            ctx.message,
            bearer_token=ctx.bearer_token,
            session_id=ctx.session_id,
            person_query=ctx.decision.person_query,
        )
        if answer is None:
            return None
        return finalize_chat_response(
            ctx.message,
            ctx.mode,
            answer=answer,
            retrieval_ms=0.0,
            generation_ms=ctx.elapsed_ms(),
            path="eligibility",
            cypher_provenance="none",
            answer_synthesis="eligibility_api",
        )

    async def _eligibility(
        self,
        ctx: HandlerContext,
        *,
        require_eligibility_path: bool,
    ) -> ChatResponse | None:
        path = ctx.path
        if require_eligibility_path:
            if path != "eligibility" and ctx.decision.retrieval_strategy != "eligibility":
                return None
        elif path != "eligibility":
            if not is_eligibility_question_heuristic(ctx.message):
                if not extract_entity_ids(ctx.message) and not extract_payment_ids(ctx.message):
                    return None

        target = ctx.decision.eligibility_target or resolve_eligibility_target(
            ctx.message, mode=ctx.mode
        )
        if target == "payment":
            answer = await ctx.service._answer_payment_eligible_approvers(
                ctx.message,
                bearer_token=ctx.bearer_token,
                session_id=ctx.session_id,
            )
        elif target == "instruction":
            answer = await ctx.service._answer_instruction_eligible_approvers(
                ctx.message,
                bearer_token=ctx.bearer_token,
                session_id=ctx.session_id,
            )
        else:
            return None

        if answer is None:
            return None

        return finalize_chat_response(
            ctx.message,
            ctx.mode,
            answer=answer,
            retrieval_ms=0.0,
            generation_ms=ctx.elapsed_ms(),
            path="eligibility",
            cypher_provenance="none",
            answer_synthesis="eligibility_api",
        )
