"""Post-process chat answers into structured presentation formats.

Formatters are tried in order; the first match wins. Unmatched text is returned unchanged
so new rules can be added incrementally without breaking existing answers.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from chat_application.formatting.common import format_markdown_table

# Gemini often emits key: value or **key:** value; older paths use key=value.
# Keys must start at a token boundary so Title-case labels (Title:, Roles:) are
# not mid-matched as "itle" / "oles".
_KV_FIELD_RE = re.compile(
    r"(?:(?<=^)|(?<=\s)|(?<=,)|(?<=\*\*))(?:\*\*)?"
    r"([a-z][a-z0-9_]*)"
    r"(?:\*\*)?\s*[:=]\s*"
)
_NUMBERED_LINE_RE = re.compile(r"^\s*\d+\.\s+(.+)$")
_MARKDOWN_TABLE_SEPARATOR_RE = re.compile(r"^\|?\s*[-:| ]+\|")
_MARKDOWN_EMPHASIS_RE = re.compile(r"\*+")

INSTRUCTION_FIELD_ORDER = [
    "instruction_id",
    "owning_lob",
    "status",
    "instruction_type",
    "currency",
    "wire_scope",
    "creditor",
    "creditor_name",
    "creditor_account",
    "creator",
    "creator_display",
    "approver",
    "approver_display",
    "approved_at",
    "effective",
    "effective_date",
    "end",
    "end_date",
    "rejected_by",
    "rejected_at",
    "rejection_reason",
    "event_id",
    "timestamp",
    "action",
    "actor",
    "actor_display",
    "severity",
    "outcome",
    "message",
]

PAYMENT_FIELD_ORDER = [
    "payment_id",
    "instruction_id",
    "status",
    "amount",
    "currency",
    "value_date",
    "owning_lob",
    "creator",
    "creator_display",
    "approver",
    "approver_display",
    "approved_at",
    "event_id",
    "timestamp",
    "action",
    "actor",
    "actor_display",
    "severity",
    "outcome",
]

FIELD_LABELS: dict[str, str] = {
    "instruction_id": "Instruction ID",
    "payment_id": "Payment ID",
    "event_id": "Event ID",
    "owning_lob": "LOB",
    "wire_scope": "Wire Scope",
    "instruction_type": "Type",
    "value_date": "Value Date",
    "approved_at": "Approved At",
    "effective_date": "Effective",
    "end_date": "End",
    "rejected_at": "Rejected At",
    "rejection_reason": "Rejection Reason",
    "actor_display": "Actor",
    "creator_display": "Creator",
    "approver_display": "Approver",
    "creditor_name": "Creditor",
    "creditor_account": "Creditor Account",
}

DOMAIN_FIELD_ORDERS = [INSTRUCTION_FIELD_ORDER, PAYMENT_FIELD_ORDER]


def format_chat_response(text: str) -> str:
    """Apply the first matching formatter, or return the original text."""
    if not text or not text.strip():
        return text

    for formatter in _FORMATTERS:
        formatted = formatter(text)
        if formatted is not None:
            return formatted
    return text


def _clean_field_value(value: str) -> str:
    cleaned = value.rstrip().removesuffix(",").strip()
    cleaned = _MARKDOWN_EMPHASIS_RE.sub("", cleaned).strip()
    return cleaned


def parse_key_value_record(text: str) -> dict[str, str]:
    """Parse comma-separated key=value / key: value segments from a record line.

    Accepts Gemini's markdown-bold variants (``**instruction_id:** …``) as well as
    the older ``instruction_id=…`` shape used by deterministic formatters.
    """
    matches = list(_KV_FIELD_RE.finditer(text))
    if not matches:
        return {}

    record: dict[str, str] = {}
    for index, match in enumerate(matches):
        key = match.group(1)
        value_start = match.end()
        value_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = _clean_field_value(text[value_start:value_end])
        if value:
            record[key] = value
    return record


def _merge_continuation_fields(
    records: list[dict[str, str]],
    parsed: dict[str, str],
) -> bool:
    """Merge a short trailing key:value line into the previous multi-field record."""
    if not records or len(parsed) != 1:
        return False
    records[-1].update(parsed)
    return True


def humanize_field_name(key: str) -> str:
    return FIELD_LABELS.get(key, key.replace("_", " ").title())


def column_order(keys: set[str]) -> list[str]:
    for preferred in DOMAIN_FIELD_ORDERS:
        ordered = [key for key in preferred if key in keys]
        if len(ordered) >= 2:
            remaining = sorted(key for key in keys if key not in ordered)
            return ordered + remaining
    return sorted(keys)


def records_to_markdown_table(records: list[dict[str, str]]) -> str:
    """Render records as a markdown table.

    Multi-record answers stay wide (one row per entity). A single record becomes a
    vertical Field/Value card — matching payment-detail UX and avoiding a one-row
    mega-table that users downvote.
    """
    if len(records) == 1:
        return _single_record_to_vertical_table(records[0])

    keys = {key for record in records for key in record}
    key_order = column_order(keys)
    headers = [humanize_field_name(key) for key in key_order]
    rows = [[record.get(key, "—") for key in key_order] for record in records]
    return format_markdown_table(headers, rows)


def _single_record_to_vertical_table(record: dict[str, str]) -> str:
    rows = [
        [humanize_field_name(key), record.get(key, "—") or "—"]
        for key in column_order(set(record))
    ]
    return format_markdown_table(["Field", "Value"], rows)


def has_markdown_table(text: str) -> bool:
    lines = text.splitlines()
    for index in range(len(lines) - 1):
        if "|" in lines[index] and _MARKDOWN_TABLE_SEPARATOR_RE.match(lines[index + 1]):
            return True
    return False


def _join_sections(*parts: str) -> str:
    return "\n".join(part for part in parts if part).rstrip()


def _format_record_block(
    intro: str,
    records: list[dict[str, str]],
    footer: str,
) -> str | None:
    if not records:
        return None

    min_keys = min(len(record) for record in records)
    if min_keys < 2:
        return None
    if len(records) == 1 and min_keys < 3:
        return None

    table = records_to_markdown_table(records)
    return _join_sections(intro, table, footer)


def _split_numbered_key_value_records(text: str) -> tuple[str, list[dict[str, str]], str]:
    intro_lines: list[str] = []
    footer_lines: list[str] = []
    records: list[dict[str, str]] = []
    seen_record = False

    for line in text.splitlines():
        match = _NUMBERED_LINE_RE.match(line)
        if match:
            parsed = parse_key_value_record(match.group(1))
            if len(parsed) < 2:
                if not seen_record:
                    intro_lines.append(line)
                else:
                    footer_lines.append(line)
                continue
            seen_record = True
            records.append(parsed)
            continue

        stripped = line.strip()
        if seen_record and stripped:
            parsed = parse_key_value_record(stripped)
            if _merge_continuation_fields(records, parsed):
                continue

        if not seen_record:
            intro_lines.append(line)
        else:
            footer_lines.append(line)

    return "\n".join(intro_lines).strip(), records, "\n".join(footer_lines).strip()


def _split_plain_key_value_lines(text: str) -> tuple[str, list[dict[str, str]], str]:
    intro_lines: list[str] = []
    footer_lines: list[str] = []
    records: list[dict[str, str]] = []
    seen_record = False
    # Gemini sometimes emits one snake_case field per line for a single entity.
    pending_vertical: dict[str, str] = {}

    def _flush_vertical() -> None:
        nonlocal pending_vertical, seen_record
        if len(pending_vertical) >= 3:
            seen_record = True
            records.append(pending_vertical)
        elif pending_vertical:
            # Too sparse to treat as a record — keep as prose.
            for key, value in pending_vertical.items():
                target = footer_lines if seen_record else intro_lines
                target.append(f"{key}: {value}")
        pending_vertical = {}

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if pending_vertical:
                _flush_vertical()
            if not seen_record:
                intro_lines.append(line)
            else:
                footer_lines.append(line)
            continue

        parsed = parse_key_value_record(stripped)
        if len(parsed) >= 2:
            _flush_vertical()
            seen_record = True
            records.append(parsed)
            continue

        if len(parsed) == 1:
            # Continuation of a multi-field inline record, or start/continue a
            # vertical one-field-per-line card.
            if records and _merge_continuation_fields(records, parsed):
                continue
            pending_vertical.update(parsed)
            continue

        _flush_vertical()
        if not seen_record:
            intro_lines.append(line)
        else:
            footer_lines.append(line)

    _flush_vertical()
    return "\n".join(intro_lines).strip(), records, "\n".join(footer_lines).strip()


def _try_numbered_key_value_list(text: str) -> str | None:
    if has_markdown_table(text):
        return None

    intro, records, footer = _split_numbered_key_value_records(text)
    if len(records) < 1:
        return None
    return _format_record_block(intro, records, footer)


def _try_plain_key_value_lines(text: str) -> str | None:
    if has_markdown_table(text):
        return None

    intro, records, footer = _split_plain_key_value_lines(text)
    # Single multi-field records (e.g. "show me instruction X") become a one-row table.
    if len(records) < 1:
        return None
    return _format_record_block(intro, records, footer)


_FORMATTERS: list[Callable[[str], str | None]] = [
    _try_numbered_key_value_list,
    _try_plain_key_value_lines,
]
