#!/usr/bin/env python3
"""Wait until OPA has compiled lifecycle policies and can evaluate decisions."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

OPA_URL = os.environ.get("OPA_URL", "http://opa:8181").rstrip("/")
OPA_WAIT_TIMEOUT = int(os.environ.get("OPA_WAIT_TIMEOUT", "60"))
MIN_POLICY_COUNT = int(os.environ.get("MIN_POLICY_COUNT", "11"))

_CREATE_SMOKE_INPUT = {
    "action": "CREATE",
    "subject": {
        "user_id": "mo-100",
        "title": "Analyst",
        "roles": ["INSTRUCTION_CREATOR"],
        "groups": ["MIDDLE_OFFICE"],
    },
    "instruction": {
        "status": "DRAFT",
        "type": "SINGLE_USE",
        "owning_lob": "FICC",
        "effective_date": "2026-07-04T00:00:00Z",
        "end_date": "2027-07-04T00:00:00Z",
        "created_by": {"user_id": "mo-100", "title": "Analyst"},
    },
    "account": {"owning_lob": "FICC"},
}


def _post_json(path: str, payload: dict) -> dict:
    url = f"{OPA_URL}{path}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode())


def _get_json(path: str) -> dict:
    url = f"{OPA_URL}{path}"
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode())


def opa_is_healthy() -> bool:
    try:
        with urllib.request.urlopen(f"{OPA_URL}/health", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def policy_count() -> int:
    payload = _get_json("/v1/policies")
    result = payload.get("result", [])
    if not isinstance(result, list):
        return 0
    return len(result)


def create_smoke_allows() -> bool:
    payload = _post_json(
        "/v1/data/instruction/lifecycle/allow",
        {"input": _CREATE_SMOKE_INPUT},
    )
    return payload.get("result") is True


def policies_ready() -> tuple[bool, str]:
    count = policy_count()
    if count < MIN_POLICY_COUNT:
        return False, f"expected at least {MIN_POLICY_COUNT} policies, found {count}"

    if not create_smoke_allows():
        return False, "instruction CREATE smoke evaluation did not allow"

    return True, f"{count} policies loaded and CREATE smoke passed"


def main() -> None:
    deadline = time.monotonic() + OPA_WAIT_TIMEOUT
    last_reason = "OPA not reachable"

    while time.monotonic() < deadline:
        if not opa_is_healthy():
            time.sleep(1)
            continue

        try:
            ready, reason = policies_ready()
            last_reason = reason
            if ready:
                print(f"OPA policies ready at {OPA_URL}: {reason}")
                return
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_reason = str(exc)

        time.sleep(1)

    raise SystemExit(
        f"OPA policies not ready at {OPA_URL} within {OPA_WAIT_TIMEOUT}s: {last_reason}"
    )


if __name__ == "__main__":
    main()
