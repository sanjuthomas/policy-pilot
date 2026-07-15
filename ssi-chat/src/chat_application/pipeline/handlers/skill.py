from __future__ import annotations

from chat_application.formatting.response import format_chat_response
from chat_application.models import ChatResponse, SkillConfirmationInfo
from chat_application.observability.routing import finalize_chat_response
from chat_application.pipeline.handlers.base import HandlerContext


class CreatePaymentSkillHandler:
    """Mutation skill surface — Payments mode + PAYMENT_CREATOR only (gated upstream)."""

    async def handle(self, ctx: HandlerContext) -> ChatResponse | None:
        from chat_application.skills import (
            parse_create_payment_params,
            run_create_payment_phase1,
        )

        if ctx.subject is None or not ctx.bearer_token:
            return None

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

        confirmation = None
        if result.pending_id and result.confirmation is not None:
            confirmation = SkillConfirmationInfo(
                pending_id=result.pending_id,
                skill="create_payment",
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
