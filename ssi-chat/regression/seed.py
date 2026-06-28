#!/usr/bin/env python3
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from regression.auth_helpers import admin_auth_headers
from regression.models import SeedConfig, SeedStep

logger = logging.getLogger(__name__)


def _post_action(
    client: httpx.Client,
    harness_url: str,
    step: SeedStep,
    *,
    auth_headers: dict[str, str],
) -> dict[str, Any]:
    base = harness_url.rstrip("/")
    action = step.action

    if action == "run-policy-scenario":
        response = client.post(
            f"{base}/api/actions/run-policy-scenario",
            headers=auth_headers,
            timeout=300.0,
        )
    elif action == "run-payment-policy-scenario":
        response = client.post(
            f"{base}/api/actions/run-payment-policy-scenario",
            headers=auth_headers,
            timeout=300.0,
        )
    elif action in {
        "create-instructions",
        "submit-instructions",
        "approve-instructions",
        "reject-instructions",
        "suspend-instructions",
        "reactivate-instructions",
        "create-payments",
        "submit-payments",
        "approve-payments",
        "reject-payments",
    }:
        count = step.count or 1
        response = client.post(
            f"{base}/api/actions/{action}",
            json={"count": count},
            headers=auth_headers,
            timeout=300.0,
        )
    else:
        raise ValueError(f"unknown seed action: {action}")

    response.raise_for_status()
    payload = response.json()
    logger.info(
        "seed %s -> ok=%s succeeded=%s failed=%s",
        action,
        payload.get("ok"),
        payload.get("succeeded"),
        payload.get("failed"),
    )
    return payload


def run_seed(harness_url: str, config: SeedConfig) -> None:
    with httpx.Client(timeout=60.0) as client:
        auth_headers = admin_auth_headers(client, harness_url)
        for step in config.steps:
            _post_action(client, harness_url, step, auth_headers=auth_headers)


def fetch_harness_status(harness_url: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        auth_headers = admin_auth_headers(client, harness_url)
        response = client.get(
            f"{harness_url.rstrip('/')}/api/status",
            headers=auth_headers,
        )
        response.raise_for_status()
        return response.json()


def fetch_qdrant_points(qdrant_url: str, collection: str) -> int:
    with httpx.Client(timeout=15.0) as client:
        response = client.get(f"{qdrant_url.rstrip('/')}/collections/{collection}")
        if response.status_code == 404:
            return 0
        response.raise_for_status()
        result = response.json().get("result") or {}
        return int(result.get("points_count") or 0)


def wait_for_index(
    *,
    harness_url: str,
    qdrant_url: str,
    qdrant_collection: str,
    min_security_events: int,
    min_qdrant_points: int,
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_status: dict[str, Any] = {}

    while time.monotonic() < deadline:
        last_status = fetch_harness_status(harness_url)
        events = int(last_status.get("security_event_count") or 0)
        payment_events = int(last_status.get("payment_security_event_count") or 0)
        total_events = max(events, 0) + max(payment_events, 0)
        points = fetch_qdrant_points(qdrant_url, qdrant_collection)

        logger.info(
            "index wait: security_events=%s payment_events=%s qdrant_points=%s",
            events,
            payment_events,
            points,
        )

        if total_events >= min_security_events and points >= min_qdrant_points:
            return last_status

        time.sleep(poll_interval_seconds)

    raise TimeoutError(
        "timed out waiting for ETL index "
        f"(need events>={min_security_events}, qdrant_points>={min_qdrant_points}); "
        f"last status={last_status}"
    )


def fetch_context(
    *,
    harness_url: str,
    ilm_url: str,
    payment_url: str,
) -> dict[str, str]:
    context: dict[str, str] = {}

    with httpx.Client(timeout=30.0) as client:
        auth_headers = admin_auth_headers(client, harness_url)
        instructions_response = client.get(
            f"{ilm_url.rstrip('/')}/api/ui/instructions",
            params={"limit": 500},
            headers=auth_headers,
        )
        instructions_response.raise_for_status()
        instructions_payload = instructions_response.json()
        instructions = (
            instructions_payload
            if isinstance(instructions_payload, list)
            else instructions_payload.get("instructions", [])
        )

        payments_response = client.get(
            f"{payment_url.rstrip('/')}/api/ui/payments",
            params={"limit": 500},
            headers=auth_headers,
        )
        payments_response.raise_for_status()
        payments_payload = payments_response.json()
        payments = (
            payments_payload
            if isinstance(payments_payload, list)
            else payments_payload.get("payments", [])
        )

    approved_instructions = [
        item
        for item in instructions
        if item.get("status") in {"STANDING", "SINGLE_USE"}
        and item.get("approved_by")
    ]
    pending_instructions = [
        item for item in instructions if item.get("status") == "PENDING"
    ]
    ficc_standing = [
        item
        for item in approved_instructions
        if item.get("owning_lob") == "FICC" and item.get("status") == "STANDING"
    ]
    approved_payments = [
        item for item in payments if item.get("status") == "APPROVED"
    ]
    submitted_payments = [
        item for item in payments if item.get("status") == "SUBMITTED"
    ]

    if approved_instructions:
        context["approved_instruction_id"] = approved_instructions[0]["instruction_id"]
    if ficc_standing:
        context["ficc_standing_instruction_id"] = ficc_standing[0]["instruction_id"]
    if pending_instructions:
        context["pending_instruction_id"] = pending_instructions[0]["instruction_id"]
    if approved_payments:
        payment = approved_payments[0]
        context["approved_payment_id"] = payment["payment_id"]
        context["approved_payment_instruction_id"] = payment.get("instruction_id", "")
    if submitted_payments:
        context["submitted_payment_id"] = submitted_payments[0]["payment_id"]
    if payments:
        context["any_payment_id"] = payments[0]["payment_id"]
    if instructions:
        context["any_instruction_id"] = instructions[0]["instruction_id"]

    return context
