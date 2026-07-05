"""Generic facet (GROUP BY) aggregation for instructions and payments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

FacetEntityName = Literal["instruction", "payment"]
AnalyticsMetric = Literal["count", "sum_amount", "avg_approval_time"]
ReturnMode = Literal["table", "single_winner"]

_ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_FROM_TO = re.compile(
    r"\bfrom\s+(\d{4}-\d{2}-\d{2})\s+(?:to|through|until)\s+(\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
_BETWEEN_DATES = re.compile(
    r"\bbetween\s+(\d{4}-\d{2}-\d{2})\s+and\s+(\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
_SINCE_DATE = re.compile(r"\bsince\s+(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)
_LAST_N_DAYS = re.compile(r"\blast\s+(\d{1,4})\s+days?\b", re.IGNORECASE)
_WEEK_QUESTION = re.compile(
    r"\b(this week|past week|last week|last 7 days|past 7 days)\b",
    re.IGNORECASE,
)
_MONTH_QUESTION = re.compile(
    r"\b(this month|past month|last month|last 30 days|past 30 days)\b",
    re.IGNORECASE,
)
_YEAR_QUESTION = re.compile(
    r"\b(this year|past year|last year|last 365 days)\b",
    re.IGNORECASE,
)

_FACET_AGGREGATE = re.compile(
    r"\b("
    r"group(?:ed)?|break\s*down|split|bucket|distribut(?:e|ion)|"
    r"count\s+per|number\s+of\s+\w+\s+per|how\s+many\s+\w+\s+per"
    r")\b",
    re.IGNORECASE,
)
_PER_LOB = re.compile(r"\b(?:per|by|each)\s+lob\b", re.IGNORECASE)
_GROUP_BY = re.compile(
    r"\b(?:group(?:ed)?|break\s*down|split|bucket(?:ed)?|distribut(?:e|ion)?)"
    r"(?:\s+\w+){0,6}\s+by\s+(.+)$",
    re.IGNORECASE,
)
_COUNT_PER = re.compile(
    r"\b(?:count|number)\s+per\s+(.+?)(?:[?.!]|$|\s+for\s|\s+in\s|\s+this\s|\s+last\s|\s+from\s)",
    re.IGNORECASE,
)
_PER_DIMENSION = re.compile(
    r"\bper\s+(.+?)(?:[?.!]|$|\s+for\s|\s+in\s|\s+this\s|\s+last\s|\s+from\s)",
    re.IGNORECASE,
)

_TRAILING_FILTER = re.compile(
    r"\s+(?:for|in|during|within)\s+(?:this|last|past)\s+(?:week|month|year|day|\d+\s+days?).*$",
    re.IGNORECASE,
)
_AND_INCLUDE = re.compile(r"\s+and\s+include\s+.+$", re.IGNORECASE)
_TOP_N = re.compile(r"\btop\s+(\d+)\b", re.IGNORECASE)
_SUPERLATIVE_CUE = re.compile(
    r"\b(who|which)\b.{0,120}\b(most|top|highest|greatest|leading)\b|"
    r"\b(most|top|highest|greatest|leading)\b.{0,40}\b(payments?|instructions?)\b",
    re.IGNORECASE,
)
_AVG_APPROVAL_TIME = re.compile(
    r"\baverage\s+approval\s+time\b|"
    r"\bavg\s+approval\b|"
    r"\b(?:average|avg|mean)\b.{0,60}\b(?:time|duration|hours|days|latency)\b.{0,40}"
    r"\b(?:approve|approval|approving)\b|"
    r"\b(?:time|duration)\b.{0,40}\b(?:approve|approval)\b|"
    r"\baverage\s+time\s+they\s+have\s+taken\s+to\s+approve\b",
    re.IGNORECASE,
)
_MEDIAN_CUE = re.compile(r"\bmedian\b", re.IGNORECASE)


class FacetEntity(StrEnum):
    INSTRUCTION = "instruction"
    PAYMENT = "payment"


@dataclass(frozen=True)
class FacetDimension:
    key: str
    label: str
    bucket_expr: str
    aliases: tuple[str, ...]
    optional_match: str = ""


@dataclass(frozen=True)
class DateRangeSpec:
    """Resolved date filter rendered as a Cypher AND clause."""

    field_label: str
    cypher_clause: str


@dataclass(frozen=True)
class FacetAggregateSpec:
    entity: FacetEntity
    dimension: FacetDimension
    metrics: tuple[str, ...] = ("count",)
    status_filter: str | None = None
    lob_filter: str | None = None
    instruction_type_filter: str | None = None
    date_range: DateRangeSpec | None = None
    limit: int = 50
    return_mode: ReturnMode = "table"
    unsupported_requests: tuple[str, ...] = ()

    @property
    def sum_amount(self) -> bool:
        return "sum_amount" in self.metrics


def _normalize_phrase(value: str) -> str:
    cleaned = value.lower().strip().rstrip("?.!")
    cleaned = _TRAILING_FILTER.sub("", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _instruction_dimensions() -> dict[str, FacetDimension]:
    return {
        "status": FacetDimension(
            key="status",
            label="Status",
            bucket_expr="coalesce(v.status, 'unknown')",
            aliases=("status", "lifecycle", "state", "lifecycle status"),
        ),
        "owning_lob": FacetDimension(
            key="owning_lob",
            label="LOB",
            bucket_expr="coalesce(v.owning_lob, 'unknown')",
            aliases=("lob", "owning lob", "line of business", "profit center", "desk"),
        ),
        "instruction_type": FacetDimension(
            key="instruction_type",
            label="Instruction type",
            bucket_expr="coalesce(v.instruction_type, 'unknown')",
            aliases=("instruction type", "type", "single use", "standing"),
        ),
        "currency": FacetDimension(
            key="currency",
            label="Currency",
            bucket_expr="coalesce(v.currency, 'unknown')",
            aliases=("currency",),
        ),
        "wire_scope": FacetDimension(
            key="wire_scope",
            label="Wire scope",
            bucket_expr="coalesce(v.wire_scope, 'unknown')",
            aliases=("wire scope", "scope", "domestic", "international"),
        ),
        "creator": FacetDimension(
            key="creator",
            label="Creator",
            bucket_expr="coalesce(creator.display_name, v.creator_user_id, 'unknown')",
            aliases=("creator", "created by", "instruction creator", "submitter"),
            optional_match="OPTIONAL MATCH (creator:User {user_id: v.creator_user_id})",
        ),
        "approver": FacetDimension(
            key="approver",
            label="Approver",
            bucket_expr="coalesce(approver.display_name, v.approver_user_id, 'unknown')",
            aliases=("approver", "approved by", "instruction approver", "approvers"),
            optional_match="OPTIONAL MATCH (approver:User {user_id: v.approver_user_id})",
        ),
        "rejector": FacetDimension(
            key="rejector",
            label="Rejector",
            bucket_expr="coalesce(rejector.display_name, v.rejector_user_id, 'unknown')",
            aliases=("rejector", "rejected by"),
            optional_match="OPTIONAL MATCH (rejector:User {user_id: v.rejector_user_id})",
        ),
        "created_day": FacetDimension(
            key="created_day",
            label="Created date",
            bucket_expr=(
                "CASE WHEN v.timestamp IS NULL THEN 'unknown' "
                "ELSE toString(date(datetime(v.timestamp))) END"
            ),
            aliases=("created date", "creation date", "created day", "created at"),
        ),
    }


def _payment_dimensions() -> dict[str, FacetDimension]:
    return {
        "status": FacetDimension(
            key="status",
            label="Status",
            bucket_expr="coalesce(p.status, 'unknown')",
            aliases=("status", "lifecycle", "state", "payment status"),
        ),
        "owning_lob": FacetDimension(
            key="owning_lob",
            label="LOB",
            bucket_expr="coalesce(p.owning_lob, 'unknown')",
            aliases=("lob", "owning lob", "line of business", "profit center", "desk"),
        ),
        "instruction_type": FacetDimension(
            key="instruction_type",
            label="Instruction type",
            bucket_expr="coalesce(p.instruction_type, 'unknown')",
            aliases=("instruction type", "type", "single use", "standing"),
        ),
        "currency": FacetDimension(
            key="currency",
            label="Currency",
            bucket_expr="coalesce(p.currency, 'unknown')",
            aliases=("currency",),
        ),
        "creator": FacetDimension(
            key="creator",
            label="Creator",
            bucket_expr="coalesce(creator.display_name, p.creator_user_id, 'unknown')",
            aliases=("creator", "created by", "payment creator"),
            optional_match="OPTIONAL MATCH (creator:User {user_id: p.creator_user_id})",
        ),
        "submitter": FacetDimension(
            key="submitter",
            label="Submitter",
            bucket_expr="coalesce(submitter.display_name, p.submitter_user_id, 'unknown')",
            aliases=("submitter", "submitted by"),
            optional_match="OPTIONAL MATCH (submitter:User {user_id: p.submitter_user_id})",
        ),
        "approver": FacetDimension(
            key="approver",
            label="Approver",
            bucket_expr="coalesce(approver.display_name, p.approver_user_id, 'unknown')",
            aliases=("approver", "approved by", "payment approver", "approvers"),
            optional_match="OPTIONAL MATCH (approver:User {user_id: p.approver_user_id})",
        ),
        "rejector": FacetDimension(
            key="rejector",
            label="Rejector",
            bucket_expr="coalesce(rejector.display_name, p.rejector_user_id, 'unknown')",
            aliases=("rejector", "rejected by"),
            optional_match="OPTIONAL MATCH (rejector:User {user_id: p.rejector_user_id})",
        ),
        "value_date": FacetDimension(
            key="value_date",
            label="Value date",
            bucket_expr=(
                "CASE WHEN p.value_date IS NULL OR p.value_date = '' THEN 'unknown' "
                "ELSE substring(p.value_date, 0, 10) END"
            ),
            aliases=("value date", "value dates", "settlement date", "val date"),
        ),
        "value_date_week": FacetDimension(
            key="value_date_week",
            label="Value date (week)",
            bucket_expr=(
                "CASE WHEN p.value_date IS NULL OR p.value_date = '' THEN 'unknown' "
                "ELSE toString(date(truncate('week', date(substring(p.value_date, 0, 10))))) END"
            ),
            aliases=("value date week", "week of value date", "value date by week"),
        ),
        "value_date_month": FacetDimension(
            key="value_date_month",
            label="Value date (month)",
            bucket_expr=(
                "CASE WHEN p.value_date IS NULL OR p.value_date = '' THEN 'unknown' "
                "ELSE toString(date(truncate('month', date(substring(p.value_date, 0, 10))))) END"
            ),
            aliases=("value date month", "month of value date", "value date by month"),
        ),
        "created_day": FacetDimension(
            key="created_day",
            label="Created date",
            bucket_expr=(
                "CASE WHEN p.created_at IS NULL THEN 'unknown' "
                "ELSE toString(date(datetime(p.created_at))) END"
            ),
            aliases=("created date", "creation date", "created day", "created at"),
        ),
        "updated_day": FacetDimension(
            key="updated_day",
            label="Updated date",
            bucket_expr=(
                "CASE WHEN p.updated_at IS NULL THEN 'unknown' "
                "ELSE toString(date(datetime(p.updated_at))) END"
            ),
            aliases=("updated date", "updated day", "updated at", "modified date"),
        ),
    }


def facet_dimensions(entity: FacetEntity) -> dict[str, FacetDimension]:
    if entity == FacetEntity.INSTRUCTION:
        return _instruction_dimensions()
    return _payment_dimensions()


def resolve_facet_dimension(phrase: str, entity: FacetEntity) -> FacetDimension | None:
    normalized = _normalize_phrase(phrase)
    if not normalized:
        return None
    catalog = facet_dimensions(entity)
    if normalized in catalog:
        return catalog[normalized]
    best: FacetDimension | None = None
    best_len = -1
    for dimension in catalog.values():
        for alias in dimension.aliases:
            if normalized == alias or normalized.endswith(f" {alias}") or alias in normalized:
                if len(alias) > best_len:
                    best = dimension
                    best_len = len(alias)
    return best


def resolve_facet_entity(question: str, *, mode: str) -> FacetEntity | None:
    q = question.lower()
    if mode == "payments":
        return FacetEntity.PAYMENT
    if mode == "instructions":
        return FacetEntity.INSTRUCTION
    if "payment" in q and "instruction" not in q:
        return FacetEntity.PAYMENT
    if "instruction" in q and "payment" not in q:
        return FacetEntity.INSTRUCTION
    return None


def _extract_group_by_phrase(question: str) -> str | None:
    if _PER_LOB.search(question):
        return "lob"
    match = _GROUP_BY.search(question.strip())
    if match:
        phrase = _AND_INCLUDE.sub("", match.group(1).strip()).strip()
        return phrase.rstrip("?.!")
    match = _COUNT_PER.search(question)
    if match:
        phrase = _AND_INCLUDE.sub("", match.group(1).strip()).strip()
        return phrase.rstrip("?.!")
    match = _PER_DIMENSION.search(question)
    if match and _FACET_AGGREGATE.search(question):
        phrase = _AND_INCLUDE.sub("", match.group(1).strip()).strip()
        return phrase.rstrip("?.!")
    return None


def _looks_superlative(question: str) -> bool:
    if _is_payment_extreme_amount_question(question):
        return False
    return bool(_SUPERLATIVE_CUE.search(question))


def _is_payment_extreme_amount_question(question: str) -> bool:
    q = question.lower()
    if "payment" not in q:
        return False
    return bool(
        re.search(
            r"\b(maximum|largest|highest|greatest|biggest|most expensive)\b",
            q,
        )
        and re.search(r"\b(amount|dollar|\$|value)\b", q)
    )


def _superlative_limit(question: str) -> int:
    match = _TOP_N.search(question)
    if match:
        return max(1, min(int(match.group(1)), 50))
    if re.search(r"\b(who|which)\b", question, re.IGNORECASE):
        return 1
    return 50


def _extract_superlative_dimension(
    question: str, entity: FacetEntity
) -> FacetDimension | None:
    if not _looks_superlative(question):
        return None
    q = question.lower()
    catalog = facet_dimensions(entity)
    verb_to_key = (
        (r"\b(?:creat(?:ed|es|or)|creation)\b", "creator"),
        (r"\b(?:approv(?:ed|es|er|al))\b", "approver"),
        (r"\b(?:submit(?:ted|s|ter))\b", "submitter"),
        (r"\b(?:reject(?:ed|s|or))\b", "rejector"),
    )
    for pattern, key in verb_to_key:
        if re.search(pattern, q) and key in catalog:
            return catalog[key]
    for dimension in catalog.values():
        for alias in dimension.aliases:
            if alias in q:
                return dimension
    return None


def _is_group_by_facet_question(question: str, *, mode: str) -> bool:
    if mode not in ("instructions", "payments", "all"):
        return False
    if resolve_facet_entity(question, mode=mode) is None:
        return False
    if _FACET_AGGREGATE.search(question):
        return True
    if mode == "instructions" and _PER_LOB.search(question):
        return True
    if _GROUP_BY.search(question.strip()):
        return True
    return False


def is_analytics_question(question: str, *, mode: str) -> bool:
    entity = resolve_facet_entity(question, mode=mode)
    if entity is None or mode not in ("instructions", "payments", "all"):
        return False
    if _extract_superlative_dimension(question, entity) is not None:
        return True
    return _is_group_by_facet_question(question, mode=mode)


def is_facet_aggregate_question(question: str, *, mode: str) -> bool:
    return is_analytics_question(question, mode=mode)


def _parse_requested_metrics(
    question: str, *, entity: FacetEntity
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    metrics: list[str] = ["count"]
    unsupported: list[str] = []
    q = question.lower()

    if entity == FacetEntity.PAYMENT and (
        "total amount" in q
        or re.search(r"\bsum\b", q)
        or (
            "amount" in q
            and "count" not in q
            and "average" not in q
            and "avg" not in q
            and "mean" not in q
        )
    ):
        if "sum_amount" not in metrics:
            metrics.append("sum_amount")

    if entity == FacetEntity.PAYMENT and _AVG_APPROVAL_TIME.search(question):
        metrics.append("avg_approval_time")

    if _MEDIAN_CUE.search(question):
        unsupported.append("median")

    deduped: list[str] = []
    for metric in metrics:
        if metric not in deduped:
            deduped.append(metric)
    return tuple(deduped), tuple(unsupported)


def _payment_date_field_key(question: str, dimension: FacetDimension) -> str:
    if dimension.key.startswith("value_date"):
        return "value_date"
    q = question.lower()
    from cypher_builder.query_engine import is_payment_value_date_question

    if is_payment_value_date_question(question) or "value date" in q:
        return "value_date"
    if "created" in q:
        return "created_at"
    return "updated_at"


def _instruction_date_field_key(question: str) -> str:
    q = question.lower()
    if "created" in q:
        return "timestamp"
    return "timestamp"


def _date_range_clause(
    question: str,
    *,
    entity: FacetEntity,
    dimension: FacetDimension,
) -> DateRangeSpec | None:
    q = question.lower()
    between = _BETWEEN_DATES.search(question) or _FROM_TO.search(question)
    since = _SINCE_DATE.search(question)
    last_days = _LAST_N_DAYS.search(question)
    explicit_dates = _ISO_DATE.findall(question)

    if entity == FacetEntity.PAYMENT:
        field_key = _payment_date_field_key(question, dimension)
        if field_key == "value_date":
            if between:
                start, end = between.group(1), between.group(2)
                return DateRangeSpec(
                    field_label="value date",
                    cypher_clause=(
                        f"AND p.value_date >= '{start}' AND p.value_date <= '{end}'"
                    ),
                )
            if since:
                start = since.group(1)
                return DateRangeSpec(
                    field_label="value date",
                    cypher_clause=f"AND p.value_date >= '{start}'",
                )
            if "today" in q:
                return DateRangeSpec(
                    field_label="value date",
                    cypher_clause="AND p.value_date STARTS WITH toString(date())",
                )
            if _WEEK_QUESTION.search(question):
                return DateRangeSpec(
                    field_label="value date",
                    cypher_clause="AND p.value_date >= toString(date() - duration('P7D'))",
                )
            if _MONTH_QUESTION.search(question):
                return DateRangeSpec(
                    field_label="value date",
                    cypher_clause="AND p.value_date >= toString(date() - duration('P1M'))",
                )
            if _YEAR_QUESTION.search(question):
                return DateRangeSpec(
                    field_label="value date",
                    cypher_clause="AND p.value_date >= toString(date() - duration('P1Y'))",
                )
            if last_days:
                days = int(last_days.group(1))
                return DateRangeSpec(
                    field_label="value date",
                    cypher_clause=(
                        f"AND p.value_date >= toString(date() - duration('P{days}D'))"
                    ),
                )
            if len(explicit_dates) >= 2:
                start, end = sorted(explicit_dates)[:2]
                return DateRangeSpec(
                    field_label="value date",
                    cypher_clause=(
                        f"AND p.value_date >= '{start}' AND p.value_date <= '{end}'"
                    ),
                )
            if len(explicit_dates) == 1:
                only = explicit_dates[0]
                return DateRangeSpec(
                    field_label="value date",
                    cypher_clause=f"AND p.value_date STARTS WITH '{only}'",
                )
            return None

        datetime_field = "p.created_at" if field_key == "created_at" else "p.updated_at"
        label = "created date" if field_key == "created_at" else "updated date"
        if between:
            start, end = between.group(1), between.group(2)
            return DateRangeSpec(
                field_label=label,
                cypher_clause=(
                    f"AND {datetime_field} IS NOT NULL "
                    f"AND date(datetime({datetime_field})) >= date('{start}') "
                    f"AND date(datetime({datetime_field})) <= date('{end}')"
                ),
            )
        if since:
            start = since.group(1)
            return DateRangeSpec(
                field_label=label,
                cypher_clause=(
                    f"AND {datetime_field} IS NOT NULL "
                    f"AND date(datetime({datetime_field})) >= date('{start}')"
                ),
            )
        if "today" in q:
            return DateRangeSpec(
                field_label=label,
                cypher_clause=(
                    f"AND {datetime_field} IS NOT NULL "
                    f"AND date(datetime({datetime_field})) = date()"
                ),
            )
        if _WEEK_QUESTION.search(question):
            return DateRangeSpec(
                field_label=label,
                cypher_clause=(
                    f"AND {datetime_field} IS NOT NULL "
                    f"AND date(datetime({datetime_field})) >= date() - duration('P7D')"
                ),
            )
        if _MONTH_QUESTION.search(question):
            return DateRangeSpec(
                field_label=label,
                cypher_clause=(
                    f"AND {datetime_field} IS NOT NULL "
                    f"AND date(datetime({datetime_field})) >= date() - duration('P1M')"
                ),
            )
        if _YEAR_QUESTION.search(question):
            return DateRangeSpec(
                field_label=label,
                cypher_clause=(
                    f"AND {datetime_field} IS NOT NULL "
                    f"AND date(datetime({datetime_field})) >= date() - duration('P1Y')"
                ),
            )
        if last_days:
            days = int(last_days.group(1))
            return DateRangeSpec(
                field_label=label,
                cypher_clause=(
                    f"AND {datetime_field} IS NOT NULL "
                    f"AND date(datetime({datetime_field})) >= date() - duration('P{days}D')"
                ),
            )
        return None

    field_key = _instruction_date_field_key(question)
    if between:
        start, end = between.group(1), between.group(2)
        return DateRangeSpec(
            field_label="timestamp",
            cypher_clause=(
                "AND v.timestamp IS NOT NULL "
                f"AND date(datetime(v.timestamp)) >= date('{start}') "
                f"AND date(datetime(v.timestamp)) <= date('{end}')"
            ),
        )
    if since:
        start = since.group(1)
        return DateRangeSpec(
            field_label="timestamp",
            cypher_clause=(
                "AND v.timestamp IS NOT NULL "
                f"AND date(datetime(v.timestamp)) >= date('{start}')"
            ),
        )
    if "today" in q:
        return DateRangeSpec(
            field_label="timestamp",
            cypher_clause=(
                "AND v.timestamp IS NOT NULL AND date(datetime(v.timestamp)) = date()"
            ),
        )
    if _WEEK_QUESTION.search(question):
        return DateRangeSpec(
            field_label="timestamp",
            cypher_clause=(
                "AND v.timestamp IS NOT NULL "
                "AND date(datetime(v.timestamp)) >= date() - duration('P7D')"
            ),
        )
    if _MONTH_QUESTION.search(question):
        return DateRangeSpec(
            field_label="timestamp",
            cypher_clause=(
                "AND v.timestamp IS NOT NULL "
                "AND date(datetime(v.timestamp)) >= date() - duration('P1M')"
            ),
        )
    if _YEAR_QUESTION.search(question):
        return DateRangeSpec(
            field_label="timestamp",
            cypher_clause=(
                "AND v.timestamp IS NOT NULL "
                "AND date(datetime(v.timestamp)) >= date() - duration('P1Y')"
            ),
        )
    if last_days:
        days = int(last_days.group(1))
        return DateRangeSpec(
            field_label="timestamp",
            cypher_clause=(
                "AND v.timestamp IS NOT NULL "
                f"AND date(datetime(v.timestamp)) >= date() - duration('P{days}D')"
            ),
        )
    if len(explicit_dates) >= 2:
        start, end = sorted(explicit_dates)[:2]
        return DateRangeSpec(
            field_label=field_key,
            cypher_clause=(
                "AND v.timestamp IS NOT NULL "
                f"AND date(datetime(v.timestamp)) >= date('{start}') "
                f"AND date(datetime(v.timestamp)) <= date('{end}')"
            ),
        )
    return None


def parse_facet_aggregate(question: str, *, mode: str) -> FacetAggregateSpec | None:
    from cypher_builder.query_engine import (
        instruction_status_filter_from_question,
        instruction_type_filter_from_question,
        lob_filter_from_question,
        payment_status_filter_from_question,
    )

    entity = resolve_facet_entity(question, mode=mode)
    if entity is None:
        return None

    metrics, unsupported = _parse_requested_metrics(question, entity=entity)

    superlative_dim = _extract_superlative_dimension(question, entity)
    if superlative_dim is not None:
        limit = _superlative_limit(question)
        return_mode: ReturnMode = "single_winner" if limit == 1 else "table"
        dimension = superlative_dim
    else:
        if not _is_group_by_facet_question(question, mode=mode):
            return None
        phrase = _extract_group_by_phrase(question)
        if not phrase:
            return None
        dimension = resolve_facet_dimension(phrase, entity)
        if dimension is None:
            return None
        limit = 50
        return_mode = "table"

    status_filter = None
    instruction_type_filter = None
    if entity == FacetEntity.INSTRUCTION:
        status_filter = instruction_status_filter_from_question(question)
        instruction_type_filter = instruction_type_filter_from_question(question)
    else:
        status_filter = payment_status_filter_from_question(question)

    lob_filter = lob_filter_from_question(question)
    date_range = _date_range_clause(question, entity=entity, dimension=dimension)

    return FacetAggregateSpec(
        entity=entity,
        dimension=dimension,
        metrics=metrics,
        status_filter=status_filter,
        lob_filter=lob_filter,
        instruction_type_filter=instruction_type_filter,
        date_range=date_range,
        limit=limit,
        return_mode=return_mode,
        unsupported_requests=unsupported,
    )


def _aggregate_with_clauses(spec: FacetAggregateSpec) -> tuple[str, list[str]]:
    """Build WITH aggregations and RETURN column names."""
    agg_parts: list[str] = [f"{spec.dimension.bucket_expr} AS bucket"]
    return_cols = ["bucket"]

    if "count" in spec.metrics:
        if spec.entity == FacetEntity.INSTRUCTION:
            agg_parts.append("count(DISTINCT i.instruction_id) AS total")
        else:
            agg_parts.append("count(DISTINCT pay.payment_id) AS total")
        return_cols.append("total")

    if "sum_amount" in spec.metrics and spec.entity == FacetEntity.PAYMENT:
        agg_parts.append("sum(p.amount) AS total_amount")
        return_cols.append("total_amount")

    if "avg_approval_time" in spec.metrics and spec.entity == FacetEntity.PAYMENT:
        agg_parts.append(
            "avg("
            "CASE WHEN p.approved_at IS NOT NULL AND p.created_at IS NOT NULL "
            "THEN duration.inSeconds(datetime(p.created_at), datetime(p.approved_at)) / 3600.0 "
            "ELSE NULL END"
            ") AS avg_approval_hours"
        )
        return_cols.append("avg_approval_hours")

    return ", ".join(agg_parts), return_cols


def build_facet_aggregate_cypher(spec: FacetAggregateSpec) -> str:
    filters: list[str] = ["AND true"]
    if spec.status_filter:
        field = "v.status" if spec.entity == FacetEntity.INSTRUCTION else "p.status"
        filters.append(f"AND {field} = '{spec.status_filter}'")
    if spec.lob_filter:
        field = "v.owning_lob" if spec.entity == FacetEntity.INSTRUCTION else "p.owning_lob"
        filters.append(f"AND {field} = '{spec.lob_filter}'")
    if spec.instruction_type_filter and spec.entity == FacetEntity.INSTRUCTION:
        filters.append(f"AND v.instruction_type = '{spec.instruction_type_filter}'")
    if spec.date_range is not None:
        filters.append(spec.date_range.cypher_clause)
    filter_clause = "\n".join(filters)

    optional_match = spec.dimension.optional_match
    optional_line = f"{optional_match}\n" if optional_match else ""
    with_aggs, return_cols = _aggregate_with_clauses(spec)
    order_field = "total" if "total" in return_cols else return_cols[-1]
    return_clause = ", ".join(return_cols)
    limit = max(1, min(spec.limit, 50))

    if spec.entity == FacetEntity.INSTRUCTION:
        prefix = """
MATCH (i:Instruction)-[:HAS_VERSION]->(iv:InstructionVersion)
WHERE iv.status IS NOT NULL AND iv.status <> ''
WITH i, max(iv.version_number) AS max_ver
MATCH (i)-[:HAS_VERSION]->(v:InstructionVersion)
WHERE v.version_number = max_ver AND v.status IS NOT NULL AND v.status <> ''
"""
        return (
            f"{prefix}"
            f"{filter_clause}\n"
            f"{optional_line}"
            f"WITH {with_aggs}\n"
            f"RETURN {return_clause}\n"
            f"ORDER BY {order_field} DESC, bucket ASC\n"
            f"LIMIT {limit}"
        )

    prefix = """
MATCH (pay:Payment)-[:HAS_VERSION]->(pv:PaymentVersion)
WHERE pv.status IS NOT NULL
WITH pay, max(pv.version_number) AS max_ver
MATCH (pay)-[:HAS_VERSION]->(p:PaymentVersion)
WHERE p.version_number = max_ver AND p.status IS NOT NULL
"""
    return (
        f"{prefix}"
        f"{filter_clause}\n"
        f"{optional_line}"
        f"WITH {with_aggs}\n"
        f"RETURN {return_clause}\n"
        f"ORDER BY {order_field} DESC, bucket ASC\n"
        f"LIMIT {limit}"
    )


def facet_aggregate_queries(question: str, *, mode: str) -> list[tuple[str, str]] | None:
    spec = parse_facet_aggregate(question, mode=mode)
    if spec is None:
        return None
    return [("facet_aggregate", build_facet_aggregate_cypher(spec))]


def _markdown_table(headers: list[str], rows: list[tuple[str | int | float, ...]]) -> str:
    if not rows:
        return "_No rows._"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def _facet_qualifier_suffix(spec: FacetAggregateSpec) -> str:
    qualifiers: list[str] = []
    if spec.status_filter:
        qualifiers.append(f"status {spec.status_filter}")
    if spec.instruction_type_filter:
        qualifiers.append(f"type {spec.instruction_type_filter}")
    if spec.lob_filter:
        qualifiers.append(f"LOB {spec.lob_filter}")
    if spec.date_range is not None:
        qualifiers.append(spec.date_range.field_label)
    if not qualifiers:
        return ""
    return f" ({', '.join(qualifiers)})"


def _dimension_action_verb(dimension_key: str) -> str:
    return {
        "creator": "created",
        "approver": "approved",
        "submitter": "submitted",
        "rejector": "rejected",
    }.get(dimension_key, "has")


def _format_hours(value: object) -> str:
    if value is None:
        return "—"
    hours = float(value)
    if hours < 1:
        return f"{hours * 60:.0f} minutes"
    return f"{hours:.1f} hours"


def _unsupported_note(spec: FacetAggregateSpec) -> str:
    if not spec.unsupported_requests:
        return ""
    joined = ", ".join(spec.unsupported_requests)
    return f"\n\n_Note: {joined} is not supported yet; showing available metrics only._"


def format_facet_aggregate_answer(
    question: str,
    rows: list[dict[str, object]],
    *,
    mode: str,
) -> str | None:
    spec = parse_facet_aggregate(question, mode=mode)
    if spec is None:
        return None

    entity_label = "Instruction" if spec.entity == FacetEntity.INSTRUCTION else "Payment"
    entity_plural = f"{entity_label.lower()}s"
    qualifier = _facet_qualifier_suffix(spec)
    note = _unsupported_note(spec)

    bucket_rows = [row for row in rows if row.get("bucket") is not None]
    if not bucket_rows:
        return (
            f"No {entity_plural} were found grouped by "
            f"{spec.dimension.label.lower()}{qualifier}."
        )

    if spec.return_mode == "single_winner" and bucket_rows:
        winner = bucket_rows[0]
        bucket = str(winner.get("bucket") or "unknown")
        count = int(winner.get("total") or 0)
        verb = _dimension_action_verb(spec.dimension.key)
        if count == 1:
            count_text = f"1 {entity_label.lower()}"
        else:
            count_text = f"{count} {entity_plural}"
        answer = (
            f"**{bucket}** {verb} the most {entity_plural}{qualifier} "
            f"({count_text})."
        )
        if "avg_approval_time" in spec.metrics:
            answer += (
                f" Average approval time: "
                f"{_format_hours(winner.get('avg_approval_hours'))}."
            )
        return answer + note

    headers: list[str] = [spec.dimension.label]
    table_rows: list[tuple[str | int | float, ...]] = []

    if "count" in spec.metrics:
        headers.append(f"{entity_label}s")
    if "sum_amount" in spec.metrics:
        headers.append("Total amount")
    if "avg_approval_time" in spec.metrics:
        headers.append("Avg approval time")

    for row in bucket_rows:
        cells: list[str | int | float] = [str(row.get("bucket") or "unknown")]
        if "count" in spec.metrics:
            cells.append(int(row.get("total") or 0))
        if "sum_amount" in spec.metrics:
            cells.append(float(row.get("total_amount") or 0))
        if "avg_approval_time" in spec.metrics:
            cells.append(_format_hours(row.get("avg_approval_hours")))
        table_rows.append(tuple(cells))

    total = sum(int(row.get("total") or 0) for row in bucket_rows if "count" in spec.metrics)
    total_suffix = f" ({total} total)" if "count" in spec.metrics else ""
    return (
        f"{entity_label} counts by {spec.dimension.label.lower()}{qualifier}"
        f"{total_suffix}:\n\n"
        f"{_markdown_table(headers, table_rows)}"
        f"{note}"
    )
