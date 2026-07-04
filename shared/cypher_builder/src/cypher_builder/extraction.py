from __future__ import annotations

import json
import re
from typing import Any

from cypher_builder.models import GraphQueryPlan

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

GRAPH_QUERY_EXTRACTION_SYSTEM = """You translate financial security operations questions into a JSON query plan.
Return ONLY valid JSON matching this schema — no markdown, no explanation.

Schema:
{
  "intent": one of [
    "alert_count_today",
    "instruction_approval",
    "instruction_approver_via_payment",
    "instruction_aggregate",
    "instruction_compliance",
    "instruction_inventory",
    "instruction_lookup",
    "max_payments_per_instruction",
    "payment_aggregate",
    "payment_approval",
    "payments_for_instruction",
    "security_event_aggregate",
    "security_event_rank"
  ],
  "operation": "count" | "list" | "sum" | "rank" | null,
  "time_window": "today" | "week" | "all" | null,
  "domain": "payments" | "instructions" | "all" | null,
  "instruction_id": string | null,
  "payment_id": string | null,
  "user_id": string | null,
  "status": string | null,
  "instruction_type": "SINGLE_USE" | "STANDING" | null,
  "owning_lob": "FICC" | "FX" | "DESK" | null,
  "severity": "ALERT" | null,
  "denial": boolean | null,
  "use_value_date": boolean,
  "compliance_pattern": "mutual" | "self" | "subordinate" | "duplicate_routes" | null,
  "confidence": number between 0 and 1
}

Rules:
- Pick the single best intent family; use optional fields for variation.
- Extract IDs exactly as written (sequence IDs like 20260101-FICC-I-1 or UUIDs).
- user_id values look like mo-001, ficc-003, comp-001, pay-001, etc.
- For approval audit (who approved, when) use instruction_approval or payment_approval with IDs.
- For total security event counts (all severities) use security_event_aggregate with operation count,
  severity null, denial false — unless the question explicitly asks for alerts/denials only.
- For policy denial alert counts use security_event_aggregate with severity ALERT and denial true.
- For ranking/top user questions use security_event_rank with operation rank.
- For payment totals use payment_aggregate with operation sum; counts use operation count.
- For instruction counts use instruction_aggregate with operation count.
- compliance_pattern only for instruction_compliance intent.
- If the question cannot be mapped, set intent to security_event_aggregate, confidence to 0.1, and leave filters null.
"""


def build_extraction_user_prompt(*, question: str, mode: str) -> str:
    return f"""Search mode: {mode}

Question: {question}

JSON plan:"""


def parse_graph_query_plan(raw: str) -> GraphQueryPlan:
    text = raw.strip()
    if not text:
        raise ValueError("empty extraction response")

    block = _JSON_BLOCK.search(text)
    if block:
        text = block.group(1)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("extraction response is not JSON")

    payload: dict[str, Any] = json.loads(text[start : end + 1])
    return GraphQueryPlan.model_validate(payload)
