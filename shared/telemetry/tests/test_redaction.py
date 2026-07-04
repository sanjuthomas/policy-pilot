from __future__ import annotations

import json

from telemetry.redaction import (
    redact_headers,
    redact_json_body,
    redact_payload,
    redact_string,
    redact_value,
)


def test_redact_payload_masks_sensitive_keys() -> None:
    payload = {
        "instruction_id": "inst-123",
        "amount": 25_000_000,
        "creditor_name": "Acme Bank",
        "creditor_account_id": "1234567890123456",
        "actor": {
            "given_name": "Sarah",
            "family_name": "Chen",
            "user_id": "mo-100",
        },
    }
    redacted = redact_payload(payload)
    assert redacted["instruction_id"] == "inst-123"
    assert redacted["amount"] == "[REDACTED]"
    assert redacted["creditor_name"] == "[REDACTED]"
    assert redacted["creditor_account_id"] == "[REDACTED]"
    assert redacted["actor"]["given_name"] == "[REDACTED]"
    assert redacted["actor"]["user_id"] == "mo-100"


def test_redact_string_masks_profile_lines_and_account_numbers() -> None:
    text = (
        "amount: 1000000.00\n"
        "creditor_name: Example Corp\n"
        "account_id: 1234567890123456\n"
        "instruction_id: abc-123"
    )
    redacted = redact_string(text)
    assert "amount: [REDACTED]" in redacted
    assert "creditor_name: [REDACTED]" in redacted
    assert "account_id: [REDACTED]" in redacted
    assert "instruction_id: abc-123" in redacted


def test_redact_json_body() -> None:
    body = json.dumps(
        {
            "query": "payments over 10M",
            "payment": {"amount": 10_000_000, "currency": "USD"},
        }
    ).encode()
    redacted = redact_json_body(body)
    parsed = json.loads(redacted)
    assert parsed["query"] == "payments over 10M"
    assert parsed["payment"]["amount"] == "[REDACTED]"


def test_redact_headers() -> None:
    headers = {
        "Authorization": "Bearer secret-token",
        "Content-Type": "application/json",
    }
    redacted = redact_headers(headers)
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["Content-Type"] == "application/json"


def test_redact_value_on_non_dict() -> None:
    assert redact_value("amount: 5000") == "amount: [REDACTED]"
