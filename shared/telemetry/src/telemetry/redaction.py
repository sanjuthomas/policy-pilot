from __future__ import annotations

import json
import re
from typing import Any

_REDACTED = "[REDACTED]"

# Exact dict keys that should always be redacted.
_EXACT_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "client_name",
    }
)

# Dict keys whose values must never appear in logs (substring match, case-insensitive).
_SENSITIVE_KEY_FRAGMENTS: tuple[str, ...] = (
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "account",
    "amount",
    "creditor",
    "debtor",
    "bic",
    "iban",
    "swift",
    "given_name",
    "family_name",
    "display_name",
    "client_name",
    "supervisor_name",
    "approver_name",
    "creator_name",
    "actor_name",
    "rejector_name",
    "identification",
)

# YAML / plain-text profile lines (search_text sent to Vertex embed API).
_SENSITIVE_FIELD_LINE = re.compile(
    r"(?m)^(?P<key>(?:amount|creditor|debtor|account|bic|iban|swift|given_name|"
    r"family_name|display_name|identification|client_name|supervisor|approver|"
    r"creator|actor|rejector)[^\n:]*):\s*[^\n]*",
    re.IGNORECASE,
)

# Long digit sequences likely to be account or routing numbers.
_ACCOUNT_NUMBER = re.compile(r"\b\d{8,}\b")

# Western-style person names in free text (e.g. echoed client names in JSON values).
_PROPER_NAME = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")

# JSON / key-value amount patterns in unstructured text.
_AMOUNT_PATTERN = re.compile(
    r'(?i)(["\']?(?:amount|payment_amount|value)["\']?\s*[:=]\s*)'
    r'(?:["\'])?[\d,]+(?:\.\d+)?(?:["\'])?'
)


def _key_is_sensitive(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    if lowered in _EXACT_SENSITIVE_KEYS:
        return True
    return any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS)


def redact_value(value: Any) -> Any:
    """Return a log-safe copy of *value* with sensitive fields removed."""
    if isinstance(value, dict):
        return redact_payload(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_string(value)
    return value


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if _key_is_sensitive(key):
            redacted[key] = _REDACTED
        elif isinstance(value, dict):
            redacted[key] = redact_payload(value)
        elif isinstance(value, list):
            redacted[key] = [redact_value(item) for item in value]
        elif isinstance(value, str):
            redacted[key] = redact_string(value)
        else:
            redacted[key] = value
    return redacted


def redact_string(text: str, *, max_len: int = 4000) -> str:
    if not text:
        return text
    scrubbed = _SENSITIVE_FIELD_LINE.sub(
        lambda match: f"{match.group('key')}: {_REDACTED}",
        text,
    )
    scrubbed = _AMOUNT_PATTERN.sub(r"\1" + _REDACTED, scrubbed)
    scrubbed = _PROPER_NAME.sub(_REDACTED, scrubbed)
    scrubbed = _ACCOUNT_NUMBER.sub(_REDACTED, scrubbed)
    if len(scrubbed) > max_len:
        return scrubbed[:max_len] + "…"
    return scrubbed


def redact_json_body(body: bytes | str | None, *, max_len: int = 4000) -> str:
    if body is None:
        return ""
    raw = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
    if not raw.strip():
        return ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return redact_string(raw, max_len=max_len)
    safe = redact_value(parsed)
    encoded = json.dumps(safe, default=str, ensure_ascii=False)
    if len(encoded) > max_len:
        return encoded[:max_len] + "…"
    return encoded


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    sensitive = {"authorization", "cookie", "set-cookie", "x-api-key"}
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in sensitive:
            redacted[key] = _REDACTED
        else:
            redacted[key] = value
    return redacted
