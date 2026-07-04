from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Cypher validation patterns ─────────────────────────────────────────────

# Strip comment styles before keyword analysis
_LINE_COMMENT = re.compile(r"//[^\n]*", re.MULTILINE)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)

# Replace string literal content with empty placeholders so keywords inside
# quoted values (e.g. WHERE n.name = 'DELETE') don't trigger false positives
_STRING_LITERAL = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")

# Cypher DML/DDL keywords that must never appear in a read query
_WRITE_KEYWORD = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DROP|DETACH|FOREACH|LOAD)\b",
    re.IGNORECASE,
)

# CALL to built-in or APOC write-capable procedures
_WRITE_PROCEDURE = re.compile(
    r"\bCALL\s+(db\.\w+|apoc\.create\.|apoc\.periodic\.|apoc\.merge\.|apoc\.refactor\.)",
    re.IGNORECASE,
)

# Valid first clause for a read-only query
_READ_START = re.compile(
    r"^\s*(MATCH|OPTIONAL\s+MATCH|WITH|RETURN|UNWIND)\b",
    re.IGNORECASE,
)

# Require an explicit upper bound
_LIMIT_CLAUSE = re.compile(r"\bLIMIT\s+\d+\b", re.IGNORECASE)

_AGGREGATE_RETURN = re.compile(
    r"\bRETURN\b.*\b(count|sum|avg|min|max)\s*\(",
    re.IGNORECASE | re.DOTALL,
)

_COUNT_QUESTION = re.compile(
    r"\b(how many|number of|count of|total number)\b",
    re.IGNORECASE,
)

_PAYMENT_VALUE_DATE_QUESTION = re.compile(r"value\s*date", re.IGNORECASE)

_PAYMENT_TOTAL_AMOUNT = re.compile(
    r"\b(total|sum)\b.*\b(amount|value)\b|\b(amount|value)\b.*\b(total|sum)\b",
    re.IGNORECASE,
)

_LOB_FILTER = re.compile(
    r"\b(?:lob\s+|for\s+|payments?\s+for\s+)?(FICC|FX|DESK)\b",
    re.IGNORECASE,
)

_RANKING_QUESTION = re.compile(
    r"\b(most|top|highest|greatest|largest|biggest|who triggered|which user|which users)\b",
    re.IGNORECASE,
)

_MAX_PAYMENTS_PER_INSTRUCTION = re.compile(
    r"\bwhich instruction\b.*\bpayments?\b|"
    r"\binstruction\b.*\b(maximum|max|most|highest|largest|greatest|biggest)\b.*\bpayments?\b|"
    r"\b(maximum|max|most|highest|largest|greatest|biggest)\b.*\bpayments?\b.*\binstruction\b",
    re.IGNORECASE,
)

_LIST_PAYMENTS_FOR_INSTRUCTION = re.compile(
    r"\b(list|show|enumerate|display)\b.*\bpayments?\b|"
    r"\bpayments?\s+for\s+instruction\b",
    re.IGNORECASE,
)

_INSTRUCTION_ID_IN_QUESTION = re.compile(
    r"instruction\s+(\d{8}-[A-Z0-9_]+-I-\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)

_PAYMENT_STATUSES = ("APPROVED", "SUBMITTED", "REJECTED", "DRAFT", "CANCELLED", "PENDING")

_DENIAL_QUESTION = re.compile(
    r"\b(policy denial|denials?|denied|alert|alerts)\b",
    re.IGNORECASE,
)

_LIST_ALERT_QUESTION = re.compile(
    r"\b(list|show|summarize|summarise|summary|enumerate|display)\b.*\balerts?\b|"
    r"\balerts?\b.*\b(list|show|summarize|summarise|summary|enumerate|display|all)\b|"
    r"\b(all|every)\b.*\balerts?\b",
    re.IGNORECASE,
)

_WEEK_QUESTION = re.compile(
    r"\b(this week|past week|last week|last 7 days|past 7 days)\b",
    re.IGNORECASE,
)

_HIERARCHY_QUESTION = re.compile(
    r"\b(reports?\s+to|reporting\s+to|directly\s+reports?|subordinate|supervisor|"
    r"inversion\s+of\s+control|reporting\s+chain|hierarchy)\b",
    re.IGNORECASE,
)

# UUID pattern for security event exact-lookup detection
_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)

# Combined instruction/payment ID pattern (sequence or legacy UUID)
_ENTITY_ID_PATTERN = re.compile(
    r"(\d{8}-[A-Z0-9_]+-[IP]-\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
_SEQUENCE_PAYMENT_ID_PATTERN = re.compile(
    r"\d{8}-[A-Z0-9_]+-P-\d+",
    re.IGNORECASE,
)
_SEQUENCE_INSTRUCTION_ID_PATTERN = re.compile(
    r"\d{8}-[A-Z0-9_]+-I-\d+",
    re.IGNORECASE,
)
_INSTRUCTION_APPROVER_VIA_PAYMENT = re.compile(
    r"approv\w*\s+of\s+(?:the\s+)?instruction|"
    r"instruction\s+approv|"
    r"instruction\s+(?:used\s+by|for|backing|linked\s+to|associated\s+with)\s+payment",
    re.IGNORECASE,
)
_PAYMENT_APPROVER_QUESTION = re.compile(
    r"(?:who\s+)?approv\w*\s+(?:the\s+)?payment|payment\s+approv",
    re.IGNORECASE,
)

_MAX_CYPHER_LEN = 4096

# ── Fixed parametric queries ───────────────────────────────────────────────

LOOKUP_INSTRUCTION_BY_EVENT_CYPHER = """MATCH (e:SecurityEvent {event_id: $event_id})
OPTIONAL MATCH (e)-[:TARGETS]->(i:Instruction)
OPTIONAL MATCH (e)-[:TARGETS_VERSION]->(v:InstructionVersion)
RETURN e.event_id AS event_id,
       coalesce(i.instruction_id, v.instruction_id) AS instruction_id
LIMIT 1"""

_SECURITY_EVENT_GRAPH_OPTIONAL_MATCHES = """
OPTIONAL MATCH (actor:User)-[:ACTED_AS]->(e)
OPTIONAL MATCH (e)-[:TARGETS]->(i:Instruction)
OPTIONAL MATCH (e)-[:TARGETS_VERSION]->(v:InstructionVersion)
OPTIONAL MATCH (e)-[:TARGETS_PAYMENT]->(pay:Payment)
OPTIONAL MATCH (e)-[:TARGETS_PAYMENT_VERSION]->(pv:PaymentVersion)"""

_INSTRUCTION_ID_COALESCE = (
    "coalesce(v.instruction_id, i.instruction_id, pv.instruction_id, pay.instruction_id, '')"
)

_ALERT_LIST_ENTITY_ID = """CASE
         WHEN e.payment_id IS NOT NULL THEN e.payment_id
         ELSE coalesce(v.instruction_id, i.instruction_id, '')
       END"""


def load_graph_schema(schema_path: Path | None = None) -> str:
    if schema_path is None:
        return ""
    if schema_path.is_file():
        return schema_path.read_text(encoding="utf-8")
    logger.warning("graph schema file not found: %s", schema_path)
    return ""


def normalize_read_only_cypher(cypher: str) -> str:
    """Append LIMIT 1 to aggregate-only queries that omit an explicit LIMIT."""
    stripped = cypher.strip()
    if not stripped:
        return stripped

    normalized = _LINE_COMMENT.sub("", stripped)
    normalized = _BLOCK_COMMENT.sub("", normalized)
    no_strings = _STRING_LITERAL.sub("''", normalized)

    if _LIMIT_CLAUSE.search(no_strings):
        return stripped
    if _AGGREGATE_RETURN.search(no_strings):
        return stripped.rstrip(";") + "\nLIMIT 1"
    return stripped


def is_count_question(question: str) -> bool:
    return bool(_COUNT_QUESTION.search(question))


def is_payment_value_date_question(question: str) -> bool:
    return bool(_PAYMENT_VALUE_DATE_QUESTION.search(question))


def is_payment_total_amount_question(question: str) -> bool:
    if "payment" not in question.lower():
        return False
    return bool(_PAYMENT_TOTAL_AMOUNT.search(question))


def is_payment_count_aggregate_question(question: str) -> bool:
    if not is_count_question(question):
        return False
    if "payment" not in question.lower():
        return False
    if is_payments_for_instruction_question(question):
        return False
    if _LIST_PAYMENTS_FOR_INSTRUCTION.search(question):
        return False
    return True


def is_instruction_count_aggregate_question(question: str) -> bool:
    if not is_count_question(question):
        return False
    q = question.lower()
    if "payment" in q:
        return False
    if is_payments_for_instruction_question(question):
        return False
    return "instruction" in q


def is_security_event_alert_count_question(question: str, *, mode: str = "events") -> bool:
    """True when the user asks for ALERT / denial counts (not all severities)."""
    if not is_count_question(question):
        return False
    if mode not in ("events", "all"):
        return False
    q = question.lower()
    return "alert" in q or bool(_DENIAL_QUESTION.search(question))


def is_security_event_count_aggregate_question(question: str, *, mode: str = "events") -> bool:
    """True when the user asks for total security event counts (INFO + ALERT)."""
    if not is_count_question(question):
        return False
    if mode not in ("events", "all"):
        return False
    if is_security_event_alert_count_question(question, mode=mode):
        return False
    q = question.lower()
    if "payment" in q and "security event" not in q:
        return False
    if "instruction" in q and "payment" not in q and "security event" not in q:
        return False
    return "security event" in q or mode == "events"


def is_security_event_alert_list_question(question: str, *, mode: str = "events") -> bool:
    """True when the user wants a tabular list of ALERT events (not rankings or counts)."""
    if mode not in ("events", "all"):
        return False
    if is_count_question(question):
        return False
    if is_alert_ranking_question(question, mode="events"):
        return False
    flags = _question_flags(question)
    if not (flags["alerts"] or flags["denial"]):
        return False
    if _LIST_ALERT_QUESTION.search(question):
        return True
    q = question.lower()
    return "alert" in q and "actor" in q and "action" in q


def instruction_type_filter_from_question(question: str) -> str | None:
    """Return instruction_type filter for standing/single-use wording."""
    upper = question.upper()
    if "SINGLE_USE" in upper:
        return "SINGLE_USE"
    q = question.lower()
    if re.search(r"\bsingle[\s_-]?use\b", q):
        return "SINGLE_USE"
    if "STANDING" in upper or re.search(r"\bstanding\b", q):
        return "STANDING"
    return None


def _instruction_count_type_cue(question: str) -> bool:
    q = question.lower()
    type_cues = (
        r"\bcreated\s+as\b",
        r"\b(of|with)\s+type\b",
        r"\binstruction\s+type\b",
        r"\b(standing|single[\s_-]?use)\s+type\b",
        r"\btype\s+(standing|single[\s_-]?use)\b",
        r"\b(were|was)\s+created\b",
    )
    return any(re.search(pattern, q) for pattern in type_cues)


def instruction_count_filters_from_question(question: str) -> tuple[str | None, str | None]:
    """Return (status_filter, type_filter) for instruction count queries.

    Standing and single-use questions are instruction_type filters. Lifecycle
    words such as approved, submitted, or draft are status filters.
    """
    status = instruction_status_filter_from_question(question)
    if status:
        return status, None
    instruction_type = instruction_type_filter_from_question(question)
    if instruction_type:
        return None, instruction_type
    return None, None


def instruction_status_filter_from_question(question: str) -> str | None:
    upper = question.upper()
    for status in (
        "SUBMITTED",
        "APPROVED",
        "REJECTED",
        "SUSPENDED",
        "EXPIRED",
        "DELETED",
        "DRAFT",
        "USED",
    ):
        if status in upper:
            return status

    q = question.lower()
    natural_status_patterns = (
        (r"\bpending[\s_-]?approval\b", "SUBMITTED"),
        (r"\bpending\b", "SUBMITTED"),
        (r"\bsubmitted\b", "SUBMITTED"),
        (r"\bapproved\b", "APPROVED"),
        (r"\bsuspended\b", "SUSPENDED"),
        (r"\brejected\b", "REJECTED"),
        (r"\bexpired\b", "EXPIRED"),
        (r"\bdeleted\b", "DELETED"),
        (r"\bdraft\b", "DRAFT"),
        (r"\bused\b", "USED"),
    )
    for pattern, status in natural_status_patterns:
        if re.search(pattern, q):
            return status
    return None


def lob_filter_from_question(question: str) -> str | None:
    match = _LOB_FILTER.search(question)
    return match.group(1).upper() if match else None


def payment_aggregate_period_label(question: str) -> str:
    flags = _question_flags(question)
    if flags["today"]:
        return "today"
    if flags["week"]:
        return "this week"
    return "all time"


def is_max_payments_per_instruction_question(question: str) -> bool:
    q = question.lower()
    return "instruction" in q and "payment" in q and bool(_MAX_PAYMENTS_PER_INSTRUCTION.search(question))


def is_payments_for_instruction_question(question: str) -> bool:
    q = question.lower()
    if not extract_entity_ids(question):
        return False
    if is_max_payments_per_instruction_question(question):
        return False
    if "approv" in q and ("who" in q or "when" in q or "why" in q):
        return False
    if "payment" not in q or "instruction" not in q:
        return False
    return bool(_LIST_PAYMENTS_FOR_INSTRUCTION.search(question))


def instruction_id_from_list_payments_question(question: str) -> str | None:
    match = _INSTRUCTION_ID_IN_QUESTION.search(question)
    if match:
        return match.group(1)
    entity_ids = extract_entity_ids(question)
    return entity_ids[0] if entity_ids else None


def payment_status_filter_from_question(question: str) -> str | None:
    upper = question.upper()
    for status in _PAYMENT_STATUSES:
        if status in upper:
            return status
    return None


def is_alert_ranking_question(question: str, *, mode: str) -> bool:
    if mode != "events":
        return False
    flags = _question_flags(question)
    return (
        flags["ranking"]
        and flags["denial"]
        and (flags["alerts"] or flags["denial"])
    )


def ranking_period_label(question: str) -> str:
    flags = _question_flags(question)
    if flags["today"]:
        return "today"
    if flags["week"]:
        return "this week"
    return "all time"


def _question_flags(question: str) -> dict[str, bool]:
    q = question.lower()
    return {
        "count": is_count_question(question),
        "ranking": bool(_RANKING_QUESTION.search(question)),
        "denial": bool(_DENIAL_QUESTION.search(question)),
        "today": "today" in q,
        "week": bool(_WEEK_QUESTION.search(question)),
        "alerts": "alert" in q,
        "payments": "payment" in q,
        "instructions": "instruction" in q and "payment" not in q,
    }


def _time_filter_cypher(flags: dict[str, bool]) -> str:
    if flags["today"]:
        return "AND date(datetime(e.timestamp)) = date()"
    if flags["week"]:
        return "AND date(datetime(e.timestamp)) >= date() - duration('P7D')"
    return ""


def _payment_value_date_filter_cypher(flags: dict[str, bool]) -> str:
    """value_date is an ISO date string on PaymentVersion — compare via toString(date())."""
    if flags["today"]:
        return "AND p.value_date STARTS WITH toString(date())"
    if flags["week"]:
        return "AND p.value_date >= toString(date() - duration('P7D'))"
    return ""


def _payment_time_filter_cypher(flags: dict[str, bool], *, use_value_date: bool = False) -> str:
    if use_value_date:
        return _payment_value_date_filter_cypher(flags)
    if flags["today"]:
        return "AND date(datetime(p.updated_at)) = date()"
    if flags["week"]:
        return "AND date(datetime(p.updated_at)) >= date() - duration('P7D')"
    return ""


def _payment_status_filter_cypher(question: str) -> str:
    status = payment_status_filter_from_question(question)
    if status:
        return f"AND p.status = '{status}'"
    q = question.lower()
    if "approv" in q and "reject" not in q:
        return "AND p.status = 'APPROVED'"
    if "reject" in q:
        return "AND p.status = 'REJECTED'"
    if "submit" in q:
        return "AND p.status = 'SUBMITTED'"
    return ""


def _payment_aggregate_queries(
    question: str,
    flags: dict[str, bool],
    *,
    sum_amount: bool,
) -> list[tuple[str, str]]:
    lob = lob_filter_from_question(question)
    lob_filter = f"AND p.owning_lob = '{lob}'" if lob else ""
    status_filter = _payment_status_filter_cypher(question)
    time_filter = _payment_time_filter_cypher(
        flags,
        use_value_date=is_payment_value_date_question(question),
    )

    if sum_amount:
        return [
            (
                "payment_total_amount",
                f"""MATCH (pay:Payment)-[:CURRENT]->(p:PaymentVersion)
WHERE true {status_filter} {lob_filter} {time_filter}
RETURN coalesce(p.currency, 'USD') AS currency,
       count(pay) AS payment_count,
       sum(p.amount) AS total_amount
ORDER BY currency
LIMIT 10""",
            )
        ]

    return [
        (
            "payment_count",
            f"""MATCH (pay:Payment)-[:CURRENT]->(p:PaymentVersion)
WHERE true {status_filter} {lob_filter} {time_filter}
RETURN count(pay) AS total
LIMIT 1""",
        )
    ]


def _alert_ranking_queries(
    *,
    time_filter: str,
    payments_only: bool = False,
    instructions_only: bool = False,
) -> list[tuple[str, str]]:
    domain_filter = ""
    if payments_only:
        domain_filter = "AND e.payment_id IS NOT NULL"
    elif instructions_only:
        domain_filter = "AND e.payment_id IS NULL"

    return [
        (
            "ranking",
            f"""MATCH (e:SecurityEvent {{severity: 'ALERT'}})
WHERE true {domain_filter} {time_filter}
OPTIONAL MATCH (actor:User)-[:ACTED_AS]->(e)
WITH actor.user_id AS user_id,
     coalesce(actor.display_name, actor.user_id, '') AS actor_display,
     count(e) AS alert_count,
     sum(CASE WHEN e.payment_id IS NOT NULL THEN 1 ELSE 0 END) AS payment_alerts,
     sum(CASE WHEN e.payment_id IS NULL THEN 1 ELSE 0 END) AS instruction_alerts
WHERE user_id IS NOT NULL
RETURN user_id, actor_display, alert_count, payment_alerts, instruction_alerts
ORDER BY alert_count DESC
LIMIT 20""",
        ),
        (
            "details",
            f"""MATCH (e:SecurityEvent {{severity: 'ALERT'}})
WHERE true {domain_filter} {time_filter}{_SECURITY_EVENT_GRAPH_OPTIONAL_MATCHES}
RETURN e.event_id, e.timestamp, e.action, e.message, e.severity,
       CASE WHEN e.payment_id IS NOT NULL THEN 'payment' ELSE 'instruction' END AS domain,
       coalesce(e.payment_id, '') AS payment_id,
       {_INSTRUCTION_ID_COALESCE} AS instruction_id,
       coalesce(pv.amount, 0) AS amount,
       coalesce(pv.currency, '') AS currency,
       coalesce(pv.owning_lob, e.owning_lob, v.owning_lob, '') AS owning_lob,
       coalesce(actor.display_name, actor.user_id, '') AS actor_display
ORDER BY e.timestamp DESC
LIMIT 200""",
        ),
    ]


def _is_subordinate_approver_question(question: str) -> bool:
    """Approver directly reports to the instruction creator (inversion-of-control)."""
    q = question.lower()
    if "approv" not in q:
        return False
    if not _HIERARCHY_QUESTION.search(question):
        return False
    return any(
        token in q
        for token in (
            "creator",
            "created",
            "supervisor",
            "subordinate",
            "reports to",
            "reporting to",
            "directly report",
        )
    )


def extract_payment_ids(text: str) -> list[str]:
    """Return sequence payment IDs (-P-) in order of appearance."""
    return list(dict.fromkeys(match.group(0) for match in _SEQUENCE_PAYMENT_ID_PATTERN.finditer(text)))


def extract_instruction_ids(text: str) -> list[str]:
    """Return sequence instruction IDs (-I-) in order of appearance."""
    return list(
        dict.fromkeys(match.group(0) for match in _SEQUENCE_INSTRUCTION_ID_PATTERN.finditer(text))
    )


def is_instruction_approver_via_payment_question(question: str) -> bool:
    """Approver of the backing instruction when the question anchors on a payment ID."""
    q = question.lower()
    if "approv" not in q or "instruction" not in q:
        return False
    if not extract_payment_ids(question):
        return False
    if _PAYMENT_APPROVER_QUESTION.search(question) and not _INSTRUCTION_APPROVER_VIA_PAYMENT.search(
        question
    ):
        return False
    if _INSTRUCTION_APPROVER_VIA_PAYMENT.search(question):
        return True
    return "payment" in q and not extract_instruction_ids(question)


def _is_instruction_approval_lookup(question: str) -> bool:
    q = question.lower()
    if "approv" not in q:
        return False
    if is_instruction_approver_via_payment_question(question):
        return False
    if "payment" in q and "instruction" not in q:
        return False
    if extract_payment_ids(question) and not extract_instruction_ids(question):
        return False
    return bool(_ENTITY_ID_PATTERN.search(question)) or "instruction" in q


def _is_payment_approval_lookup(question: str, *, mode: str) -> bool:
    q = question.lower()
    if "approv" not in q:
        return False
    if is_instruction_approver_via_payment_question(question):
        return False
    if "instruction" in q and "payment" not in q:
        return False
    if not _ENTITY_ID_PATTERN.search(question):
        return False
    return "payment" in q or mode == "payments"


_APPROVAL_LOOKUP_EVENT_AUTH = """
OPTIONAL MATCH (approveEvent:SecurityEvent)-[:TARGETS]->(i)
WHERE approveEvent.action = 'APPROVE' AND approveEvent.outcome = 'success'
WITH v, approverUser, approveEvent
ORDER BY approveEvent.timestamp DESC
WITH v, approverUser, collect(approveEvent)[0] AS approveEvent
"""

_APPROVAL_AUTH_COALESCE = """
       coalesce(
         CASE WHEN v.authorization_summary IS NULL OR trim(toString(v.authorization_summary)) = ''
              THEN null ELSE v.authorization_summary END,
         approveEvent.authorization_summary
       ) AS authorization_summary,
       coalesce(
         CASE WHEN v.authorization_basis IS NULL OR trim(toString(v.authorization_basis)) IN ['', '[]']
              THEN null ELSE v.authorization_basis END,
         approveEvent.authorization_basis
       ) AS authorization_basis
"""


def _instruction_approval_lookup_queries(instruction_id: str) -> list[tuple[str, str]]:
    return [
        (
            "approval_lookup",
            f"""MATCH (i:Instruction {{instruction_id: '{instruction_id}'}})-[:CURRENT]->(v:InstructionVersion)
OPTIONAL MATCH (approverUser:User {{user_id: v.approver_user_id}})
{_APPROVAL_LOOKUP_EVENT_AUTH}
RETURN v.instruction_id AS instruction_id,
       v.status AS status,
       coalesce(v.approved_at, approveEvent.timestamp) AS approved_at,
       coalesce(approverUser.display_name, v.approver_user_id, '') AS approver_display,
{_APPROVAL_AUTH_COALESCE}
LIMIT 1""",
        ),
    ]


def _instruction_approver_via_payment_queries(payment_id: str) -> list[tuple[str, str]]:
    return [
        (
            "instruction_approver_via_payment",
            f"""MATCH (i:Instruction)-[:HAS_PAYMENT]->(p:Payment {{payment_id: '{payment_id}'}})
MATCH (i)-[:CURRENT]->(v:InstructionVersion)
OPTIONAL MATCH (approverUser:User {{user_id: v.approver_user_id}})
{_APPROVAL_LOOKUP_EVENT_AUTH}
RETURN p.payment_id AS payment_id,
       v.instruction_id AS instruction_id,
       v.status AS status,
       coalesce(v.approved_at, approveEvent.timestamp) AS approved_at,
       coalesce(approverUser.display_name, v.approver_user_id, '') AS approver_display,
{_APPROVAL_AUTH_COALESCE}
LIMIT 1""",
        ),
    ]


def _payments_for_instruction_queries(
    instruction_id: str,
    *,
    status: str | None = None,
) -> list[tuple[str, str]]:
    status_filter = f"AND p.status = '{status}'" if status else ""
    return [
        (
            "payments_for_instruction",
            f"""MATCH (i:Instruction {{instruction_id: '{instruction_id}'}})-[:HAS_PAYMENT]->(pay:Payment)
MATCH (pay)-[:CURRENT]->(p:PaymentVersion)
WHERE true {status_filter}
WITH collect(DISTINCT pay) AS payments
UNWIND payments AS pay
MATCH (pay)-[:CURRENT]->(p:PaymentVersion)
OPTIONAL MATCH (creator:User)-[:CREATED_PAYMENT]->(p)
OPTIONAL MATCH (approver:User)-[:APPROVED_PAYMENT]->(p)
WITH pay, p,
     head(collect(DISTINCT creator)) AS creator,
     head(collect(DISTINCT approver)) AS approver
RETURN pay.payment_id AS payment_id,
       p.instruction_id AS instruction_id,
       p.status AS status,
       p.amount AS amount,
       p.currency AS currency,
       p.value_date AS value_date,
       p.owning_lob AS owning_lob,
       p.created_at AS created_at,
       coalesce(creator.display_name, creator.user_id, p.creator_user_id, '') AS creator_display,
       coalesce(approver.display_name, approver.user_id, p.approver_user_id, '') AS approver_display
ORDER BY p.created_at ASC
LIMIT 200""",
        ),
    ]


def _max_payments_per_instruction_queries() -> list[tuple[str, str]]:
    """Instruction with the most payments, plus one row per payment."""
    return [
        (
            "max_payments_per_instruction",
            """MATCH (i:Instruction)-[:HAS_PAYMENT]->(pay:Payment)
WITH i.instruction_id AS instruction_id, count(DISTINCT pay) AS payment_count
ORDER BY payment_count DESC, instruction_id ASC
LIMIT 1
WITH instruction_id, payment_count
MATCH (i:Instruction {instruction_id: instruction_id})-[:HAS_PAYMENT]->(pay:Payment)
MATCH (pay)-[:CURRENT]->(p:PaymentVersion)
WITH instruction_id, payment_count, pay, p
ORDER BY p.created_at ASC
WITH instruction_id, payment_count, collect(DISTINCT pay) AS payments
UNWIND payments AS pay
MATCH (pay)-[:CURRENT]->(p:PaymentVersion)
OPTIONAL MATCH (creator:User)-[:CREATED_PAYMENT]->(p)
OPTIONAL MATCH (approver:User)-[:APPROVED_PAYMENT]->(p)
WITH instruction_id,
     payment_count,
     p,
     head(collect(DISTINCT creator)) AS creator,
     head(collect(DISTINCT approver)) AS approver
RETURN instruction_id,
       payment_count,
       p.payment_id AS payment_id,
       p.created_at AS created_at,
       coalesce(creator.display_name, creator.user_id, p.creator_user_id, '') AS creator_display,
       coalesce(approver.display_name, approver.user_id, p.approver_user_id, '') AS approver_display
ORDER BY created_at ASC
LIMIT 200""",
        ),
    ]


def _payment_approval_lookup_queries(payment_id: str) -> list[tuple[str, str]]:
    return [
        (
            "payment_approval_lookup",
            f"""MATCH (e:SecurityEvent)
WHERE e.payment_id = '{payment_id}'
  AND e.action = 'APPROVE_PAYMENT'
  AND e.outcome = 'success'
OPTIONAL MATCH (actor:User)-[:ACTED_AS]->(e)
RETURN e.payment_id AS payment_id,
       e.timestamp AS approved_at,
       coalesce(actor.display_name, actor.user_id, '') AS approver_display,
       e.authorization_summary AS authorization_summary,
       e.authorization_basis AS authorization_basis
ORDER BY e.timestamp DESC
LIMIT 1""",
        ),
    ]


def _instruction_count_queries(
    question: str, flags: dict[str, bool]
) -> list[tuple[str, str]]:
    """Count distinct instructions via CURRENT version (Mongo-aligned business key)."""
    status, instruction_type = instruction_count_filters_from_question(question)
    lob = lob_filter_from_question(question)
    status_clause = f"AND v.status = '{status}'" if status else ""
    type_clause = f"AND v.instruction_type = '{instruction_type}'" if instruction_type else ""
    lob_clause = f"AND v.owning_lob = '{lob}'" if lob else ""

    time_clause = ""
    if flags["today"]:
        time_clause = "AND v.timestamp IS NOT NULL AND date(datetime(v.timestamp)) = date()"
    elif flags["week"]:
        time_clause = (
            "AND v.timestamp IS NOT NULL "
            "AND date(datetime(v.timestamp)) >= date() - duration('P7D')"
        )

    q = question.lower()
    if "per lob" in q or "by lob" in q or "each lob" in q:
        return [
            (
                "count_by_lob",
                f"""MATCH (i:Instruction)-[:CURRENT]->(v:InstructionVersion)
WHERE true {status_clause} {type_clause} {time_clause}
RETURN v.owning_lob AS lob, count(DISTINCT i.instruction_id) AS total
ORDER BY lob
LIMIT 20""",
            ),
        ]

    return [
        (
            "count",
            f"""MATCH (i:Instruction)-[:CURRENT]->(v:InstructionVersion)
WHERE true {status_clause} {type_clause} {lob_clause} {time_clause}
RETURN count(DISTINCT i.instruction_id) AS total LIMIT 1""",
        ),
        (
            "details",
            f"""MATCH (i:Instruction)-[:CURRENT]->(v:InstructionVersion)
WHERE true {status_clause} {type_clause} {lob_clause} {time_clause}
RETURN v.instruction_id, v.status, v.instruction_type, v.owning_lob, v.currency, v.wire_scope,
       v.version_number
ORDER BY v.instruction_id
LIMIT 200""",
        ),
    ]


def _instruction_subordinate_approver_queries() -> list[tuple[str, str]]:
    """Instructions where approver-[:REPORTS_TO]->creator on the current version."""
    return [
        (
            "hierarchy_violations",
            """MATCH (i:Instruction)-[:CURRENT]->(v:InstructionVersion)
WHERE v.approver_user_id IS NOT NULL AND v.creator_user_id IS NOT NULL
MATCH (creator:User {user_id: v.creator_user_id})
MATCH (approver:User {user_id: v.approver_user_id})-[:REPORTS_TO]->(creator)
RETURN v.instruction_id, v.owning_lob, v.status, v.instruction_type,
       v.currency, v.wire_scope,
       v.creditor_name, v.creditor_account,
       v.effective_date, v.end_date, v.is_expired,
       creator.user_id AS creator_user_id,
       coalesce(creator.display_name, creator.user_id, '') AS creator_display,
       approver.user_id AS approver_user_id,
       coalesce(approver.display_name, approver.user_id, '') AS approver_display,
       approver.supervisor_id AS approver_supervisor_id
ORDER BY v.instruction_id
LIMIT 50""",
        ),
    ]


def _escape_cypher_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _instruction_detail_by_id_queries(instruction_id: str) -> list[tuple[str, str]]:
    safe_id = _escape_cypher_literal(instruction_id)
    return [
        (
            "instruction_detail",
            f"""MATCH (i:Instruction {{instruction_id: '{safe_id}'}})-[:CURRENT]->(v:InstructionVersion)
OPTIONAL MATCH (creator:User {{user_id: v.creator_user_id}})
OPTIONAL MATCH (approver:User {{user_id: v.approver_user_id}})
OPTIONAL MATCH (rejector:User {{user_id: v.rejector_user_id}})
RETURN v.instruction_id AS instruction_id,
       v.status AS status,
       v.owning_lob AS owning_lob,
       v.currency AS currency,
       v.wire_scope AS wire_scope,
       v.instruction_type AS instruction_type,
       coalesce(creator.display_name, v.creator_user_id, '') AS creator_display,
       coalesce(approver.display_name, v.approver_user_id, '') AS approver_display,
       coalesce(rejector.display_name, v.rejector_user_id, '') AS rejector_display,
       v.approved_at AS approved_at,
       v.rejection_reason AS rejection_reason,
       v.authorization_summary AS authorization_summary
LIMIT 1""",
        ),
    ]


def _instruction_list_by_status_queries(*, status: str, lob: str | None = None) -> list[tuple[str, str]]:
    lob_clause = f"AND v.owning_lob = '{_escape_cypher_literal(lob)}'" if lob else ""
    safe_status = _escape_cypher_literal(status)
    return [
        (
            "instruction_inventory",
            f"""MATCH (i:Instruction)-[:CURRENT]->(v:InstructionVersion {{status: '{safe_status}'}})
WHERE true {lob_clause}
OPTIONAL MATCH (creator:User {{user_id: v.creator_user_id}})
OPTIONAL MATCH (approver:User {{user_id: v.approver_user_id}})
RETURN v.instruction_id AS instruction_id,
       v.status AS status,
       v.owning_lob AS owning_lob,
       v.currency AS currency,
       v.wire_scope AS wire_scope,
       coalesce(creator.display_name, v.creator_user_id, '') AS creator_display,
       coalesce(approver.display_name, v.approver_user_id, '') AS approver_display,
       v.approved_at AS approved_at
ORDER BY v.instruction_id
LIMIT 200""",
        ),
    ]


def _instruction_list_by_type_queries(*, instruction_type: str, lob: str | None = None) -> list[tuple[str, str]]:
    lob_clause = f"AND v.owning_lob = '{_escape_cypher_literal(lob)}'" if lob else ""
    safe_type = _escape_cypher_literal(instruction_type)
    return [
        (
            "instruction_inventory",
            f"""MATCH (i:Instruction)-[:CURRENT]->(v:InstructionVersion {{instruction_type: '{safe_type}'}})
WHERE true {lob_clause}
OPTIONAL MATCH (creator:User {{user_id: v.creator_user_id}})
OPTIONAL MATCH (approver:User {{user_id: v.approver_user_id}})
RETURN v.instruction_id AS instruction_id,
       v.status AS status,
       v.instruction_type AS instruction_type,
       v.owning_lob AS owning_lob,
       v.currency AS currency,
       v.wire_scope AS wire_scope,
       coalesce(creator.display_name, v.creator_user_id, '') AS creator_display,
       coalesce(approver.display_name, v.approver_user_id, '') AS approver_display,
       v.approved_at AS approved_at
ORDER BY v.instruction_id
LIMIT 200""",
        ),
    ]


def _instructions_created_by_user_queries(user_id: str) -> list[tuple[str, str]]:
    safe_user = _escape_cypher_literal(user_id)
    return [
        (
            "instructions_by_creator",
            f"""MATCH (u:User {{user_id: '{safe_user}'}})-[:CREATED]->(v:InstructionVersion)<-[:CURRENT]-(i:Instruction)
OPTIONAL MATCH (approver:User {{user_id: v.approver_user_id}})
RETURN v.instruction_id AS instruction_id,
       v.status AS status,
       v.owning_lob AS owning_lob,
       v.currency AS currency,
       coalesce(u.display_name, u.user_id, '') AS creator_display,
       coalesce(approver.display_name, v.approver_user_id, '') AS approver_display,
       v.approved_at AS approved_at
ORDER BY v.instruction_id
LIMIT 200""",
        ),
    ]


def _instruction_mutual_approval_queries() -> list[tuple[str, str]]:
    return [
        (
            "mutual_approval",
            """MATCH (a:User)-[:APPROVED]->(va:InstructionVersion)<-[:CREATED]-(b:User)
MATCH (b)-[:APPROVED]->(vb:InstructionVersion)<-[:CREATED]-(a)
WHERE a.user_id <> b.user_id
RETURN coalesce(a.display_name, a.user_id, '') AS user_a_display,
       a.user_id AS user_a_id,
       coalesce(b.display_name, b.user_id, '') AS user_b_display,
       b.user_id AS user_b_id,
       va.instruction_id AS approved_by_a,
       vb.instruction_id AS approved_by_b,
       va.owning_lob AS lob_a,
       vb.owning_lob AS lob_b
ORDER BY user_a_id, user_b_id
LIMIT 50""",
        ),
    ]


def _instruction_self_approval_queries() -> list[tuple[str, str]]:
    return [
        (
            "self_approval",
            """MATCH (i:Instruction)-[:CURRENT]->(v:InstructionVersion)
WHERE v.creator_user_id IS NOT NULL
  AND v.approver_user_id IS NOT NULL
  AND v.creator_user_id = v.approver_user_id
OPTIONAL MATCH (creator:User {user_id: v.creator_user_id})
RETURN v.instruction_id AS instruction_id,
       v.status AS status,
       v.owning_lob AS owning_lob,
       coalesce(creator.display_name, v.creator_user_id, '') AS creator_display,
       v.approved_at AS approved_at
ORDER BY v.instruction_id
LIMIT 50""",
        ),
    ]


def _instruction_duplicate_routes_queries(*, lob: str | None = None) -> list[tuple[str, str]]:
    lob_clause = ""
    if lob:
        lob_clause = f"AND v1.owning_lob = '{_escape_cypher_literal(lob)}'"
    return [
        (
            "duplicate_routes",
            f"""MATCH (i1:Instruction)-[:CONFLICTS_WITH]-(i2:Instruction)
WHERE elementId(i1) < elementId(i2)
MATCH (i1)-[:CURRENT]->(v1:InstructionVersion)
MATCH (i2)-[:CURRENT]->(v2:InstructionVersion)
WHERE v1.status IN ['APPROVED', 'SUBMITTED']
  AND v2.status IN ['APPROVED', 'SUBMITTED']
  {lob_clause}
RETURN i1.instruction_id AS instruction_id_a,
       i2.instruction_id AS instruction_id_b,
       v1.owning_lob AS owning_lob,
       v1.currency AS currency,
       v1.creditor_account AS creditor_account,
       v1.creditor_name AS creditor_name
ORDER BY v1.creditor_account, v1.currency
LIMIT 50""",
        ),
    ]


def _instruction_security_event_timeline_queries(instruction_id: str) -> list[tuple[str, str]]:
    safe_id = _escape_cypher_literal(instruction_id)
    event_return = """
OPTIONAL MATCH (actor:User)-[:ACTED_AS]->(event)
RETURN event.event_id AS event_id,
       event.timestamp AS timestamp,
       event.action AS action,
       event.severity AS severity,
       event.outcome AS outcome,
       event.message AS message,
       coalesce(actor.display_name, actor.user_id, '') AS actor_display
ORDER BY timestamp ASC
LIMIT 200"""
    return [
        (
            "instruction_timeline_targets",
            f"""MATCH (i:Instruction {{instruction_id: '{safe_id}'}})
MATCH (event:SecurityEvent)-[:TARGETS]->(i)
{event_return}""",
        ),
        (
            "instruction_timeline_versions",
            f"""MATCH (i:Instruction {{instruction_id: '{safe_id}'}})-[:HAS_VERSION]->(v:InstructionVersion)
MATCH (event:SecurityEvent)-[:TARGETS_VERSION]->(v)
{event_return}""",
        ),
    ]


def _alert_count_today_queries() -> list[tuple[str, str]]:
    return [
        (
            "alert_count_today",
            """MATCH (e:SecurityEvent {severity: 'ALERT'})
WHERE date(datetime(e.timestamp)) = date()
RETURN count(e) AS total
LIMIT 1""",
        ),
    ]


def _security_event_domain_where(*, domain: str, time_filter: str) -> str:
    if domain == "payments":
        return f"e.payment_id IS NOT NULL {time_filter}"
    if domain == "instructions":
        return f"e.payment_id IS NULL {time_filter}"
    return f"true {time_filter}"


def _security_event_count_queries(
    *,
    time_filter: str,
    domain: str,
) -> list[tuple[str, str]]:
    """Count all security events with ALERT/INFO breakdown."""
    domain_where = _security_event_domain_where(domain=domain, time_filter=time_filter)
    return [
        (
            "security_event_count",
            f"""MATCH (e:SecurityEvent)
WHERE {domain_where}
RETURN count(e) AS total,
       sum(CASE WHEN e.severity = 'ALERT' THEN 1 ELSE 0 END) AS alert_count,
       sum(CASE WHEN e.severity = 'INFO' THEN 1 ELSE 0 END) AS info_count
LIMIT 1""",
        ),
    ]


def _security_event_alert_count_queries(
    *,
    time_filter: str,
    domain: str,
) -> list[tuple[str, str]]:
    if domain == "payments":
        count_where = f"e.payment_id IS NOT NULL AND e.severity = 'ALERT' {time_filter}"
        detail_optional = """
OPTIONAL MATCH (actor:User)-[:ACTED_AS]->(e)
OPTIONAL MATCH (e)-[:TARGETS_PAYMENT]->(pay:Payment)
OPTIONAL MATCH (e)-[:TARGETS_PAYMENT_VERSION]->(pv:PaymentVersion)"""
        detail_return = """RETURN e.event_id, e.timestamp, e.action, e.message, e.severity,
       e.payment_id AS payment_id,
       coalesce(pv.instruction_id, pay.instruction_id, '') AS instruction_id,
       coalesce(pv.amount, 0) AS amount,
       coalesce(pv.currency, '') AS currency,
       coalesce(pv.owning_lob, e.owning_lob, '') AS owning_lob,
       coalesce(actor.display_name, actor.user_id, '') AS actor_display"""
    elif domain == "instructions":
        count_where = f"e.payment_id IS NULL AND e.severity = 'ALERT' {time_filter}"
        detail_optional = """
OPTIONAL MATCH (e)-[:TARGETS]->(i:Instruction)
OPTIONAL MATCH (e)-[:TARGETS_VERSION]->(v:InstructionVersion)
OPTIONAL MATCH (actor:User)-[:ACTED_AS]->(e)"""
        detail_return = """RETURN e.event_id, e.timestamp, e.action, e.message, e.severity,
       coalesce(v.instruction_id, i.instruction_id, '') AS instruction_id,
       coalesce(e.owning_lob, v.owning_lob, '') AS lob,
       coalesce(actor.display_name, actor.user_id, '') AS actor_display"""
    else:
        count_where = f"true {time_filter}"
        detail_optional = _SECURITY_EVENT_GRAPH_OPTIONAL_MATCHES
        detail_return = f"""RETURN e.event_id, e.timestamp, e.action, e.message, e.severity,
       CASE WHEN e.payment_id IS NOT NULL THEN 'payment' ELSE 'instruction' END AS domain,
       coalesce(e.payment_id, '') AS payment_id,
       {_INSTRUCTION_ID_COALESCE} AS instruction_id,
       coalesce(actor.display_name, actor.user_id, '') AS actor_display"""

    count_match = (
        "MATCH (e:SecurityEvent)"
        if domain in ("payments", "instructions")
        else "MATCH (e:SecurityEvent {severity: 'ALERT'})"
    )
    return [
        (
            "count",
            f"""{count_match}
WHERE {count_where}
RETURN count(e) AS total LIMIT 1""",
        ),
        (
            "details",
            f"""{count_match}
WHERE {count_where}{detail_optional}
{detail_return}
ORDER BY e.timestamp DESC
LIMIT 200""",
        ),
    ]


def _security_event_alert_list_queries(
    *,
    time_filter: str,
    domain: str,
) -> list[tuple[str, str]]:
    domain_filter = ""
    if domain == "payments":
        domain_filter = "AND e.payment_id IS NOT NULL"
    elif domain == "instructions":
        domain_filter = "AND e.payment_id IS NULL"

    return [
        (
            "security_event_alert_list",
            f"""MATCH (e:SecurityEvent {{severity: 'ALERT'}})
WHERE true {domain_filter} {time_filter}{_SECURITY_EVENT_GRAPH_OPTIONAL_MATCHES}
RETURN e.event_id AS event_id,
       e.timestamp AS timestamp,
       e.action AS action,
       CASE WHEN e.payment_id IS NOT NULL THEN 'payment' ELSE 'instruction' END AS entity_type,
       {_ALERT_LIST_ENTITY_ID} AS entity_id,
       coalesce(actor.display_name, actor.user_id, '') AS actor_display
ORDER BY e.timestamp DESC
LIMIT 200""",
        ),
    ]


def plan_graph_queries(question: str, *, mode: str) -> list[tuple[str, str]] | None:
    """Deterministic read-only Cypher for common aggregate questions."""
    from cypher_builder.builder import CypherQueryBuilder

    builder = CypherQueryBuilder()
    flags = _question_flags(question)
    time_filter = _time_filter_cypher(flags)

    if mode == "instructions" and _is_subordinate_approver_question(question):
        return builder.instruction_subordinate_approver()

    if is_instruction_approver_via_payment_question(question):
        payment_ids = extract_payment_ids(question)
        if payment_ids:
            return builder.instruction_approver_via_payment(payment_ids[0])

    if mode == "instructions" and _is_instruction_approval_lookup(question):
        instruction_ids = extract_instruction_ids(question) or extract_entity_ids(question)
        if instruction_ids:
            return builder.instruction_approval_lookup(instruction_ids[0])

    if mode in ("payments", "events") and _is_payment_approval_lookup(question, mode=mode):
        if not is_payments_for_instruction_question(question):
            entity_ids = extract_entity_ids(question)
            if entity_ids:
                return builder.payment_approval_lookup(entity_ids[0])

    if mode in ("payments", "all") and is_payments_for_instruction_question(question):
        instruction_id = instruction_id_from_list_payments_question(question)
        if instruction_id:
            return builder.payments_for_instruction(
                instruction_id,
                status=payment_status_filter_from_question(question),
            )

    if mode in ("payments", "all") and is_max_payments_per_instruction_question(question):
        return builder.max_payments_per_instruction()

    if (
        mode == "events"
        and flags["ranking"]
        and flags["denial"]
        and (flags["alerts"] or flags["denial"])
    ):
        if flags["payments"]:
            return builder.alert_ranking(time_filter=time_filter, payments_only=True)
        if flags["instructions"]:
            return builder.alert_ranking(time_filter=time_filter, instructions_only=True)
        return builder.alert_ranking(time_filter=time_filter)

    if mode in ("events", "all") and is_security_event_alert_list_question(
        question, mode=mode
    ):
        if flags["payments"]:
            return builder.security_event_alert_list(
                time_filter=time_filter, domain="payments"
            )
        if flags["instructions"]:
            return builder.security_event_alert_list(
                time_filter=time_filter, domain="instructions"
            )
        return builder.security_event_alert_list(time_filter=time_filter, domain="all")

    if mode in ("payments", "all") and is_payment_total_amount_question(question):
        return builder.payment_aggregate(question, flags, sum_amount=True)

    if mode in ("payments", "all") and is_payment_count_aggregate_question(question):
        return builder.payment_aggregate(question, flags, sum_amount=False)

    if mode == "instructions" and is_instruction_count_aggregate_question(question):
        return builder.instruction_count(question, flags)

    if not flags["count"]:
        return None

    if is_security_event_count_aggregate_question(question, mode=mode):
        if flags["payments"]:
            return builder.security_event_count(time_filter=time_filter, domain="payments")
        if flags["instructions"]:
            return builder.security_event_count(time_filter=time_filter, domain="instructions")
        return builder.security_event_count(time_filter=time_filter, domain="all")

    if mode in ("events", "all") and flags["alerts"] and flags["payments"]:
        return builder.security_event_alert_count(time_filter=time_filter, domain="payments")

    if mode in ("events", "all") and flags["alerts"] and flags["instructions"]:
        return builder.security_event_alert_count(time_filter=time_filter, domain="instructions")

    if mode in ("events", "all") and flags["alerts"] and not flags["payments"] and not flags["instructions"]:
        return builder.security_event_alert_count(time_filter=time_filter, domain="all")

    return None


def validate_read_only_cypher(cypher: str) -> None:
    """
    Multi-layer read-only guard for LLM-generated Cypher.

    Layers (innermost protection is the Neo4j READ_ACCESS session in neo4j.py):
    1. Reject empty or oversized query
    2. Reject multi-statement injection (embedded semicolons)
    3. Strip comments and string literal content before keyword analysis
    4. Require query to start with a read clause (MATCH / WITH / RETURN / UNWIND)
    5. Reject write DML/DDL keywords (CREATE, MERGE, SET, DELETE, …)
    6. Reject CALL to write-capable built-in or APOC procedures
    7. Require an explicit LIMIT clause to prevent full-graph scans
    """
    stripped = cypher.strip()

    # Layer 1 — empty / oversized
    if not stripped:
        raise ValueError("Cypher validation failed: empty query")
    if len(stripped) > _MAX_CYPHER_LEN:
        raise ValueError(
            f"Cypher validation failed: query exceeds {_MAX_CYPHER_LEN} characters"
        )

    # Layer 2 — multi-statement injection
    if ";" in stripped.rstrip(";"):
        raise ValueError(
            "Cypher validation failed: multiple statements are not allowed"
        )

    # Layer 3 — normalize: strip comments then string literals
    normalized = _LINE_COMMENT.sub("", stripped)
    normalized = _BLOCK_COMMENT.sub("", normalized)
    no_strings = _STRING_LITERAL.sub("''", normalized)

    # Layer 4 — must start with a read clause
    if not _READ_START.match(no_strings):
        raise ValueError(
            "Cypher validation failed: query must begin with "
            "MATCH, OPTIONAL MATCH, WITH, RETURN, or UNWIND"
        )

    # Layer 5 — write DML/DDL keywords
    m = _WRITE_KEYWORD.search(no_strings)
    if m:
        raise ValueError(
            f"Cypher validation failed: disallowed write keyword '{m.group(0).upper()}'"
        )

    # Layer 6 — write-capable CALL procedures
    if _WRITE_PROCEDURE.search(no_strings):
        raise ValueError(
            "Cypher validation failed: CALL to a write-capable procedure is not allowed"
        )

    # Layer 7 — explicit LIMIT required
    if not _LIMIT_CLAUSE.search(no_strings):
        raise ValueError(
            "Cypher validation failed: query must include a LIMIT clause"
        )


def _node_to_dict(node: Any) -> dict[str, Any]:
    if node is None:
        return {}
    if hasattr(node, "items"):
        return dict(node.items())
    if isinstance(node, dict):
        return node
    return {"value": str(node)}


def records_to_rows(records: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        row: dict[str, Any] = {}
        for key in record.keys():
            value = record[key]
            if hasattr(value, "items"):
                row[key] = _node_to_dict(value)
            elif isinstance(value, list):
                row[key] = [
                    _node_to_dict(item) if hasattr(item, "items") else item for item in value
                ]
            else:
                row[key] = value
        rows.append(row)
    return rows


def extract_uuids(text: str) -> list[str]:
    """Return unique UUIDs from text in order of appearance."""
    return list(dict.fromkeys(match.group(0) for match in _UUID_PATTERN.finditer(text)))


def extract_entity_ids(text: str) -> list[str]:
    """Return unique instruction/payment business IDs (sequence or legacy UUID)."""
    return list(dict.fromkeys(match.group(1) for match in _ENTITY_ID_PATTERN.finditer(text)))


def extract_event_id(row: dict[str, Any]) -> str | None:
    if row.get("event_id"):
        return str(row["event_id"])
    for value in row.values():
        if isinstance(value, dict) and value.get("event_id"):
            return str(value["event_id"])
    return None


def row_summary(row: dict[str, Any]) -> str:
    event_id = extract_event_id(row)
    if event_id:
        for key, value in row.items():
            if isinstance(value, dict) and value.get("event_id") == event_id:
                parts = [
                    value.get("action"),
                    value.get("severity"),
                    value.get("message"),
                    value.get("timestamp"),
                ]
                return " · ".join(str(p) for p in parts if p)
    return " · ".join(f"{k}={v}" for k, v in row.items() if v is not None)[:500]
