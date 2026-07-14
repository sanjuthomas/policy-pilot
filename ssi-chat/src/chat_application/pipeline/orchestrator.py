from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from chat_application.config import settings
from chat_application.cypher import extract_entity_ids, extract_uuids
from chat_application.formatting.response import format_chat_response
from chat_application.models import ChatMessage, ChatResponse, SearchMode
from chat_application.pipeline.heuristic_strategy import resolve_eligibility_target
from chat_application.pipeline.models import RouterDecision
from chat_application.pipeline.retrieve import execute_selective_retrieval
from chat_application.pipeline.route import route_question
from chat_application.routing_observability import (
    AnswerSynthesis,
    cypher_provenance_for_direct_intent,
    finalize_chat_response,
)

if TYPE_CHECKING:
    from chat_application.rag import RagService
    from chat_application.subject import Subject

logger = logging.getLogger(__name__)

_GRAPH_UNAVAILABLE_ANSWER = (
    "I couldn't retrieve Neo4j graph results for this question "
    "(query planning or execution failed). "
    "I won't invent an answer without graph evidence — please rephrase, "
    "include a specific entity id, or try again shortly."
)


class RagPipelineOrchestrator:
    """Route → retrieve → synthesize pipeline for RagService."""

    def __init__(self, service: RagService) -> None:
        self._service = service

    async def ask(
        self,
        message: str,
        history: list[ChatMessage],
        *,
        mode: SearchMode = "events",
        bearer_token: str | None = None,
        session_id: str | None = None,
        subject: "Subject | None" = None,
    ) -> ChatResponse:
        started = time.perf_counter()

        from chat_application.pipeline.follow_up import expand_follow_up_question

        message = expand_follow_up_question(message, history)

        decision = await route_question(self._service.ml_client, message, mode=mode)
        path = decision.path or decision.retrieval_strategy

        if path == "skill" and subject is not None and bearer_token:
            skill_response = await self._try_create_payment_skill(
                message,
                mode=mode,
                subject=subject,
                bearer_token=bearer_token,
                session_id=session_id,
                started=started,
                routed=True,
            )
            if skill_response is not None:
                return skill_response

        if path == "me" and subject is not None:
            me_response = await self._try_me_intent(
                message,
                mode=mode,
                subject=subject,
                started=started,
                decision=decision,
            )
            if me_response is not None:
                return me_response

        from chat_application.capabilities import capabilities_for

        allow_compliance_tools = subject is None or capabilities_for(subject).is_compliance

        if allow_compliance_tools:
            if path == "policy_summary":
                policy_summary_response = await self._try_policy_summary(
                    message,
                    mode=mode,
                    bearer_token=bearer_token,
                    session_id=session_id,
                    started=started,
                    decision=decision,
                )
                if policy_summary_response is not None:
                    return policy_summary_response

            if path == "policy_directory":
                policy_directory_response = await self._try_policy_directory(
                    message,
                    mode=mode,
                    bearer_token=bearer_token,
                    session_id=session_id,
                    started=started,
                    force=True,
                )
                if policy_directory_response is not None:
                    return policy_directory_response

            if path == "person_permissions":
                person_permission_response = await self._try_person_permissions(
                    message,
                    mode=mode,
                    bearer_token=bearer_token,
                    session_id=session_id,
                    started=started,
                    decision=decision,
                )
                if person_permission_response is not None:
                    return person_permission_response

            if path == "eligibility" or (
                mode == "policies" and path in {"eligibility", "graph", "vector", "hybrid"}
            ):
                eligibility_response = await self._try_eligibility(
                    message,
                    mode=mode,
                    decision=decision,
                    bearer_token=bearer_token,
                    session_id=session_id,
                    started=started,
                    force=path == "eligibility" or mode == "policies",
                )
                if eligibility_response is not None:
                    return eligibility_response

            if mode == "policies":
                from chat_application.policy_summary import policies_mode_guidance

                elapsed = (time.perf_counter() - started) * 1000
                return finalize_chat_response(
                    message,
                    mode,
                    answer=policies_mode_guidance(),
                    retrieval_ms=0.0,
                    generation_ms=elapsed,
                    path="eligibility",
                    cypher_provenance="none",
                    answer_synthesis="eligibility_api",
                )
        elif mode == "policies":
            elapsed = (time.perf_counter() - started) * 1000
            return finalize_chat_response(
                message,
                mode,
                answer=(
                    "Policies mode is available to compliance analysts. "
                    "As an operational user, ask me-centric questions such as "
                    "“Are there any other users like me?” or switch to Payments / Events mode."
                ),
                retrieval_ms=0.0,
                generation_ms=elapsed,
                path="eligibility",
                cypher_provenance="none",
                answer_synthesis="formatter",
            )

        # Neo4j direct YAML match is a latency fast-path for retrieval questions
        # (not primary NLU). Skip for dedicated skill/me/policy/eligibility handlers.
        if path not in {
            "skill",
            "me",
            "policy_summary",
            "policy_directory",
            "person_permissions",
            "eligibility",
        }:
            direct = await self._service._try_neo4j_direct_answer(message, mode=mode)
            if direct is not None:
                elapsed = (time.perf_counter() - started) * 1000
                return finalize_chat_response(
                    message,
                    mode,
                    answer=format_chat_response(direct.answer),
                    cypher=direct.cypher,
                    graph_rows=direct.graph_rows,
                    retrieval_ms=elapsed,
                    generation_ms=0.0,
                    path="neo4j_direct",
                    cypher_provenance=cypher_provenance_for_direct_intent(
                        direct.intent_id,
                        source=direct.source,
                    ),
                    answer_synthesis="formatter",
                    intent_id=direct.intent_id,
                )

        execution_strategy = decision.retrieval_strategy
        if execution_strategy == "eligibility":
            execution_strategy = "graph"

        search_source = self._search_source_for_mode(mode)
        event_ids = extract_uuids(message)
        entity_ids = extract_entity_ids(message)

        retrieval = await execute_selective_retrieval(
            self._service,
            message=message,
            mode=mode,
            strategy=execution_strategy,
            limit=settings.retrieval_limit,
            search_source=search_source,
            event_ids=event_ids,
            entity_ids=entity_ids,
        )
        retrieval_ms = (time.perf_counter() - started) * 1000

        graph_result = retrieval.graph_result
        graph_provenance = graph_result.get("cypher_provenance") or "none"
        if self._should_short_circuit_graph_unavailable(
            execution_strategy, graph_result
        ):
            logger.warning(
                "short-circuiting Gemini synthesis: graph strategy with unavailable graph "
                "(provenance=%s)",
                graph_provenance,
            )
            return finalize_chat_response(
                message,
                mode,
                answer=format_chat_response(_GRAPH_UNAVAILABLE_ANSWER),
                sources=[self._service._to_source(hit) for hit in retrieval.merged],
                cypher=graph_result.get("cypher"),
                graph_rows=retrieval.graph_rows,
                retrieval_ms=retrieval_ms,
                generation_ms=0.0,
                path="full_rag",
                cypher_provenance=graph_provenance,
                answer_synthesis="formatter",
                intent_id="graph.unavailable",
            )

        gen_started = time.perf_counter()
        answer, answer_synthesis = await self._synthesize(
            message,
            history,
            mode=mode,
            entity_ids=entity_ids,
            merged=retrieval.merged,
            graph_result=graph_result,
        )
        generation_ms = (time.perf_counter() - gen_started) * 1000

        return finalize_chat_response(
            message,
            mode,
            answer=answer,
            sources=[self._service._to_source(hit) for hit in retrieval.merged],
            cypher=graph_result.get("cypher"),
            graph_rows=retrieval.graph_rows,
            retrieval_ms=retrieval_ms,
            generation_ms=max(generation_ms, 0.0),
            path="full_rag",
            cypher_provenance=graph_provenance,
            answer_synthesis=answer_synthesis,
        )

    @staticmethod
    def _should_short_circuit_graph_unavailable(
        strategy: str,
        graph_result: dict[str, Any],
    ) -> bool:
        """Pure graph routes must not invent answers when Neo4j produced no evidence.

        Successful empty queries still set ``cypher`` (0 rows is a real answer). Failures
        and missing plans leave no Cypher and no rows — those must not call Gemini.
        """
        if strategy != "graph":
            return False
        if graph_result.get("cypher") or graph_result.get("rows"):
            return False
        return True

    async def _try_create_payment_skill(
        self,
        message: str,
        *,
        mode: SearchMode,
        subject: Subject,
        bearer_token: str,
        session_id: str | None,
        started: float,
        routed: bool = False,
    ) -> ChatResponse | None:
        from chat_application.models import SkillConfirmationInfo
        from chat_application.skills import (
            parse_create_payment_params,
            run_create_payment_phase1,
        )

        params = parse_create_payment_params(message)
        if params is None:
            if routed:
                # Router selected skill but slots are incomplete — explain, don't fall through.
                elapsed = (time.perf_counter() - started) * 1000
                return finalize_chat_response(
                    message,
                    mode,
                    answer=format_chat_response(
                        "I understood you want to create a payment, but I need an "
                        "instruction id, amount, and value date "
                        "(e.g. today/tomorrow or YYYY-MM-DD)."
                    ),
                    retrieval_ms=0.0,
                    generation_ms=elapsed,
                    path="skill",
                    cypher_provenance="none",
                    answer_synthesis="formatter",
                    intent_id="skill.create_payment.incomplete",
                )
            return None

        result = await run_create_payment_phase1(
            message,
            subject=subject,
            user_token=bearer_token,
            user_session_id=session_id,
            params=params,
        )
        if result is None:
            return None

        elapsed = (time.perf_counter() - started) * 1000
        confirmation = None
        if result.pending_id and result.confirmation is not None:
            confirmation = SkillConfirmationInfo(
                pending_id=result.pending_id,
                skill="create_payment",
                card=result.confirmation.to_api(),
            )
        return finalize_chat_response(
            message,
            mode,
            answer=format_chat_response(result.answer),
            retrieval_ms=0.0,
            generation_ms=elapsed,
            path="skill",
            cypher_provenance="none",
            answer_synthesis="formatter",
            intent_id=result.intent_id,
            skill_activities=result.activities,
            skill_confirmation=confirmation,
        )

    async def _try_me_intent(
        self,
        message: str,
        *,
        mode: SearchMode,
        subject: Subject,
        started: float,
        decision: RouterDecision | None = None,
    ) -> ChatResponse | None:
        from chat_application.me import me_intent_from_router, try_me_intent

        intent = None
        if decision is not None:
            intent = me_intent_from_router(decision, message)
        result = await try_me_intent(message, subject=subject, intent=intent)
        if result is None:
            return None

        elapsed = (time.perf_counter() - started) * 1000
        return finalize_chat_response(
            message,
            mode,
            answer=format_chat_response(result.answer),
            retrieval_ms=0.0,
            generation_ms=elapsed,
            path="eligibility",
            cypher_provenance="none",
            answer_synthesis="formatter",
            intent_id=result.intent_id,
        )

    async def _try_policy_summary(
        self,
        message: str,
        *,
        mode: SearchMode,
        bearer_token: str | None,
        session_id: str | None,
        started: float,
        decision: RouterDecision | None = None,
    ) -> ChatResponse | None:
        domain = decision.policy_domain if decision else None
        action = decision.policy_action if decision else None
        answer = await self._service._answer_policy_summary(
            message,
            mode=mode,
            bearer_token=bearer_token,
            session_id=session_id,
            domain=domain,
            action=action,
        )
        if answer is None:
            return None

        elapsed = (time.perf_counter() - started) * 1000
        return finalize_chat_response(
            message,
            mode,
            answer=answer,
            retrieval_ms=0.0,
            generation_ms=elapsed,
            path="eligibility",
            cypher_provenance="none",
            answer_synthesis="eligibility_api",
        )

    async def _try_policy_directory(
        self,
        message: str,
        *,
        mode: SearchMode,
        bearer_token: str | None,
        session_id: str | None,
        started: float,
        force: bool = False,
    ) -> ChatResponse | None:
        answer = await self._service._answer_payment_approval_directory(
            message,
            bearer_token=bearer_token,
            session_id=session_id,
            force=force,
        )
        if answer is None:
            return None

        elapsed = (time.perf_counter() - started) * 1000
        return finalize_chat_response(
            message,
            mode,
            answer=answer,
            retrieval_ms=0.0,
            generation_ms=elapsed,
            path="policy_directory",
            cypher_provenance="none",
            answer_synthesis="policy_directory_api",
        )

    async def _try_person_permissions(
        self,
        message: str,
        *,
        mode: SearchMode,
        bearer_token: str | None,
        session_id: str | None,
        started: float,
        decision: RouterDecision | None = None,
    ) -> ChatResponse | None:
        person_query = decision.person_query if decision else None
        answer = await self._service._answer_person_permission_summary(
            message,
            bearer_token=bearer_token,
            session_id=session_id,
            person_query=person_query,
        )
        if answer is None:
            return None

        elapsed = (time.perf_counter() - started) * 1000
        return finalize_chat_response(
            message,
            mode,
            answer=answer,
            retrieval_ms=0.0,
            generation_ms=elapsed,
            path="eligibility",
            cypher_provenance="none",
            answer_synthesis="eligibility_api",
        )

    async def _try_eligibility(
        self,
        message: str,
        *,
        mode: SearchMode,
        decision: RouterDecision,
        bearer_token: str | None,
        session_id: str | None,
        started: float,
        force: bool = False,
    ) -> ChatResponse | None:
        from chat_application.cypher import extract_payment_ids
        from chat_application.pipeline.heuristic_strategy import (
            is_eligibility_question_heuristic,
        )

        path = decision.path or decision.retrieval_strategy
        if path != "eligibility" and decision.retrieval_strategy != "eligibility" and not force:
            return None

        # Policies mode: only run live eligible-approvers for true who-can / entity-id questions
        # when the router did not explicitly choose eligibility.
        if (mode == "policies" or force) and path != "eligibility":
            if not is_eligibility_question_heuristic(message):
                if not extract_entity_ids(message) and not extract_payment_ids(message):
                    return None

        target = decision.eligibility_target or resolve_eligibility_target(message, mode=mode)
        if target == "payment":
            answer = await self._service._answer_payment_eligible_approvers(
                message,
                bearer_token=bearer_token,
                session_id=session_id,
            )
        elif target == "instruction":
            answer = await self._service._answer_instruction_eligible_approvers(
                message,
                bearer_token=bearer_token,
                session_id=session_id,
            )
        else:
            return None

        if answer is None:
            return None

        elapsed = (time.perf_counter() - started) * 1000
        return finalize_chat_response(
            message,
            mode,
            answer=answer,
            retrieval_ms=0.0,
            generation_ms=elapsed,
            path="eligibility",
            cypher_provenance="none",
            answer_synthesis="eligibility_api",
        )

    @staticmethod
    def _search_source_for_mode(mode: SearchMode) -> str | None:
        if mode == "events":
            return "security_events"
        if mode == "instructions":
            return "instruction_state"
        if mode == "payments":
            return "payment"
        if mode == "policies":
            return None
        return None

    async def _synthesize(
        self,
        message: str,
        history: list[ChatMessage],
        *,
        mode: SearchMode,
        entity_ids: list[str],
        merged: list[Any],
        graph_result: dict[str, Any],
    ) -> tuple[str, AnswerSynthesis]:
        from chat_application.cypher import (
            format_facet_aggregate_answer,
            instruction_id_from_list_payments_question,
            is_alert_ranking_question,
            is_cross_entity_reciprocal_approval_question,
            is_instruction_versions_list_question,
            is_max_payments_per_instruction_question,
            is_payment_list_question,
            is_payment_versions_list_question,
            is_payments_for_instruction_question,
            plan_graph_queries,
        )
        from chat_application.formatting.neo4j import (
            format_cross_entity_reciprocal_approval,
            format_instruction_versions_table,
            format_payment_versions_table,
            format_security_event_alert_list,
        )
        from chat_application.neo4j_intents import _format_planned_graph_answer
        from chat_application.rag import (
            _format_alert_ranking_answer,
            _format_instruction_count_aggregate_answer,
            _format_largest_payment_answer,
            _format_max_payments_per_instruction_answer,
            _format_payment_count_aggregate_answer,
            _format_payment_list_answer,
            _format_payment_total_amount_answer,
            _format_payments_above_amount_answer,
            _format_payments_for_instruction_answer,
            _format_security_event_alert_count_answer,
            _format_security_event_count_aggregate_answer,
            _format_security_event_group_by_lob_answer,
            _is_instruction_approval_question,
            _is_payment_approval_question,
            _should_format_facet_aggregate,
            _should_format_instruction_count_aggregate,
            _should_format_largest_payment,
            _should_format_payment_count_aggregate,
            _should_format_payment_total_amount,
            _should_format_payments_above_amount,
            _should_format_security_event_alert_count,
            _should_format_security_event_alert_list,
            _should_format_security_event_count_aggregate,
            _should_format_security_event_group_by_lob,
        )

        context = self._service._build_context(
            merged,
            graph_result["rows"],
            graph_result.get("cypher"),
            graph_unavailable=graph_result.get("graph_unavailable", False),
            mode=mode,
        )
        chat_history = [{"role": item.role, "content": item.content} for item in history[-8:]]

        answer: str | None = None
        answer_synthesis: AnswerSynthesis = "gemini_full"

        if _is_instruction_approval_question(message, mode):
            answer = await self._service._synthesize_instruction_approval_answer(
                message, entity_ids, merged, graph_result["rows"]
            )
            if answer is not None:
                answer_synthesis = "gemini_why_only"
        if answer is None and _is_payment_approval_question(message, mode):
            answer = await self._service._synthesize_payment_approval_answer(
                message, entity_ids, merged, graph_result["rows"]
            )
            if answer is not None:
                answer_synthesis = "gemini_why_only"
        if answer is None and is_max_payments_per_instruction_question(message):
            answer = _format_max_payments_per_instruction_answer(graph_result["rows"])
            answer_synthesis = "formatter"
        if answer is None and _should_format_largest_payment(message, mode):
            answer = _format_largest_payment_answer(message, graph_result["rows"])
            answer_synthesis = "formatter"
        if answer is None and _should_format_payments_above_amount(message, mode):
            answer = _format_payments_above_amount_answer(message, graph_result["rows"])
            answer_synthesis = "formatter"
        if answer is None and is_payments_for_instruction_question(message):
            instruction_id = instruction_id_from_list_payments_question(message)
            if instruction_id:
                answer = _format_payments_for_instruction_answer(
                    instruction_id,
                    graph_result["rows"],
                    question=message,
                )
                answer_synthesis = "formatter"
        if answer is None and is_payment_list_question(message, mode=mode):
            answer = _format_payment_list_answer(message, graph_result["rows"])
            answer_synthesis = "formatter"
        if answer is None and is_alert_ranking_question(message, mode=mode):
            answer = _format_alert_ranking_answer(message, graph_result["rows"])
            answer_synthesis = "formatter"
        if answer is None and _should_format_payment_total_amount(message, mode):
            answer = _format_payment_total_amount_answer(message, graph_result["rows"])
            answer_synthesis = "formatter"
        if answer is None and _should_format_payment_count_aggregate(message, mode):
            answer = _format_payment_count_aggregate_answer(message, graph_result["rows"])
            answer_synthesis = "formatter"
        if answer is None and _should_format_facet_aggregate(message, mode):
            answer = format_facet_aggregate_answer(message, graph_result["rows"], mode=mode)
            answer_synthesis = "formatter"
        if answer is None and _should_format_instruction_count_aggregate(message, mode):
            answer = _format_instruction_count_aggregate_answer(message, graph_result["rows"])
            answer_synthesis = "formatter"
        if answer is None and _should_format_security_event_count_aggregate(message, mode):
            answer = _format_security_event_count_aggregate_answer(message, graph_result["rows"])
            answer_synthesis = "formatter"
        if answer is None and _should_format_security_event_alert_count(message, mode):
            answer = _format_security_event_alert_count_answer(message, graph_result["rows"])
            answer_synthesis = "formatter"
        if answer is None and _should_format_security_event_alert_list(message, mode):
            answer = format_security_event_alert_list(message, graph_result["rows"])
            answer_synthesis = "formatter"
        if answer is None and _should_format_security_event_group_by_lob(message, mode):
            answer = _format_security_event_group_by_lob_answer(
                message, graph_result["rows"]
            )
            answer_synthesis = "formatter"
        if answer is None and is_instruction_versions_list_question(message, mode=mode):
            answer = format_instruction_versions_table(message, graph_result["rows"])
            answer_synthesis = "formatter"
        if answer is None and is_payment_versions_list_question(message, mode=mode):
            answer = format_payment_versions_table(message, graph_result["rows"])
            answer_synthesis = "formatter"
        if answer is None and is_cross_entity_reciprocal_approval_question(message):
            planned = plan_graph_queries(message, mode=mode)
            if planned:
                answer = _format_planned_graph_answer(
                    message,
                    mode=mode,
                    planned=planned,
                    rows=graph_result["rows"],
                )
            if answer is None:
                answer = format_cross_entity_reciprocal_approval(
                    message, graph_result["rows"]
                )
            answer_synthesis = "formatter"
        if answer is None:
            answer = await self._service.ml_client.synthesize_answer(
                message, context, chat_history, mode=mode
            )
            answer_synthesis = "gemini_full"

        return format_chat_response(answer), answer_synthesis
