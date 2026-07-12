from __future__ import annotations

import json
import logging
import re
from typing import Any

from chat_application.authorization_client import (
    EligibilityClient,
    EligibilityClientError,
    format_eligible_approvers_answer,
    format_instruction_eligible_approvers_answer,
)
from chat_application.config import settings
from chat_application.cypher import (
    extract_entity_ids,
    extract_payment_ids,
    instruction_count_filters_from_question,
    is_analytics_question,
    is_count_question,
    is_instruction_approver_via_payment_question,
    is_instruction_count_aggregate_question,
    is_largest_payment_question,
    is_payment_amount_threshold_question,
    is_payment_count_aggregate_question,
    is_payment_id_lookup_for_instruction_question,
    is_payment_total_amount_question,
    is_payments_for_instruction_question,
    is_security_event_alert_count_question,
    is_security_event_alert_list_question,
    is_security_event_count_aggregate_question,
    is_security_event_group_by_lob_question,
    lob_filter_from_question,
    normalize_read_only_cypher,
    payment_aggregate_period_label,
    payment_amount_threshold_from_question,
    payment_status_filter_from_question,
    plan_graph_queries,
    plans_from_graph_query,
    ranking_period_label,
    security_event_group_by_lob_scope,
    validate_read_only_cypher,
)
from chat_application.formatting import (
    format_approval_auth_lines,
    format_markdown_table,
    format_money_amount,
    humanize_authorization_text,
    humanize_policy_basis,
    parse_authorization_basis,
)
from chat_application.ml_client import PolicyPilotMlClient
from chat_application.models import ChatMessage, ChatResponse, SearchMode, SourceHit
from chat_application.multimodal_search import MultimodalSearchClient
from chat_application.neo4j import Neo4jClient
from chat_application.neo4j_intents import try_neo4j_direct_answer
from chat_application.pipeline.orchestrator import RagPipelineOrchestrator
from chat_application.reranker import RankedHit, rrf_merge
from chat_application.subject import Subject

logger = logging.getLogger(__name__)


def _format_basis_join(basis: list[str] | None) -> str:
    if not basis:
        return ""
    return " | ".join(humanize_policy_basis(basis))


def _append_policy_basis(why: str, basis: list[str]) -> str:
    if not basis:
        return why
    readable = humanize_policy_basis(basis)
    table_rows = [[index, point] for index, point in enumerate(readable, start=1)]
    table = format_markdown_table(["#", "Policy check"], table_rows)
    return f"{why.rstrip()}\n\nPolicy basis ({len(readable)} checks):\n\n{table}"


def _is_instruction_approval_question(message: str, mode: SearchMode) -> bool:
    q = message.lower()
    if "approv" not in q:
        return False
    if is_instruction_approver_via_payment_question(message):
        return True
    if "payment" in q and "instruction" not in q:
        return False
    return mode == "instructions" or "instruction" in q


def _is_payment_approval_question(message: str, mode: SearchMode) -> bool:
    q = message.lower()
    if "approv" not in q:
        return False
    if is_instruction_approver_via_payment_question(message):
        return False
    if "instruction" in q and "payment" not in q:
        return False
    return mode == "payments" or "payment" in q


def _dedupe_payment_graph_rows(graph_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_payment_ids: set[str] = set()
    for row in graph_rows:
        payment_id = row.get("payment_id")
        if not payment_id or payment_id in seen_payment_ids:
            continue
        seen_payment_ids.add(payment_id)
        deduped.append(row)
    return deduped


def _format_payment_list_table(graph_rows: list[dict[str, Any]]) -> str:
    payment_rows = _dedupe_payment_graph_rows(graph_rows)
    table_rows = [
        [
            row.get("payment_id"),
            row.get("instruction_id") or "N/A",
            row.get("status") or "N/A",
            _format_payment_amount_display(row.get("amount"), row.get("currency")),
            row.get("value_date") or "N/A",
            row.get("owning_lob") or "N/A",
            row.get("creator_display") or "N/A",
            row.get("approver_display") or "N/A",
        ]
        for row in payment_rows
    ]
    if not table_rows:
        return "_No payments found._"
    return format_markdown_table(
        [
            "Payment ID",
            "Instruction ID",
            "Status",
            "Amount",
            "Value Date",
            "LOB",
            "Creator",
            "Approver",
        ],
        table_rows,
    )


def _format_payment_list_by_status_answer(message: str, graph_rows: list[dict[str, Any]]) -> str:
    payment_rows = _dedupe_payment_graph_rows(graph_rows)
    status = payment_status_filter_from_question(message) or "matching"
    if not payment_rows:
        return f"No payments in {status} state were found in the graph."
    return (
        f"Payments in {status} state ({len(payment_rows)}):\n\n"
        f"{_format_payment_list_table(payment_rows)}"
    )


def _format_largest_payment_answer(message: str, graph_rows: list[dict[str, Any]]) -> str:
    payment_rows = _dedupe_payment_graph_rows(graph_rows)
    period = payment_aggregate_period_label(message)
    scope = _payment_aggregate_scope_label(message)

    if not payment_rows:
        return f"No payments were found for the largest-payment query ({scope}, {period})."

    max_amount = max(float(row.get("amount") or 0) for row in payment_rows)
    top_rows = [
        row for row in payment_rows if float(row.get("amount") or 0) == max_amount
    ]
    amount_text = _format_payment_amount_display(
        max_amount, top_rows[0].get("currency")
    )

    q = message.lower()
    if len(top_rows) == 1:
        summary = f"The largest payment ({scope}, {period}) is {amount_text}."
        if re.search(r"\bwho\s+created\b", q):
            creator = top_rows[0].get("creator_display") or "unknown"
            summary = (
                f"The largest payment ({scope}, {period}) is {amount_text}, "
                f"created by **{creator}**."
            )
    else:
        summary = (
            f"The largest payment amount ({scope}, {period}) is {amount_text} "
            f"— {len(top_rows)} payment(s) tie at that amount."
        )

    return f"{summary}\n\n{_format_payment_list_table(top_rows)}"


def _format_payments_above_amount_answer(message: str, graph_rows: list[dict[str, Any]]) -> str:
    payment_rows = _dedupe_payment_graph_rows(graph_rows)
    threshold = payment_amount_threshold_from_question(message)
    threshold_text = _format_payment_amount_display(threshold, "USD")
    period = payment_aggregate_period_label(message)
    scope = _payment_aggregate_scope_label(message)
    q = message.lower()

    if not payment_rows:
        if re.search(r"\b(do we|are there|any)\b", q):
            return (
                f"No, there are no payments with an amount greater than {threshold_text} "
                f"({scope})."
            )
        return f"No payments found above {threshold_text} ({scope}, {period})."

    count = len(payment_rows)
    if is_count_question(message):
        summary = f"There are {count} payment(s) above {threshold_text} ({scope}, {period})."
    elif re.search(r"\b(do we|are there|any)\b", q):
        summary = (
            f"Yes, there are {count} payment(s) with an amount greater than "
            f"{threshold_text} ({scope})."
        )
    else:
        summary = f"Found {count} payment(s) above {threshold_text} ({scope}, {period})."

    return f"{summary}\n\n{_format_payment_list_table(payment_rows)}"


def _should_format_payments_above_amount(message: str, mode: SearchMode) -> bool:
    return mode in ("payments", "all") and is_payment_amount_threshold_question(message)


def _should_format_largest_payment(message: str, mode: SearchMode) -> bool:
    return mode in ("payments", "all") and is_largest_payment_question(message)


def _format_max_payments_per_instruction_answer(
    graph_rows: list[dict[str, Any]],
) -> str | None:
    if not graph_rows:
        return "No instruction payment counts were found in the graph."

    instruction_id = graph_rows[0].get("instruction_id")
    if not instruction_id:
        return None

    payment_rows = _dedupe_payment_graph_rows(graph_rows)
    table_rows = [
        [
            row.get("payment_id"),
            row.get("created_at") or "—",
            row.get("creator_display") or "—",
            row.get("approver_display") or "—",
        ]
        for row in payment_rows
    ]

    lines = [
        f"Instruction: {instruction_id}",
        f"Total payments: {len(table_rows)}",
        "",
    ]
    if table_rows:
        lines.append(
            format_markdown_table(
                ["Payment ID", "Created At", "Creator", "Approver"],
                table_rows,
            )
        )
    else:
        lines.append("_No payments found._")
    return "\n".join(lines)


def _format_payment_amount_display(amount: Any, currency: Any) -> str:
    return format_money_amount(amount, currency, currency_first=False)


def _format_payments_for_instruction_answer(
    instruction_id: str,
    graph_rows: list[dict[str, Any]],
    *,
    question: str | None = None,
) -> str:
    payment_rows = _dedupe_payment_graph_rows(graph_rows)
    table_rows = [
        [
            row.get("payment_id"),
            row.get("status") or "N/A",
            _format_payment_amount_display(row.get("amount"), row.get("currency")),
            row.get("value_date") or "N/A",
            row.get("owning_lob") or "N/A",
            row.get("creator_display") or "N/A",
            row.get("approver_display") or "N/A",
        ]
        for row in payment_rows
    ]

    if question and is_payment_id_lookup_for_instruction_question(question):
        if not table_rows:
            return f"No payment is linked to instruction `{instruction_id}` in the graph."
        if len(table_rows) == 1:
            payment_id = table_rows[0][0]
            return f"Payment `{payment_id}` is associated with instruction `{instruction_id}`."

    summary = f"There are {len(table_rows)} payments in total for instruction {instruction_id}."
    if not table_rows:
        return f"{summary}\n\n_No payments found._"

    return (
        f"{summary}\n\n"
        f"{format_markdown_table(['Payment ID', 'Status', 'Amount', 'Value Date', 'LOB', 'Creator', 'Approver'], table_rows)}"
    )


def _extract_alert_ranking_rows(graph_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in graph_rows
        if "alert_count" in row and "actor_display" in row
    ]


def _alert_ranking_domain_label(message: str) -> str:
    q = message.lower()
    if "payment" in q and "instruction" not in q:
        return "payment policy denial alerts"
    if "instruction" in q and "payment" not in q:
        return "instruction policy denial alerts"
    return "policy denial alerts"


def _format_alert_ranking_answer(message: str, graph_rows: list[dict[str, Any]]) -> str:
    ranking_rows = _extract_alert_ranking_rows(graph_rows)
    if not ranking_rows:
        return "No policy denial alert rankings were found in the graph."

    period = ranking_period_label(message)
    domain = _alert_ranking_domain_label(message)
    table_rows = [
        [
            row.get("actor_display") or "—",
            row.get("user_id") or "—",
            row.get("alert_count", 0),
            row.get("payment_alerts", 0),
            row.get("instruction_alerts", 0),
        ]
        for row in ranking_rows
    ]

    if len(ranking_rows) == 1:
        top = ranking_rows[0]
        summary = (
            f"The user with the most {domain} ({period}) is "
            f"{top.get('actor_display')} with {top.get('alert_count')} alert(s)."
        )
    else:
        summary = f"User ranking by {domain} ({period}): {len(table_rows)} user(s)."

    return (
        f"{summary}\n\n"
        f"{format_markdown_table(['User', 'User ID', 'Total Alerts', 'Payment Alerts', 'Instruction Alerts'], table_rows)}"
    )


def _payment_aggregate_scope_label(message: str) -> str:
    lob = lob_filter_from_question(message)
    return f"LOB {lob}" if lob else "all LOBs"


def _format_instruction_count_aggregate_answer(
    message: str, graph_rows: list[dict[str, Any]]
) -> str:
    if graph_rows and graph_rows[0].get("status") is not None:
        table_rows = [
            (row.get("status") or "unknown", int(row.get("total") or 0))
            for row in graph_rows
            if row.get("status") is not None
        ]
        if not table_rows:
            return "No instructions were found grouped by status."
        total = sum(count for _, count in table_rows)
        lob = lob_filter_from_question(message)
        period = payment_aggregate_period_label(message)
        qualifiers: list[str] = []
        if lob:
            qualifiers.append(f"LOB {lob}")
        if period != "all time":
            qualifiers.append(period)
        qualifier = f" ({', '.join(qualifiers)})" if qualifiers else ""
        return (
            f"Instruction counts by status{qualifier} ({total} total):\n\n"
            f"{format_markdown_table(['Status', 'Instructions'], table_rows)}"
        )

    if graph_rows and graph_rows[0].get("lob") is not None:
        table_rows = [
            (row.get("lob") or "unknown", int(row.get("total") or 0))
            for row in graph_rows
            if row.get("lob") is not None
        ]
        if not table_rows:
            return "No instructions were found grouped by LOB."
        return (
            "Instruction counts by LOB:\n\n"
            f"{format_markdown_table(['LOB', 'Instructions'], table_rows)}"
        )

    total = int(graph_rows[0].get("total") or 0) if graph_rows else 0
    status, instruction_type = instruction_count_filters_from_question(message)
    lob = lob_filter_from_question(message)
    period = payment_aggregate_period_label(message)

    qualifiers: list[str] = []
    if status:
        qualifiers.append(f"status {status}")
    if instruction_type:
        qualifiers.append(f"type {instruction_type}")
    if lob:
        qualifiers.append(f"LOB {lob}")
    if period != "all time":
        qualifiers.append(period)
    qualifier = f" ({', '.join(qualifiers)})" if qualifiers else ""

    if total == 1:
        return f"There is 1 instruction in the store{qualifier}."
    return f"There are {total} instructions in the store{qualifier}."


def _should_format_instruction_count_aggregate(message: str, mode: SearchMode) -> bool:
    return mode == "instructions" and is_instruction_count_aggregate_question(message)


def _should_format_facet_aggregate(message: str, mode: SearchMode) -> bool:
    return is_analytics_question(message, mode=mode)


def _format_security_event_count_aggregate_answer(
    message: str, graph_rows: list[dict[str, Any]]
) -> str:
    row = graph_rows[0] if graph_rows else {}
    total = int(row.get("total") or 0)
    alert_count = int(row.get("alert_count") or 0)
    info_count = int(row.get("info_count") or 0)
    period = payment_aggregate_period_label(message)
    qualifier = f" ({period})" if period != "all time" else ""

    if total == 0:
        return f"There are no security events in the system{qualifier}."

    if total == 1:
        return (
            f"There is 1 security event in the system{qualifier} "
            f"({alert_count} ALERT, {info_count} INFO)."
        )
    return (
        f"There are {total} security events in the system{qualifier} "
        f"({alert_count} ALERT, {info_count} INFO)."
    )


def _security_event_alert_scope_label(message: str) -> str:
    q = message.lower()
    if "payment" in q:
        return "payment"
    if "instruction" in q:
        return "instruction"
    return ""


def _format_security_event_alert_count_answer(
    message: str, graph_rows: list[dict[str, Any]]
) -> str:
    total = int(graph_rows[0].get("total") or 0) if graph_rows else 0
    scope = _security_event_alert_scope_label(message)
    period = payment_aggregate_period_label(message)

    if period == "today":
        suffix = " today"
    elif period == "this week":
        suffix = " this week"
    elif period != "all time":
        suffix = f" ({period})"
    else:
        suffix = ""

    scope_prefix = f"{scope} " if scope else ""

    if total == 0:
        return f"There were no {scope_prefix}ALERT events{suffix}.".replace("  ", " ")
    if total == 1:
        return f"There was 1 {scope_prefix}ALERT event{suffix}.".replace("  ", " ")
    return f"There were {total} {scope_prefix}ALERT events{suffix}.".replace("  ", " ")


def _should_format_security_event_count_aggregate(message: str, mode: SearchMode) -> bool:
    return mode in ("events", "all") and is_security_event_count_aggregate_question(
        message, mode=mode
    )


def _should_format_security_event_alert_count(message: str, mode: SearchMode) -> bool:
    return mode in ("events", "all") and is_security_event_alert_count_question(
        message, mode=mode
    )


def _should_format_security_event_alert_list(message: str, mode: SearchMode) -> bool:
    return mode in ("events", "all") and is_security_event_alert_list_question(
        message, mode=mode
    )


def _format_security_event_group_by_lob_answer(
    message: str, graph_rows: list[dict[str, Any]]
) -> str:
    scope = security_event_group_by_lob_scope(message)
    scope_label = _security_event_alert_scope_label(message)
    scope_prefix = f"{scope_label} " if scope_label else ""
    period = payment_aggregate_period_label(message)
    period_suffix = f" ({period})" if period != "all time" else ""

    if scope == "alert":
        table_rows = [
            (row.get("lob") or "unknown", int(row.get("alert_count") or 0))
            for row in graph_rows
            if row.get("lob") is not None or row.get("alert_count") is not None
        ]
        if not table_rows:
            return "No ALERT events were found to group by LOB."

        total = sum(count for _, count in table_rows)
        if total == 0:
            return f"There were no {scope_prefix}ALERT events{period_suffix}."

        return (
            f"ALERT counts by LOB for {scope_prefix}events{period_suffix} ({total} total):\n\n"
            f"{format_markdown_table(['LOB', 'Alerts'], table_rows)}"
        ).replace("  ", " ")

    table_rows = [
        (
            row.get("lob") or "unknown",
            int(row.get("event_count") or 0),
            int(row.get("alert_count") or 0),
            int(row.get("info_count") or 0),
        )
        for row in graph_rows
        if row.get("lob") is not None or row.get("event_count") is not None
    ]
    if not table_rows:
        return "No security events were found to group by LOB."

    total = sum(count for _, count, _, _ in table_rows)
    if total == 0:
        return f"There were no {scope_prefix}security events{period_suffix}."

    return (
        f"Security event counts by LOB for {scope_prefix}events{period_suffix} ({total} total):\n\n"
        f"{format_markdown_table(['LOB', 'Events', 'ALERT', 'INFO'], table_rows)}"
    ).replace("  ", " ")


def _format_security_event_alert_group_by_lob_answer(
    message: str, graph_rows: list[dict[str, Any]]
) -> str:
    return _format_security_event_group_by_lob_answer(message, graph_rows)


def _should_format_security_event_group_by_lob(message: str, mode: SearchMode) -> bool:
    return mode in ("events", "all") and is_security_event_group_by_lob_question(
        message, mode=mode
    )


def _should_format_security_event_alert_group_by_lob(message: str, mode: SearchMode) -> bool:
    return _should_format_security_event_group_by_lob(message, mode)


def _format_payment_count_aggregate_answer(message: str, graph_rows: list[dict[str, Any]]) -> str:
    if graph_rows and graph_rows[0].get("status") is not None:
        table_rows = [
            (row.get("status") or "unknown", int(row.get("total") or 0))
            for row in graph_rows
            if row.get("status") is not None
        ]
        if not table_rows:
            return "No payments were found grouped by status."
        total = sum(count for _, count in table_rows)
        period = payment_aggregate_period_label(message)
        scope = _payment_aggregate_scope_label(message)
        period_suffix = f", {period}" if period != "all time" else ""
        return (
            f"Payment counts by status for {scope}{period_suffix} ({total} total):\n\n"
            f"{format_markdown_table(['Status', 'Payments'], table_rows)}"
        )

    total = graph_rows[0].get("total", 0) if graph_rows else 0
    period = payment_aggregate_period_label(message)
    scope = _payment_aggregate_scope_label(message)
    return f"There are {total} matching payment(s) for {scope} ({period})."


def _format_payment_total_amount_answer(message: str, graph_rows: list[dict[str, Any]]) -> str | None:
    amount_rows = [
        row
        for row in graph_rows
        if row.get("total_amount") is not None or row.get("payment_count") is not None
    ]
    if not amount_rows:
        return "No matching payments were found in the graph."

    period = payment_aggregate_period_label(message)
    scope = _payment_aggregate_scope_label(message)
    lines = [f"Approved payment totals for {scope} ({period}):"]

    for row in amount_rows:
        count = int(row.get("payment_count") or 0)
        amount_text = _format_payment_amount_display(row.get("total_amount"), row.get("currency"))
        if count == 0:
            lines.append(f"- {amount_text}: no payments")
        elif count == 1:
            lines.append(f"- Total: {amount_text} across 1 payment.")
        else:
            lines.append(f"- Total: {amount_text} across {count} payments.")

    return "\n".join(lines)


def _should_format_payment_count_aggregate(message: str, mode: SearchMode) -> bool:
    return mode in ("payments", "all") and is_payment_count_aggregate_question(message)


def _should_format_payment_total_amount(message: str, mode: SearchMode) -> bool:
    return mode in ("payments", "all") and is_payment_total_amount_question(message)


def _should_lookup_payment_ids(message: str, uuids: list[str], mode: SearchMode) -> bool:
    if not uuids:
        return False
    if is_payments_for_instruction_question(message):
        return False
    if is_instruction_approver_via_payment_question(message):
        return True
    if mode == "payments":
        return True
    return "payment" in message.lower()


def _display_from_snap_user(snap: dict[str, Any], field: str) -> str:
    user = snap.get(field) or {}
    family_name = user.get("family_name")
    given_name = user.get("given_name")
    user_id = user.get("user_id") or ""
    if family_name and given_name:
        return f"{family_name}, {given_name} ({user_id})"
    return user_id


def _instruction_lifecycle_party_lines(payload: dict[str, Any], snap: dict[str, Any]) -> str:
    status = (snap.get("status") or payload.get("status") or "").upper()
    lines: list[str] = []

    if status == "REJECTED":
        rejected_by = payload.get("rejector_display") or _display_from_snap_user(snap, "rejected_by")
        if rejected_by:
            lines.append(f"rejected_by={rejected_by}")
        rejected_at = payload.get("rejected_at") or snap.get("rejected_at")
        if rejected_at:
            lines.append(f"rejected_at={rejected_at}")
        reason = payload.get("rejection_reason") or snap.get("rejection_reason")
        if reason:
            lines.append(f"rejection_reason={reason}")
    elif status in ("APPROVED", "USED", "SUSPENDED"):
        approver = payload.get("approver_display") or _display_from_snap_user(snap, "approved_by")
        if approver:
            lines.append(f"approver={approver}")
        approved_at = payload.get("approved_at") or snap.get("approved_at")
        if approved_at:
            lines.append(f"approved_at={approved_at}")

    return "\n  ".join(lines)


class RagService:
    def __init__(
        self,
        *,
        ml_client: PolicyPilotMlClient,
        multimodal: MultimodalSearchClient,
        neo4j: Neo4jClient,
    ) -> None:
        self.ml_client = ml_client
        self.multimodal = multimodal
        self.neo4j = neo4j
        self._eligibility = EligibilityClient()
        self._pipeline = RagPipelineOrchestrator(self)

    async def _try_neo4j_direct_answer(
        self,
        message: str,
        *,
        mode: SearchMode,
    ):
        try:
            result = await try_neo4j_direct_answer(self.neo4j, message, mode=mode)
        except Exception as exc:
            logger.warning("neo4j direct answer failed: %s", exc)
            return None
        if result is None:
            return None
        return result

    async def ask(
        self,
        message: str,
        history: list[ChatMessage],
        *,
        mode: SearchMode = "events",
        bearer_token: str | None = None,
        session_id: str | None = None,
        subject: Subject | None = None,
    ) -> ChatResponse:
        """Run the full RAG pipeline (route → retrieve → synthesize)."""
        return await self._pipeline.ask(
            message,
            history,
            mode=mode,
            bearer_token=bearer_token,
            session_id=session_id,
            subject=subject,
        )

    async def _search_vector(
        self, query: str, limit: int, source: str | None = None
    ) -> list[dict[str, Any]]:
        try:
            vector = await self.ml_client.embed(query)
            return await self.multimodal.search_vector(vector, limit=limit, source=source)
        except Exception as exc:
            logger.warning("vector search failed: %s", exc)
            return []

    async def _search_bm25(
        self, query: str, limit: int, source: str | None = None
    ) -> list[dict[str, Any]]:
        try:
            return await self.multimodal.search_bm25(query, limit=limit, source=source)
        except Exception as exc:
            logger.warning("BM25 search failed: %s", exc)
            return []

    async def _lookup_exact_event_ids(
        self, event_ids: list[str]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        hits: list[dict[str, Any]] = []
        graph_rows: list[dict[str, Any]] = []

        for event_id in event_ids:
            store_hit = await self.multimodal.fetch_by_event_id(event_id)
            if store_hit is not None:
                hits.append(store_hit)

            try:
                rows = await self.neo4j.lookup_instruction_for_event(event_id)
            except Exception as exc:
                logger.warning("exact graph lookup failed for %s: %s", event_id, exc)
                rows = []

            for row in rows:
                if row.get("instruction_id"):
                    graph_rows.append(row)

        return hits, graph_rows

    async def _lookup_exact_instruction_ids(
        self, instruction_ids: list[str], message: str
    ) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        approval_question = "approv" in message.lower()

        for instruction_id in instruction_ids:
            state_hit = await self.multimodal.fetch_by_instruction_id(instruction_id)
            if state_hit is not None:
                hits.append(state_hit)

            if approval_question:
                approve_hits = await self.multimodal.fetch_instruction_approve_events(
                    instruction_id
                )
                hits.extend(approve_hits)

        return hits

    async def _lookup_exact_payment_ids(
        self, payment_ids: list[str], message: str
    ) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        approval_question = "approv" in message.lower()
        via_instruction = is_instruction_approver_via_payment_question(message)

        for payment_id in payment_ids:
            fact_hit = await self.multimodal.fetch_by_payment_id(payment_id)
            if fact_hit is not None:
                hits.append(fact_hit)

            if approval_question and via_instruction:
                instruction_id = (fact_hit or {}).get("instruction_id")
                if instruction_id:
                    approve_hits = await self.multimodal.fetch_instruction_approve_events(
                        instruction_id
                    )
                    hits.extend(approve_hits)
            elif approval_question:
                approve_hits = await self.multimodal.fetch_payment_approve_events(payment_id)
                hits.extend(approve_hits)

        return hits

    @staticmethod
    def _merge_with_exact(
        exact_hits: list[dict[str, Any]],
        vector_hits: list[dict[str, Any]],
        bm25_hits: list[dict[str, Any]],
        graph_hits: list[dict[str, Any]],
    ) -> list[RankedHit]:
        merged = rrf_merge([vector_hits, bm25_hits, graph_hits])
        if not exact_hits:
            return merged[: settings.max_context_hits]

        exact_ranked = rrf_merge([exact_hits])
        pinned_keys = {hit.key for hit in exact_ranked}
        remainder = [hit for hit in merged if hit.key not in pinned_keys]
        return (exact_ranked + remainder)[: settings.max_context_hits]

    async def _search_graph(
        self, question: str, *, mode: SearchMode = "events"
    ) -> dict[str, Any]:
        planned = plan_graph_queries(question, mode=mode)
        cypher_provenance: str = "predefined_planned" if planned else "none"

        if planned is None:
            try:
                graph_plan = await self.ml_client.extract_graph_query_plan(
                    question, mode=mode
                )
                planned = plans_from_graph_query(
                    graph_plan, mode=mode, question=question
                )
                if planned:
                    cypher_provenance = "llm_graph_plan"
            except Exception as exc:
                logger.warning("graph plan extraction failed: %s", exc)
                return {
                    "cypher": None,
                    "rows": [],
                    "cypher_provenance": "none",
                    "graph_unavailable": True,
                }

        if planned is not None:
            try:
                result = await self._run_planned_graph_queries(planned)
                return {
                    **result,
                    "cypher_provenance": cypher_provenance,
                    "graph_unavailable": False,
                }
            except Exception as exc:
                logger.warning("planned graph query failed: %s", exc)
                return {
                    "cypher": None,
                    "rows": [],
                    "cypher_provenance": cypher_provenance,
                    "graph_unavailable": True,
                }

        # Graph was attempted but no executable plan was produced.
        return {
            "cypher": None,
            "rows": [],
            "cypher_provenance": "none",
            "graph_unavailable": True,
        }

    async def _run_planned_graph_queries(
        self, planned: list[tuple[str, str]]
    ) -> dict[str, Any]:
        cyphers: list[str] = []
        rows: list[dict[str, Any]] = []
        for _label, query in planned:
            normalized = normalize_read_only_cypher(query)
            validate_read_only_cypher(normalized)
            cyphers.append(normalized)
            rows.extend(await self.neo4j.run_cypher(normalized))
        return {"cypher": "\n\n".join(cyphers), "rows": rows}

    async def _answer_payment_eligible_approvers(
        self,
        message: str,
        *,
        bearer_token: str | None,
        session_id: str | None,
    ) -> str | None:
        if not bearer_token:
            return (
                "This question requires a live OPA policy check. "
                "Log in as a compliance analyst (comp-001 or comp-002) using the sign-in "
                "panel above, then ask again with a payment ID."
            )

        payment_ids = extract_entity_ids(message)
        if not payment_ids:
            return (
                "Please include the payment ID in your question, e.g. "
                "\"Who can approve payment <payment-id>?\""
            )

        try:
            data = await self._eligibility.eligible_approvers_for_payment(
                payment_ids[0],
                bearer_token=bearer_token,
                session_id=session_id,
            )
        except EligibilityClientError as exc:
            return str(exc)

        return format_eligible_approvers_answer(data)

    async def _answer_payment_approval_directory(
        self,
        message: str,
        *,
        bearer_token: str | None,
        session_id: str | None,
    ) -> str | None:
        from chat_application.authorization_client import (
            EligibilityClientError,
            format_group_members_answer,
        )
        from chat_application.policy_directory import (
            covering_lob_filter_from_question,
            directory_groups_for_question,
            is_payment_approval_directory_question,
            merge_group_member_rows,
        )

        if not is_payment_approval_directory_question(message):
            return None

        if not bearer_token:
            return (
                "This question requires policy directory access. "
                "Log in as a compliance analyst (comp-001 or comp-002) using the sign-in "
                "panel above, then ask again."
            )

        covering_lob = covering_lob_filter_from_question(message)
        clubs, amount, strict_threshold = directory_groups_for_question(message)
        if not clubs:
            return (
                "I could not determine which payment amount-limit club or desk LOB applies. "
                "Try including an amount (e.g. $25 billion), a club name such as "
                "UP_TO_100_BILLION_CLUB, or a covering LOB such as FICC."
            )

        merged_members: list[dict] = []
        try:
            for group in clubs:
                data = await self._eligibility.group_members(
                    group,
                    bearer_token=bearer_token,
                    role="FUNDING_APPROVER",
                    covering_lob=covering_lob,
                    session_id=session_id,
                )
                merged_members.extend(data.get("members") or [])
        except EligibilityClientError as exc:
            return str(exc)

        members = merge_group_member_rows(merged_members)
        return format_group_members_answer(
            {
                "groups": clubs,
                "members": members,
                "count": len(members),
            },
            amount=amount,
            covering_lob=covering_lob,
            strict_threshold=strict_threshold,
        )

    async def _answer_policy_summary(
        self,
        message: str,
        *,
        mode: SearchMode = "events",
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> str | None:
        from chat_application.authorization_client import (
            EligibilityClientError,
            format_policy_summary_answer,
        )
        from chat_application.policy_summary import detect_policy_summary_question

        detected = detect_policy_summary_question(message, mode=mode)
        if detected is None:
            return None

        domain, action = detected
        if not bearer_token:
            return (
                "This question requires live OPA policy access. "
                "Log in as a compliance analyst (comp-001 or comp-002) using the sign-in "
                "panel above, then ask again."
            )

        try:
            data = await self._eligibility.policy_summary(
                domain=domain,
                action=action,
                bearer_token=bearer_token,
                session_id=session_id,
            )
        except EligibilityClientError as exc:
            return str(exc)

        return format_policy_summary_answer(data)

    async def _answer_person_permission_summary(
        self,
        message: str,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> str | None:
        from chat_application.authorization_client import (
            EligibilityClientError,
            format_person_permission_summary_answer,
        )
        from chat_application.person_permissions import extract_person_permission_query

        query = extract_person_permission_query(message)
        if query is None:
            return None

        if not bearer_token:
            return (
                "This question requires policy directory access. "
                "Log in as a compliance analyst (comp-001 or comp-002) using the sign-in "
                "panel above, then ask again."
            )

        try:
            data = await self._eligibility.person_permission_summary(
                query=query,
                bearer_token=bearer_token,
                session_id=session_id,
            )
        except EligibilityClientError as exc:
            return str(exc)

        return format_person_permission_summary_answer(data)

    async def _answer_instruction_eligible_approvers(
        self,
        message: str,
        *,
        bearer_token: str | None,
        session_id: str | None,
    ) -> str | None:
        if not bearer_token:
            return (
                "This question requires a live OPA policy check. "
                "Log in as a compliance analyst (comp-001 or comp-002) using the sign-in "
                "panel above, then ask again with an instruction ID."
            )

        instruction_ids = extract_entity_ids(message)
        if not instruction_ids:
            return (
                "Please include the instruction ID in your question, e.g. "
                "\"Who can approve instruction <instruction-id>?\""
            )

        try:
            data = await self._eligibility.eligible_approvers_for_instruction(
                instruction_ids[0],
                bearer_token=bearer_token,
                session_id=session_id,
            )
        except EligibilityClientError as exc:
            return str(exc)

        return format_instruction_eligible_approvers_answer(data)

    async def _synthesize_instruction_approval_answer(
        self,
        message: str,
        instruction_ids: list[str],
        hits: list[RankedHit],
        graph_rows: list[dict[str, Any]],
    ) -> str | None:
        """Return Who/When/Why when OPA authorization is in context; LLM rewrites WHY for readability."""
        if "approv" not in message.lower():
            return None

        via_payment = is_instruction_approver_via_payment_question(message)
        payment_ids = extract_payment_ids(message)
        if via_payment:
            if not payment_ids:
                return None
            target_payment_id = payment_ids[0]
            target_instruction_id: str | None = None
        else:
            if not instruction_ids:
                return None
            target_payment_id = None
            target_instruction_id = instruction_ids[0]

        approver: str | None = None
        when: str | None = None
        summary: str | None = None
        basis: list[str] = []
        resolved_instruction_id: str | None = None

        for row in graph_rows:
            if via_payment:
                if str(row.get("payment_id")) != target_payment_id:
                    continue
                resolved_instruction_id = str(row.get("instruction_id") or "")
            else:
                row_id = row.get("v.instruction_id") or row.get("instruction_id")
                if str(row_id) != target_instruction_id:
                    continue
                resolved_instruction_id = str(row_id)
            summary = row.get("v.authorization_summary") or row.get("authorization_summary")
            approver = row.get("approver_display")
            when = row.get("v.approved_at") or row.get("approved_at")
            basis = parse_authorization_basis(
                row.get("v.authorization_basis") or row.get("authorization_basis")
            )
            break

        lookup_id = resolved_instruction_id or target_instruction_id
        for hit in hits:
            payload = hit.merged or {}
            payload_id = hit.instruction_id or payload.get("instruction_id")
            if lookup_id and str(payload_id) != lookup_id:
                continue
            if via_payment and lookup_id is None:
                continue
            summary = summary or payload.get("authorization_summary")
            approver = approver or payload.get("approver_display") or payload.get("actor_display")
            when = when or payload.get("approved_at") or payload.get("timestamp")
            if not basis:
                basis = parse_authorization_basis(payload.get("authorization_basis"))
            if summary:
                break

        if not approver or (not summary and not basis):
            return None

        readable_summary = humanize_authorization_text(summary) if summary else None
        if readable_summary:
            readable_summary = await self.ml_client.summarize_authorization_why(
                approver=approver,
                authorization_summary=readable_summary,
                authorization_basis=humanize_policy_basis(basis) if basis else None,
            )

        auth_lines = format_approval_auth_lines(summary=readable_summary, basis=basis)
        when_line = f"WHEN: {when}" if when else None
        header = (
            f"Instruction: {resolved_instruction_id} (via payment {target_payment_id})"
            if via_payment and resolved_instruction_id
            else None
        )
        return "\n".join(
            line
            for line in (
                header,
                f"WHO: {approver}",
                when_line,
                *auth_lines,
            )
            if line
        )

    async def _synthesize_payment_approval_answer(
        self,
        message: str,
        payment_ids: list[str],
        hits: list[RankedHit],
        graph_rows: list[dict[str, Any]],
    ) -> str | None:
        """Return Who/When/Why for payment approval using OPA authorization from indexed events."""
        if "approv" not in message.lower() or not payment_ids:
            return None

        target_id = payment_ids[0]
        approver: str | None = None
        when: str | None = None
        summary: str | None = None
        basis: list[str] = []

        for row in graph_rows:
            row_id = row.get("payment_id")
            if str(row_id) != target_id:
                continue
            summary = row.get("authorization_summary")
            approver = row.get("approver_display")
            when = row.get("approved_at")
            basis = parse_authorization_basis(row.get("authorization_basis"))
            break

        for hit in hits:
            payload = hit.merged or {}
            payload_id = payload.get("payment_id")
            if str(payload_id) != target_id:
                continue

            is_approve_event = payload.get("action") in ("APPROVE", "APPROVE_PAYMENT") or payload.get(
                "source"
            ) in {"exact_approve_payment_event", "payment_security_event"}

            if is_approve_event:
                summary = payload.get("authorization_summary") or summary
                approver = (
                    payload.get("actor_display")
                    or payload.get("approver_display")
                    or approver
                )
                when = payload.get("timestamp") or payload.get("approved_at") or when
                if not basis:
                    basis = parse_authorization_basis(payload.get("authorization_basis"))
            else:
                approver = approver or payload.get("approver_display")
                when = when or payload.get("approved_at")

            if summary and approver and basis:
                break

        if not approver:
            return None
        if not summary and not basis:
            return None

        summary = summary or f"{approver} was allowed to APPROVE"
        readable_summary = await self.ml_client.summarize_authorization_why(
            approver=approver,
            authorization_summary=humanize_authorization_text(summary),
            authorization_basis=humanize_policy_basis(basis) if basis else None,
        )

        auth_lines = format_approval_auth_lines(summary=readable_summary, basis=basis)
        when_line = f"WHEN: {when}" if when else None
        return "\n".join(
            line
            for line in (
                f"WHO: {approver}",
                when_line,
                *auth_lines,
            )
            if line
        )

    @staticmethod
    def _build_context(
        hits: list[RankedHit],
        graph_rows: list[dict[str, Any]],
        cypher: str | None,
        *,
        graph_unavailable: bool = False,
        mode: SearchMode = "events",
    ) -> str:
        sections: list[str] = []

        if mode == "instructions":
            sections.append("Search mode: INSTRUCTIONS (instruction master graph — independent of security events)")
        elif mode == "all":
            sections.append(
                "Search mode: ALL ENTITIES (instructions, payments, and all security events)"
            )
        elif mode == "payments":
            sections.append("Search mode: PAYMENTS (payment records only)")
        elif mode == "policies":
            sections.append(
                "Search mode: POLICIES (live OPA policy summary, directory, and eligibility tools)"
            )
        elif mode == "events":
            sections.append(
                "Search mode: SECURITY EVENTS (instruction + payment security event log)"
            )

        if graph_unavailable:
            if mode == "instructions":
                sections.append(
                    "Note: instruction graph search was unavailable. "
                    "Do not infer hierarchy or structural relationships from vector/BM25 hits."
                )
            else:
                sections.append(
                    "Note: graph search was unavailable for this question. "
                    "Answer using the retrieved vector and BM25 results below only."
                )

        if cypher:
            sections.append(f"Neo4j Cypher executed:\n{cypher}")

        if graph_rows:
            ranking_rows = [
                row
                for row in graph_rows
                if "alert_count" in row and "actor_display" in row
            ]
            if ranking_rows:
                sections.append(
                    "Neo4j user ranking by policy alerts (instruction + payment combined):\n"
                    + json.dumps(ranking_rows[:20], indent=2, default=str)
                )
            aggregate = next(
                (
                    row
                    for row in graph_rows
                    if any(key in row for key in ("total", "count"))
                    and "alert_count" not in row
                    and len(row) <= 3
                ),
                None,
            )
            if aggregate is not None:
                total = aggregate.get("total", aggregate.get("count"))
                if aggregate.get("alert_count") is not None:
                    sections.append(
                        "Neo4j security event count: "
                        f"total={total}, "
                        f"ALERT={aggregate.get('alert_count')}, "
                        f"INFO={aggregate.get('info_count')}"
                    )
                else:
                    sections.append(f"Neo4j aggregate count: {total}")
            detail_rows = [
                row for row in graph_rows if row not in ranking_rows and row is not aggregate
            ] if ranking_rows or aggregate else graph_rows
            if detail_rows:
                sections.append(
                    "Neo4j graph results:\n"
                    + json.dumps(detail_rows[:20], indent=2, default=str)
                )
        elif cypher and not graph_unavailable:
            sections.append(
                "Neo4j graph results: 0 rows — the graph query found no matching records. "
                "For structural questions (supervisor relationships, hierarchy violations, "
                "cross-approvals) this means no such case exists in the data. "
                "Do NOT use vector/BM25 hits to contradict this finding."
            )

        if hits:
            lines: list[str] = []
            for index, hit in enumerate(hits, start=1):
                payload = hit.merged or {}
                snap = payload.get("instruction_snapshot") or {}
                src = payload.get("source") or (sorted(hit.sources)[0] if hit.sources else "?")
                if src in {"vector", "bm25", "exact"} and payload.get("source"):
                    src = payload.get("source")

                if src == "instruction_state" or src == "exact_instruction":
                    party_lines = _instruction_lifecycle_party_lines(payload, snap)
                    lines.append(
                        f"[{index}] INSTRUCTION instruction_id={hit.instruction_id} "
                        f"score={hit.score:.4f}\n"
                        f"  status={snap.get('status')} type={snap.get('instruction_type')} "
                        f"lob={snap.get('owning_lob')} currency={snap.get('currency')} "
                        f"scope={snap.get('wire_scope')}\n"
                        f"  creditor={snap.get('creditor_name')} "
                        f"creditor_acct={snap.get('creditor_account_id')}\n"
                        f"  creator={payload.get('creator_display')}\n"
                        f"  {party_lines}\n"
                        f"  why={payload.get('authorization_summary') or ''}\n"
                        f"  basis={_format_basis_join(payload.get('authorization_basis'))}\n"
                        f"  effective={snap.get('effective_date')} end={snap.get('end_date')} "
                        f"expired={snap.get('is_expired', False)}"
                    )
                elif src == "payment_fact":
                    psnap = payload.get("payment_snapshot") or {}
                    lines.append(
                        f"[{index}] PAYMENT payment_id={payload.get('payment_id')} "
                        f"instruction_id={payload.get('instruction_id')} score={hit.score:.4f}\n"
                        f"  status={payload.get('status', psnap.get('status'))} "
                        f"amount={payload.get('amount', psnap.get('amount'))} "
                        f"currency={payload.get('currency', psnap.get('currency'))} "
                        f"lob={payload.get('owning_lob', psnap.get('owning_lob'))}\n"
                        f"  value_date={payload.get('value_date', psnap.get('value_date'))}\n"
                        f"  creator={payload.get('creator_display')} "
                        f"approver={payload.get('approver_display')}"
                    )
                elif src == "payment_security_event":
                    psnap = payload.get("payment_snapshot") or {}
                    lines.append(
                        f"[{index}] PAYMENT SECURITY EVENT event_id={hit.event_id} "
                        f"payment_id={payload.get('payment_id')} "
                        f"instruction_id={payload.get('instruction_id')} score={hit.score:.4f}\n"
                        f"  time={payload.get('timestamp')} action={payload.get('action')} "
                        f"severity={payload.get('severity')} outcome={payload.get('outcome')} "
                        f"actor={payload.get('actor_display')}\n"
                        f"  amount={payload.get('amount', psnap.get('amount'))} "
                        f"currency={payload.get('currency', psnap.get('currency'))} "
                        f"lob={payload.get('owning_lob', psnap.get('owning_lob'))}\n"
                        f"  why={payload.get('authorization_summary') or payload.get('reason') or payload.get('message', hit.summary)}\n"
                        f"  basis={_format_basis_join(payload.get('authorization_basis'))}"
                    )
                elif src in ("instruction_security_event", "security_event", "exact_approve_event"):
                    merged = hit.merged or {}
                    event_snap = merged.get("instruction_snapshot") or {}
                    status = (merged.get("status") or event_snap.get("status") or "").upper()
                    action = (merged.get("action") or "").upper()
                    if status == "REJECTED" or action == "REJECT":
                        party_lines = (
                            f"rejected_by={merged.get('rejector_display') or merged.get('actor_display', merged.get('actor_user_id'))}\n"
                            f"  rejected_at={merged.get('rejected_at') or event_snap.get('rejected_at') or merged.get('timestamp')}\n"
                            f"  rejection_reason={merged.get('rejection_reason') or event_snap.get('rejection_reason') or ''}"
                        )
                    else:
                        party_lines = (
                            f"approver={merged.get('approver_display', merged.get('approver_user_id'))}\n"
                            f"  approved_at={merged.get('approved_at') or event_snap.get('approved_at') or ''}"
                        )
                    lines.append(
                        f"[{index}] INSTRUCTION SECURITY EVENT event_id={hit.event_id} "
                        f"instruction_id={hit.instruction_id} "
                        f"sources={sorted(hit.sources)} score={hit.score:.4f}\n"
                        f"  time={merged.get('timestamp')} action={merged.get('action')} "
                        f"severity={merged.get('severity')} outcome={merged.get('outcome')} "
                        f"actor={merged.get('actor_display', merged.get('actor_user_id'))} "
                        f"lob={merged.get('owning_lob')}\n"
                        f"  creator={merged.get('creator_display', merged.get('creator_user_id'))}\n"
                        f"  {party_lines}\n"
                        f"  why={merged.get('authorization_summary') or merged.get('event_reason') or merged.get('reason') or hit.summary}\n"
                        f"  basis={_format_basis_join(merged.get('authorization_basis'))}"
                    )
                else:
                    merged = hit.merged or {}
                    lines.append(
                        f"[{index}] UNKNOWN source={src} event_id={hit.event_id} "
                        f"instruction_id={hit.instruction_id} score={hit.score:.4f}\n"
                        f"  summary: {hit.summary or merged.get('message', '')}"
                    )
            label = {
                "events": "Retrieved security events (instruction + payment)",
                "instructions": "Retrieved instruction states",
                "payments": "Retrieved payment records",
                "all": "Retrieved results across all entity types",
            }.get(mode, "Retrieved results")
            sections.append(f"{label} (vector + BM25 + graph):\n" + "\n".join(lines))

        if not sections:
            return "No indexed data was found."
        return "\n\n".join(sections)

    @staticmethod
    def _to_source(hit: RankedHit) -> SourceHit:
        return SourceHit(
            event_id=hit.event_id,
            instruction_id=hit.instruction_id,
            score=round(hit.score, 4),
            sources=sorted(hit.sources),
            summary=hit.summary,
            merged=hit.merged,
            security_event=hit.security_event,
        )
