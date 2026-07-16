from __future__ import annotations

from chat_application.formatting.response import format_chat_response
from chat_application.models import ChatResponse, SkillConfirmationInfo
from chat_application.observability.routing import finalize_chat_response
from chat_application.pipeline.handlers.base import HandlerContext


class CreatePaymentSkillHandler:
    """Mutation skill surface — Payments mode + creator/approver (gated upstream)."""

    async def handle(self, ctx: HandlerContext) -> ChatResponse | None:
        from chat_application.skills import (
            parse_create_payment_params,
            run_create_payment_phase1,
        )

        if ctx.subject is None or not ctx.bearer_token:
            return None

        skill_name = ctx.decision.skill or "create_payment"
        if skill_name == "submit_payment":
            return await self._handle_submit(ctx)
        if skill_name == "approve_payment":
            return await self._handle_approve(ctx)

        params = parse_create_payment_params(ctx.message)
        if params is None:
            return finalize_chat_response(
                ctx.message,
                ctx.mode,
                answer=format_chat_response(
                    "I understood you want to create a payment, but I need an "
                    "instruction id, amount, and value date "
                    "(e.g. today/tomorrow or YYYY-MM-DD)."
                ),
                retrieval_ms=0.0,
                generation_ms=ctx.elapsed_ms(),
                path="skill",
                cypher_provenance="none",
                answer_synthesis="formatter",
                intent_id="skill.create_payment.incomplete",
            )

        result = await run_create_payment_phase1(
            ctx.message,
            subject=ctx.subject,
            user_token=ctx.bearer_token,
            user_session_id=ctx.session_id,
            params=params,
        )
        if result is None:
            return None
        return self._finalize_skill(ctx, result, skill="create_payment")

    async def _handle_submit(self, ctx: HandlerContext) -> ChatResponse | None:
        from chat_application.skills import (
            parse_submit_payment_params,
            run_submit_payment_phase1,
        )

        assert ctx.subject is not None
        params = parse_submit_payment_params(ctx.message)
        if params is None:
            return finalize_chat_response(
                ctx.message,
                ctx.mode,
                answer=format_chat_response(
                    "I understood you want to submit a payment for approval, but I "
                    "need a payment id "
                    "(e.g. `20260715-FICC-P-9`)."
                ),
                retrieval_ms=0.0,
                generation_ms=ctx.elapsed_ms(),
                path="skill",
                cypher_provenance="none",
                answer_synthesis="formatter",
                intent_id="skill.submit_payment.incomplete",
            )

        result = await run_submit_payment_phase1(
            ctx.message,
            subject=ctx.subject,
            user_token=ctx.bearer_token,
            user_session_id=ctx.session_id,
            params=params,
        )
        if result is None:
            return None
        return self._finalize_skill(ctx, result, skill="submit_payment")

    async def _handle_approve(self, ctx: HandlerContext) -> ChatResponse | None:
        from chat_application.skills import (
            parse_approve_payment_params,
            run_approve_payment_phase1,
        )

        assert ctx.subject is not None
        params = parse_approve_payment_params(ctx.message)
        if params is None:
            return finalize_chat_response(
                ctx.message,
                ctx.mode,
                answer=format_chat_response(
                    "I understood you want to approve a payment, but I need a "
                    "payment id (e.g. `20260715-FICC-P-9`)."
                ),
                retrieval_ms=0.0,
                generation_ms=ctx.elapsed_ms(),
                path="skill",
                cypher_provenance="none",
                answer_synthesis="formatter",
                intent_id="skill.approve_payment.incomplete",
            )

        result = await run_approve_payment_phase1(
            ctx.message,
            subject=ctx.subject,
            user_token=ctx.bearer_token,
            user_session_id=ctx.session_id,
            params=params,
        )
        if result is None:
            return None
        return self._finalize_skill(ctx, result, skill="approve_payment")

    def _finalize_skill(self, ctx: HandlerContext, result, *, skill: str) -> ChatResponse:
        confirmation = None
        if result.pending_id and result.confirmation is not None:
            confirmation = SkillConfirmationInfo(
                pending_id=result.pending_id,
                skill=skill,
                card=result.confirmation.to_api(),
            )
        return finalize_chat_response(
            ctx.message,
            ctx.mode,
            answer=format_chat_response(result.answer),
            retrieval_ms=0.0,
            generation_ms=ctx.elapsed_ms(),
            path="skill",
            cypher_provenance="none",
            answer_synthesis="formatter",
            intent_id=result.intent_id,
            skill_activities=result.activities,
            skill_confirmation=confirmation,
        )
