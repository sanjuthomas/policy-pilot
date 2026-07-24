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

    if action in {
        "run-policy-scenario",
        "run-payment-policy-scenario",
        "seed-skill-fixtures",
    }:
        response = client.post(
            f"{base}/api/actions/{action}",
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


def run_seed(harness_url: str, config: SeedConfig) -> dict[str, str]:
    """Run suite-level seed steps; return any context ids they produced."""
    context: dict[str, str] = {}
    with httpx.Client(timeout=60.0) as client:
        auth_headers = admin_auth_headers(client, harness_url)
        for step in config.steps:
            payload = _post_action(client, harness_url, step, auth_headers=auth_headers)
            step_context = payload.get("context") or {}
            if isinstance(step_context, dict):
                context.update(
                    {str(k): str(v) for k, v in step_context.items() if v}
                )
    return context


def skill_fixture_need(requires_context: list[str]) -> str | None:
    """Derive setup-skill-fixture ``need`` from case placeholder requirements."""
    required = set(requires_context)
    if "used_instruction_id" in required:
        return "used_single_use"
    if "suspended_instruction_id" in required:
        return "suspended"
    if "submitted_payment_id" in required:
        return "submitted"
    if "draft_payment_id" in required:
        return "draft"
    if "ficc_standing_instruction_id" in required:
        return "instruction"
    return None


def setup_skill_fixture(harness_url: str, *, need: str) -> dict[str, str]:
    """Create isolated fixture data for one skill case. Raises on failure.

    On failure the exception carries ``partial_context`` so the caller can still
    tear down anything that was created before the error.
    """
    with httpx.Client(timeout=120.0) as client:
        auth_headers = admin_auth_headers(client, harness_url)
        response = client.post(
            f"{harness_url.rstrip('/')}/api/actions/setup-skill-fixture",
            json={"need": need},
            headers=auth_headers,
            timeout=120.0,
        )
        response.raise_for_status()
        payload = response.json()
    context = {
        str(k): str(v) for k, v in (payload.get("context") or {}).items() if v
    }
    logger.info(
        "setup-skill-fixture need=%s -> ok=%s succeeded=%s failed=%s context=%s",
        need,
        payload.get("ok"),
        payload.get("succeeded"),
        payload.get("failed"),
        sorted(context.keys()),
    )
    if not payload.get("ok"):
        logs = payload.get("logs") or []
        err = RuntimeError(
            f"setup-skill-fixture({need}) failed: " + "; ".join(logs[-5:])
        )
        err.partial_context = context  # type: ignore[attr-defined]
        raise err
    return context


def teardown_skill_fixture(harness_url: str, context: dict[str, str]) -> None:
    """Best-effort teardown of fixtures created for one skill case."""
    if not context:
        return
    with httpx.Client(timeout=120.0) as client:
        auth_headers = admin_auth_headers(client, harness_url)
        response = client.post(
            f"{harness_url.rstrip('/')}/api/actions/teardown-skill-fixture",
            json={"context": context},
            headers=auth_headers,
            timeout=120.0,
        )
        response.raise_for_status()
        payload = response.json()
    logger.info(
        "teardown-skill-fixture -> ok=%s succeeded=%s skipped=%s failed=%s",
        payload.get("ok"),
        payload.get("succeeded"),
        payload.get("skipped"),
        payload.get("failed"),
    )


def fetch_harness_status(harness_url: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        auth_headers = admin_auth_headers(client, harness_url)
        response = client.get(
            f"{harness_url.rstrip('/')}/api/status",
            headers=auth_headers,
        )
        response.raise_for_status()
        return response.json()


def fetch_multimodal_document_count(indexer_url: str, auth_headers: dict[str, str]) -> int:
    with httpx.Client(timeout=15.0) as client:
        response = client.get(
            f"{indexer_url.rstrip('/')}/api/stats",
            headers=auth_headers,
        )
        if response.status_code == 404:
            return 0
        response.raise_for_status()
        components = response.json().get("components") or {}
        vector = components.get("multimodal_vector") or {}
        return int(vector.get("documents_count") or 0)


def wait_for_index(
    *,
    harness_url: str,
    indexer_url: str,
    min_security_events: int,
    min_multimodal_documents: int,
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_status: dict[str, Any] = {}

    with httpx.Client(timeout=30.0) as client:
        auth_headers = admin_auth_headers(client, harness_url)

        while time.monotonic() < deadline:
            last_status = fetch_harness_status(harness_url)
            events = int(last_status.get("security_event_count") or 0)
            payment_events = int(last_status.get("payment_security_event_count") or 0)
            total_events = max(events, 0) + max(payment_events, 0)
            documents = fetch_multimodal_document_count(indexer_url, auth_headers)

            logger.info(
                "index wait: security_events=%s payment_events=%s multimodal_documents=%s",
                events,
                payment_events,
                documents,
            )

            if total_events >= min_security_events and documents >= min_multimodal_documents:
                return last_status

            time.sleep(poll_interval_seconds)

    raise TimeoutError(
        "timed out waiting for ETL index "
        f"(need events>={min_security_events}, multimodal_documents>={min_multimodal_documents}); "
        f"last status={last_status}"
    )


def fetch_context(
    *,
    harness_url: str,
    instruction_service_url: str,
    payment_url: str,
) -> dict[str, str]:
    context: dict[str, str] = {}

    with httpx.Client(timeout=30.0) as client:
        auth_headers = admin_auth_headers(client, harness_url)
        instructions_response = client.get(
            f"{instruction_service_url.rstrip('/')}/api/ui/instructions",
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
        if item.get("status") == "APPROVED"
        and item.get("approved_by")
    ]
    pending_instructions = [
        item for item in instructions if item.get("status") == "SUBMITTED"
    ]
    ficc_standing = [
        item
        for item in approved_instructions
        if item.get("owning_lob") == "FICC" and item.get("instruction_type") == "STANDING"
    ]
    approved_payments = [
        item for item in payments if item.get("status") == "APPROVED"
    ]
    submitted_payments = [
        item for item in payments if item.get("status") == "SUBMITTED"
    ]
    draft_payments = [item for item in payments if item.get("status") == "DRAFT"]
    ficc_drafts = [
        item for item in draft_payments if item.get("owning_lob") == "FICC"
    ]

    if approved_instructions:
        context["approved_instruction_id"] = approved_instructions[0]["instruction_id"]
    if ficc_standing:
        context["ficc_standing_instruction_id"] = ficc_standing[0]["instruction_id"]
    else:
        # Fallback when seed RNG left no APPROVED FICC STANDING (e.g. only
        # SINGLE_USE FICC). VIEW goldens still need a FICC id the persona can see.
        ficc_approved = [
            item for item in approved_instructions if item.get("owning_lob") == "FICC"
        ]
        if ficc_approved:
            context["ficc_standing_instruction_id"] = ficc_approved[0]["instruction_id"]
    if pending_instructions:
        context["pending_instruction_id"] = pending_instructions[0]["instruction_id"]
    if approved_payments:
        payment = approved_payments[0]
        context["approved_payment_id"] = payment["payment_id"]
        context["approved_payment_instruction_id"] = payment.get("instruction_id", "")
    if submitted_payments:
        context["submitted_payment_id"] = submitted_payments[0]["payment_id"]
    if ficc_drafts:
        context["draft_payment_id"] = ficc_drafts[0]["payment_id"]
    elif draft_payments:
        context["draft_payment_id"] = draft_payments[0]["payment_id"]
    if payments:
        context["any_payment_id"] = payments[0]["payment_id"]
    if instructions:
        context["any_instruction_id"] = instructions[0]["instruction_id"]

    return context
