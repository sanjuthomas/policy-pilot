from __future__ import annotations

from typing import Literal

from cypher_builder import query_engine as qe
from cypher_builder.models import GraphIntent, GraphQueryPlan


class CypherQueryBuilder:
    """Render structured graph query plans to validated read-only Cypher."""

    def alert_count_today(self) -> list[tuple[str, str]]:
        return qe._alert_count_today_queries()

    def alert_ranking(
        self,
        *,
        time_filter: str,
        payments_only: bool = False,
        instructions_only: bool = False,
    ) -> list[tuple[str, str]]:
        return qe._alert_ranking_queries(
            time_filter=time_filter,
            payments_only=payments_only,
            instructions_only=instructions_only,
        )

    def instruction_approval_lookup(self, instruction_id: str) -> list[tuple[str, str]]:
        return qe._instruction_approval_lookup_queries(instruction_id)

    def instruction_approver_via_payment(self, payment_id: str) -> list[tuple[str, str]]:
        return qe._instruction_approver_via_payment_queries(payment_id)

    def instruction_count(
        self, question: str, flags: dict[str, bool]
    ) -> list[tuple[str, str]]:
        return qe._instruction_count_queries(question, flags)

    def facet_aggregate(
        self, question: str, *, mode: str
    ) -> list[tuple[str, str]] | None:
        from cypher_builder.facets import facet_aggregate_queries

        return facet_aggregate_queries(question, mode=mode)

    def instruction_detail(self, instruction_id: str) -> list[tuple[str, str]]:
        return qe._instruction_detail_by_id_queries(instruction_id)

    def instruction_versions(self, instruction_id: str) -> list[tuple[str, str]]:
        return qe._instruction_versions_by_id_queries(instruction_id)

    def payment_versions(self, payment_id: str) -> list[tuple[str, str]]:
        return qe._payment_versions_by_id_queries(payment_id)

    def instruction_duplicate_routes(self, *, lob: str | None = None) -> list[tuple[str, str]]:
        return qe._instruction_duplicate_routes_queries(lob=lob)

    def instruction_list_by_status(
        self, *, status: str, lob: str | None = None
    ) -> list[tuple[str, str]]:
        return qe._instruction_list_by_status_queries(status=status, lob=lob)

    def instruction_list_by_type(
        self, *, instruction_type: str, lob: str | None = None
    ) -> list[tuple[str, str]]:
        return qe._instruction_list_by_type_queries(instruction_type=instruction_type, lob=lob)

    def instruction_mutual_approval(self) -> list[tuple[str, str]]:
        return qe._instruction_mutual_approval_queries()

    def cross_entity_reciprocal_approval(self) -> list[tuple[str, str]]:
        return qe._cross_entity_reciprocal_approval_queries()

    def instruction_security_event_timeline(
        self, instruction_id: str
    ) -> list[tuple[str, str]]:
        return qe._instruction_security_event_timeline_queries(instruction_id)

    def instruction_self_approval(self) -> list[tuple[str, str]]:
        return qe._instruction_self_approval_queries()

    def instruction_subordinate_approver(self) -> list[tuple[str, str]]:
        return qe._instruction_subordinate_approver_queries()

    def instructions_created_by_user(self, user_id: str) -> list[tuple[str, str]]:
        return qe._instructions_created_by_user_queries(user_id)

    def largest_payment(
        self, question: str, flags: dict[str, bool]
    ) -> list[tuple[str, str]]:
        return qe._largest_payment_queries(question, flags)

    def max_payments_per_instruction(self) -> list[tuple[str, str]]:
        return qe._max_payments_per_instruction_queries()

    def payment_aggregate(
        self, question: str, flags: dict[str, bool], *, sum_amount: bool
    ) -> list[tuple[str, str]]:
        return qe._payment_aggregate_queries(question, flags, sum_amount=sum_amount)

    def payments_above_amount(
        self,
        question: str,
        flags: dict[str, bool],
        *,
        min_amount: float,
    ) -> list[tuple[str, str]]:
        return qe._payments_above_amount_queries(question, flags, min_amount=min_amount)

    def payment_approval_lookup(self, payment_id: str) -> list[tuple[str, str]]:
        return qe._payment_approval_lookup_queries(payment_id)

    def payment_detail(self, payment_id: str) -> list[tuple[str, str]]:
        return qe._payment_detail_by_id_queries(payment_id)

    def payments_for_instruction(
        self, instruction_id: str, *, status: str | None = None
    ) -> list[tuple[str, str]]:
        return qe._payments_for_instruction_queries(instruction_id, status=status)

    def security_event_alert_count(
        self,
        *,
        time_filter: str,
        domain: str,
    ) -> list[tuple[str, str]]:
        return qe._security_event_alert_count_queries(time_filter=time_filter, domain=domain)

    def security_event_count(
        self,
        *,
        time_filter: str,
        domain: str,
    ) -> list[tuple[str, str]]:
        return qe._security_event_count_queries(time_filter=time_filter, domain=domain)

    def instruction_payment_count_list(self) -> list[tuple[str, str]]:
        return qe._instruction_payment_count_list_queries()

    def instructions_without_payments(self, question: str) -> list[tuple[str, str]]:
        return qe._instructions_without_payments_queries(question)

    def payment_list(
        self, question: str, flags: dict[str, bool]
    ) -> list[tuple[str, str]]:
        return qe._payment_list_queries(question, flags)

    def security_event_alert_list(
        self,
        *,
        time_filter: str,
        domain: str,
        approval_only: bool = False,
    ) -> list[tuple[str, str]]:
        return qe._security_event_alert_list_queries(
            time_filter=time_filter, domain=domain, approval_only=approval_only
        )

    def security_event_group_by_lob(
        self,
        *,
        time_filter: str,
        domain: str,
        scope: Literal["alert", "all"],
    ) -> list[tuple[str, str]]:
        return qe._security_event_group_by_lob_queries(
            time_filter=time_filter, domain=domain, scope=scope
        )


def flags_from_plan(plan: GraphQueryPlan) -> dict[str, bool]:
    time_window = plan.time_window or "all"
    domain = plan.domain or "all"
    return {
        "count": plan.operation in (None, "count", "sum"),
        "ranking": plan.operation == "rank",
        "denial": bool(plan.denial),
        "today": time_window == "today",
        "week": time_window == "week",
        "alerts": (plan.severity or "").upper() == "ALERT" or bool(plan.denial),
        "payments": domain == "payments",
        "instructions": domain == "instructions",
    }


def time_filter_from_flags(flags: dict[str, bool]) -> str:
    return qe._time_filter_cypher(flags)


def plans_from_graph_query(
    plan: GraphQueryPlan,
    *,
    mode: str,
    question: str = "",
) -> list[tuple[str, str]] | None:
    """Map a structured GraphQueryPlan to rendered Cypher query pairs."""
    builder = CypherQueryBuilder()
    flags = flags_from_plan(plan)
    time_filter = time_filter_from_flags(flags)

    if plan.intent == GraphIntent.ALERT_COUNT_TODAY:
        return builder.alert_count_today()

    if plan.intent == GraphIntent.INSTRUCTION_APPROVER_VIA_PAYMENT:
        if not plan.payment_id:
            return None
        return builder.instruction_approver_via_payment(plan.payment_id)

    if plan.intent == GraphIntent.INSTRUCTION_APPROVAL:
        if not plan.instruction_id:
            return None
        return builder.instruction_approval_lookup(plan.instruction_id)

    if plan.intent == GraphIntent.PAYMENT_APPROVAL:
        if not plan.payment_id:
            return None
        return builder.payment_approval_lookup(plan.payment_id)

    if plan.intent == GraphIntent.INSTRUCTION_LOOKUP:
        if not plan.instruction_id:
            return None
        return builder.instruction_detail(plan.instruction_id)

    if plan.intent == GraphIntent.PAYMENTS_FOR_INSTRUCTION:
        if not plan.instruction_id:
            return None
        return builder.payments_for_instruction(plan.instruction_id, status=plan.status)

    if plan.intent == GraphIntent.MAX_PAYMENTS_PER_INSTRUCTION:
        return builder.max_payments_per_instruction()

    if plan.intent == GraphIntent.INSTRUCTION_COMPLIANCE:
        pattern = plan.compliance_pattern
        if pattern == "mutual":
            return builder.instruction_mutual_approval()
        if pattern == "self":
            return builder.instruction_self_approval()
        if pattern == "subordinate":
            return builder.instruction_subordinate_approver()
        if pattern == "duplicate_routes":
            return builder.instruction_duplicate_routes(lob=plan.owning_lob)
        return None

    if plan.intent == GraphIntent.INSTRUCTION_INVENTORY:
        if plan.user_id:
            return builder.instructions_created_by_user(plan.user_id)
        if plan.instruction_type:
            return builder.instruction_list_by_type(
                instruction_type=plan.instruction_type,
                lob=plan.owning_lob,
            )
        if plan.status:
            return builder.instruction_list_by_status(
                status=plan.status,
                lob=plan.owning_lob,
            )
        if plan.instruction_type is None and "SINGLE_USE" in question.upper():
            return builder.instruction_list_by_type(
                instruction_type="SINGLE_USE",
                lob=plan.owning_lob,
            )
        return None

    if plan.intent == GraphIntent.SECURITY_EVENT_RANK:
        if mode != "events":
            return None
        domain = plan.domain or "all"
        if domain == "payments":
            return builder.alert_ranking(time_filter=time_filter, payments_only=True)
        if domain == "instructions":
            return builder.alert_ranking(time_filter=time_filter, instructions_only=True)
        return builder.alert_ranking(time_filter=time_filter)

    if plan.intent == GraphIntent.PAYMENT_AGGREGATE:
        if mode not in ("payments", "all"):
            return None
        synthetic_question = _synthetic_payment_question(plan, question)
        sum_amount = plan.operation == "sum"
        return builder.payment_aggregate(synthetic_question, flags, sum_amount=sum_amount)

    if plan.intent == GraphIntent.SECURITY_EVENT_AGGREGATE:
        if mode not in ("events", "all") or not flags["count"]:
            return None
        domain = plan.domain or "all"
        question_flags = qe._question_flags(question) if question else {}
        wants_alerts = flags["alerts"] or question_flags.get("alerts", False)
        if wants_alerts:
            if domain == "payments":
                return builder.security_event_alert_count(
                    time_filter=time_filter, domain="payments"
                )
            if domain == "instructions":
                return builder.security_event_alert_count(
                    time_filter=time_filter, domain="instructions"
                )
            return builder.security_event_alert_count(time_filter=time_filter, domain="all")
        if domain == "payments":
            return builder.security_event_count(time_filter=time_filter, domain="payments")
        if domain == "instructions":
            return builder.security_event_count(time_filter=time_filter, domain="instructions")
        return builder.security_event_count(time_filter=time_filter, domain="all")

    if plan.intent == GraphIntent.INSTRUCTION_AGGREGATE:
        if mode != "instructions":
            return None
        synthetic_question = _synthetic_instruction_count_question(plan, question)
        return builder.instruction_count(synthetic_question, flags)

    return None


def _synthetic_payment_question(plan: GraphQueryPlan, question: str) -> str:
    parts = [question, "payment"]
    if plan.status:
        parts.append(plan.status.lower())
    if plan.owning_lob:
        parts.append(plan.owning_lob)
    if plan.time_window == "today":
        parts.append("today")
    elif plan.time_window == "week":
        parts.append("this week")
    if plan.use_value_date:
        parts.append("value date")
    if plan.operation == "sum":
        parts.extend(["total", "amount"])
    elif plan.operation == "count":
        parts.extend(["how many", "count"])
    return " ".join(parts)


def _synthetic_instruction_count_question(plan: GraphQueryPlan, question: str) -> str:
    parts = [question, "instruction", "how many"]
    if plan.status:
        parts.append(plan.status.lower())
    if plan.instruction_type:
        parts.append(plan.instruction_type.lower().replace("_", " "))
    if plan.owning_lob:
        parts.append(plan.owning_lob)
    if plan.time_window == "today":
        parts.append("today")
    elif plan.time_window == "week":
        parts.append("this week")
    return " ".join(parts)
