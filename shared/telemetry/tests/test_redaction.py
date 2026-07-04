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


def test_redact_string_scrubs_session_token_in_url() -> None:
    message = (
        "HTTP Request: GET http://zitadel-proxy/v2/sessions/380233132256788490"
        "?sessionToken=YzyFnENFkW6EAcFZjzNdQqB_CS9dvaONbyUA3gftt05t9ZDIlMxpt4OUhznLHrPj118A21fTG5SqnA "
        '"HTTP/1.1 200 OK"'
    )
    redacted = redact_string(message)
    assert "YzyFnENFkW6EAcFZjzNdQqB" not in redacted
    assert "380233132256788490" not in redacted
    assert "sessionToken=[REDACTED]" in redacted
    assert "/v2/sessions/[REDACTED]" in redacted


def test_redact_string_scrubs_session_token_in_url_legacy_example() -> None:
    message = (
        'HTTP Request: GET http://zitadel-proxy/v2/sessions/380308458517299202'
        '?sessionToken=fyFCkrWbD_lZ89mi9qoM975QJJNgwD2cJ2C7qJm87MM "HTTP/1.1 200 OK"'
    )
    redacted = redact_string(message)
    assert "fyFCkrWbD" not in redacted
    assert "380308458517299202" not in redacted
    assert "sessionToken=[REDACTED]" in redacted
    assert "/v2/sessions/[REDACTED]" in redacted


def test_redact_string_scrubs_bearer_token() -> None:
    redacted = redact_string("Authorization failed for Bearer eyJhbGciOiJIUzI1NiJ9.abc")
    assert "eyJhbGci" not in redacted
    assert "Bearer [REDACTED]" in redacted
