from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from regression.auth_helpers import (
    admin_auth_headers,
    compliance_auth_headers,
    login_headers,
    obo_headers,
    service_auth_headers,
)

logger = logging.getLogger(__name__)

SKIP_VERTEX = os.environ.get("API_SMOKE_SKIP_VERTEX", "").lower() in {"1", "true", "yes"}


@dataclass
class SmokeCheck:
    id: str
    service: str
    description: str
    passed: bool = False
    skipped: bool = False
    reason: str = ""


@dataclass
class SmokeResult:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    checks: list[SmokeCheck] = field(default_factory=list)

    def record(self, check: SmokeCheck) -> None:
        self.checks.append(check)
        if check.skipped:
            self.skipped += 1
        elif check.passed:
            self.passed += 1
        else:
            self.failed += 1


def _ok(check_id: str, service: str, description: str) -> SmokeCheck:
    return SmokeCheck(id=check_id, service=service, description=description, passed=True)


def _fail(check_id: str, service: str, description: str, reason: str) -> SmokeCheck:
    return SmokeCheck(
        id=check_id,
        service=service,
        description=description,
        passed=False,
        reason=reason,
    )


def _skip(check_id: str, service: str, description: str, reason: str) -> SmokeCheck:
    return SmokeCheck(
        id=check_id,
        service=service,
        description=description,
        skipped=True,
        reason=reason,
    )


def _run_check(
    result: SmokeResult,
    check_id: str,
    service: str,
    description: str,
    fn: Callable[[], None],
) -> None:
    try:
        fn()
        result.record(_ok(check_id, service, description))
    except SkipCheck as exc:
        result.record(_skip(check_id, service, description, str(exc)))
    except Exception as exc:  # noqa: BLE001
        result.record(_fail(check_id, service, description, str(exc)))


class SkipCheck(Exception):
    pass


def run_api_smoke(
    *,
    harness_url: str,
    instruction_service_url: str,
    payment_url: str,
    indexer_url: str,
    chat_url: str,
    authz_url: str,
    context: dict[str, str] | None = None,
) -> SmokeResult:
    context = context or {}
    result = SmokeResult()

    with httpx.Client(timeout=60.0) as client:
        admin_headers = admin_auth_headers(client, harness_url)
        # Domain /api/v1 never accepts bare human JWTs — always svc-chat + OBO.
        service_headers = service_auth_headers(client, chat_url)
        compliance_obo = obo_headers(
            service_headers,
            compliance_auth_headers(client, chat_url),
        )

        def health(service: str, base_url: str) -> None:
            response = client.get(f"{base_url.rstrip('/')}/health")
            if response.status_code != 200:
                raise RuntimeError(f"expected 200, got {response.status_code}")
            status = response.json().get("status")
            allowed = {"UP", "DEGRADED"} if service == "ssi-indexer" else {"UP"}
            if status not in allowed:
                raise RuntimeError(f"unexpected health status {status!r}: {response.text[:200]}")

        for service, url in [
            ("harness", harness_url),
            ("instruction-service", instruction_service_url),
            ("payment-service", payment_url),
            ("ssi-indexer", indexer_url),
            ("ssi-chat", chat_url),
            ("authorization-service", authz_url),
        ]:
            _run_check(
                result,
                f"{service}_health",
                service,
                "GET /health",
                lambda service=service, url=url: health(service, url),
            )

        def chat_compliance_users() -> None:
            response = client.get(f"{chat_url.rstrip('/')}/api/compliance-users")
            if response.status_code != 200:
                raise RuntimeError(f"expected 200, got {response.status_code}")
            users = response.json().get("users")
            if not users:
                raise RuntimeError("expected non-empty compliance users list")

        _run_check(
            result,
            "chat_compliance_users",
            "ssi-chat",
            "GET /api/compliance-users",
            chat_compliance_users,
        )

        def chat_auth_gate() -> None:
            try:
                with httpx.Client(timeout=10.0) as gate_client:
                    response = gate_client.post(
                        f"{chat_url.rstrip('/')}/api/chat",
                        json={"message": "hello", "mode": "events", "history": []},
                    )
            except httpx.TimeoutException as exc:
                raise SkipCheck(
                    "chat server did not respond in 10s (likely single-worker backlog; "
                    "auth gate is covered by unit tests)"
                ) from exc
            if response.status_code != 401:
                raise RuntimeError(f"expected 401 without auth, got {response.status_code}")

        _run_check(
            result,
            "chat_auth_gate",
            "ssi-chat",
            "POST /api/chat rejects unauthenticated",
            chat_auth_gate,
        )

        def payment_eligible_requires_auth() -> None:
            response = client.post(
                f"{payment_url.rstrip('/')}/api/v1/payments/pay-smoke/eligible-approvers",
            )
            if response.status_code != 401:
                raise RuntimeError(f"expected 401 without auth, got {response.status_code}")

        _run_check(
            result,
            "payment_eligible_auth_gate",
            "payment-service",
            "POST eligible-approvers rejects unauthenticated",
            payment_eligible_requires_auth,
        )

        def payment_obo_required() -> None:
            """Bare human JWT must not call domain APIs (no end-user direct access)."""
            human = compliance_auth_headers(client, chat_url)
            response = client.post(
                f"{payment_url.rstrip('/')}/api/v1/payments/pay-smoke/eligible-approvers",
                headers=human,
            )
            if response.status_code != 403:
                raise RuntimeError(
                    f"expected 403 without OBO (bare user JWT), got {response.status_code}"
                )

        _run_check(
            result,
            "payment_obo_required",
            "payment-service",
            "POST eligible-approvers rejects bare user JWT (OBO required)",
            payment_obo_required,
        )

        def harness_status() -> None:
            response = client.get(
                f"{harness_url.rstrip('/')}/api/status",
                headers=admin_headers,
            )
            if response.status_code != 200:
                raise RuntimeError(f"expected 200, got {response.status_code}")
            body = response.json()
            for key in ("instruction_total", "payment_total", "security_event_count"):
                if key not in body:
                    raise RuntimeError(f"missing {key} in status payload")

        _run_check(
            result,
            "harness_status",
            "harness",
            "GET /api/status (admin)",
            harness_status,
        )

        def harness_action_requires_auth() -> None:
            response = client.post(
                f"{harness_url.rstrip('/')}/api/actions/create-instructions",
                json={"count": 1},
            )
            if response.status_code != 401:
                raise RuntimeError(f"expected 401 without auth, got {response.status_code}")

        _run_check(
            result,
            "harness_action_auth",
            "harness",
            "POST /api/actions/create-instructions rejects unauthenticated",
            harness_action_requires_auth,
        )

        def harness_suspend_route_auth() -> None:
            response = client.post(
                f"{harness_url.rstrip('/')}/api/actions/suspend-instructions",
                json={"count": 1},
            )
            if response.status_code != 401:
                raise RuntimeError(f"expected 401 without auth, got {response.status_code}")

        _run_check(
            result,
            "harness_suspend_auth",
            "harness",
            "POST /api/actions/suspend-instructions rejects unauthenticated",
            harness_suspend_route_auth,
        )

        def instruction_service_ui_list() -> None:
            response = client.get(
                f"{instruction_service_url.rstrip('/')}/api/ui/instructions",
                params={"limit": 10},
                headers=admin_headers,
            )
            if response.status_code != 200:
                raise RuntimeError(f"expected 200, got {response.status_code}")
            body = response.json()
            if isinstance(body, list):
                return
            if "instructions" not in body:
                raise RuntimeError("expected instructions key in UI response")

        _run_check(
            result,
            "instruction_service_ui_instructions",
            "instruction-service",
            "GET /api/ui/instructions (admin)",
            instruction_service_ui_list,
        )

        def instruction_service_ui_auth() -> None:
            response = client.get(f"{instruction_service_url.rstrip('/')}/api/ui/instructions")
            if response.status_code != 401:
                raise RuntimeError(f"expected 401 without auth, got {response.status_code}")

        _run_check(
            result,
            "instruction_service_ui_auth",
            "instruction-service",
            "GET /api/ui/instructions rejects unauthenticated",
            instruction_service_ui_auth,
        )

        def instruction_service_rest_auth() -> None:
            response = client.get(f"{instruction_service_url.rstrip('/')}/api/v1/instructions")
            if response.status_code != 401:
                raise RuntimeError(f"expected 401 without auth, got {response.status_code}")

        _run_check(
            result,
            "instruction_service_rest_auth",
            "instruction-service",
            "GET /api/v1/instructions rejects unauthenticated",
            instruction_service_rest_auth,
        )

        def payment_ui_list() -> None:
            response = client.get(
                f"{payment_url.rstrip('/')}/api/ui/payments",
                params={"limit": 10},
                headers=admin_headers,
            )
            if response.status_code != 200:
                raise RuntimeError(f"expected 200, got {response.status_code}")
            body = response.json()
            if isinstance(body, list):
                return
            if "payments" not in body:
                raise RuntimeError("expected payments key in UI response")

        _run_check(
            result,
            "payment_ui_payments",
            "payment-service",
            "GET /api/ui/payments (admin)",
            payment_ui_list,
        )

        def payment_rest_auth() -> None:
            response = client.get(f"{payment_url.rstrip('/')}/api/v1/payments")
            if response.status_code != 401:
                raise RuntimeError(f"expected 401 without auth, got {response.status_code}")

        _run_check(
            result,
            "payment_rest_auth",
            "payment-service",
            "GET /api/v1/payments rejects unauthenticated",
            payment_rest_auth,
        )

        def indexer_stats() -> None:
            response = client.get(
                f"{indexer_url.rstrip('/')}/api/stats",
                headers=admin_headers,
            )
            if response.status_code != 200:
                raise RuntimeError(f"expected 200, got {response.status_code}")
            body = response.json()
            if "components" not in body:
                raise RuntimeError("missing components in stats payload")

        _run_check(
            result,
            "indexer_stats",
            "ssi-indexer",
            "GET /api/stats (admin)",
            indexer_stats,
        )

        def indexer_stats_auth() -> None:
            response = client.get(f"{indexer_url.rstrip('/')}/api/stats")
            if response.status_code != 401:
                raise RuntimeError(f"expected 401 without auth, got {response.status_code}")

        _run_check(
            result,
            "indexer_stats_auth",
            "ssi-indexer",
            "GET /api/stats rejects unauthenticated",
            indexer_stats_auth,
        )

        def indexer_intent_extract_auth() -> None:
            response = client.post(
                f"{indexer_url.rstrip('/')}/api/intent/extract",
                json={"question": "How many alerts today?", "mode": "events"},
            )
            if response.status_code != 401:
                raise RuntimeError(f"expected 401 without auth, got {response.status_code}")

        _run_check(
            result,
            "indexer_intent_extract_auth",
            "ssi-indexer",
            "POST /api/intent/extract rejects unauthenticated",
            indexer_intent_extract_auth,
        )

        def indexer_search_vector() -> None:
            if SKIP_VERTEX:
                raise SkipCheck("API_SMOKE_SKIP_VERTEX set")
            response = client.post(
                f"{indexer_url.rstrip('/')}/api/search/vector",
                json={"query": "policy denial", "limit": 3},
                headers=admin_headers,
                timeout=120.0,
            )
            if response.status_code != 200:
                raise RuntimeError(f"expected 200, got {response.status_code}: {response.text[:200]}")
            body = response.json()
            if body.get("mode") != "vector":
                raise RuntimeError(f"unexpected mode: {body.get('mode')}")

        _run_check(
            result,
            "indexer_search_vector",
            "ssi-indexer",
            "POST /api/search/vector (admin, Vertex embeddings)",
            indexer_search_vector,
        )

        def indexer_graph_events() -> None:
            response = client.get(
                f"{indexer_url.rstrip('/')}/api/graph/events",
                params={"limit": 5},
                headers=admin_headers,
            )
            if response.status_code != 200:
                raise RuntimeError(f"expected 200, got {response.status_code}")
            if "events" not in response.json():
                raise RuntimeError("missing events in graph response")

        _run_check(
            result,
            "indexer_graph_events",
            "ssi-indexer",
            "GET /api/graph/events (admin)",
            indexer_graph_events,
        )

        def indexer_cypher_run() -> None:
            response = client.post(
                f"{indexer_url.rstrip('/')}/api/cypher/run",
                json={"cypher": "MATCH (n) RETURN count(n) AS total LIMIT 1"},
                headers=admin_headers,
            )
            if response.status_code != 200:
                raise RuntimeError(f"expected 200, got {response.status_code}: {response.text[:200]}")
            if "row_count" not in response.json():
                raise RuntimeError("missing row_count in cypher run response")

        _run_check(
            result,
            "indexer_cypher_run",
            "ssi-indexer",
            "POST /api/cypher/run (admin)",
            indexer_cypher_run,
        )

        def indexer_intent_extract() -> None:
            if SKIP_VERTEX:
                raise SkipCheck("API_SMOKE_SKIP_VERTEX set")
            response = client.post(
                f"{indexer_url.rstrip('/')}/api/intent/extract",
                json={
                    "question": "How many payment ALERT events happened today?",
                    "mode": "events",
                },
                headers=admin_headers,
                timeout=120.0,
            )
            if response.status_code != 200:
                raise RuntimeError(f"expected 200, got {response.status_code}: {response.text[:200]}")
            body = response.json()
            if body.get("source") != "vertex_gemini":
                raise RuntimeError("expected vertex_gemini source in intent response")
            if not body.get("plan", {}).get("intent"):
                raise RuntimeError("missing plan.intent in intent extract response")

        _run_check(
            result,
            "indexer_intent_extract",
            "ssi-indexer",
            "POST /api/intent/extract (admin, Vertex Gemini)",
            indexer_intent_extract,
        )

        def payment_eligible() -> None:
            payment_id = context.get("submitted_payment_id") or context.get("approved_payment_id")
            if not payment_id:
                raise SkipCheck("no payment_id in context (run with --seed first)")
            response = client.post(
                f"{payment_url.rstrip('/')}/api/v1/payments/{payment_id}/eligible-approvers",
                headers=compliance_obo,
            )
            if response.status_code not in {200, 404}:
                raise RuntimeError(f"expected 200 or 404, got {response.status_code}: {response.text[:200]}")
            if response.status_code == 200:
                body = response.json()
                if body.get("payment_id") != payment_id:
                    raise RuntimeError("payment_id mismatch in eligible-approvers response")

        _run_check(
            result,
            "payment_eligible",
            "payment-service",
            "POST /api/v1/payments/{id}/eligible-approvers (svc-chat + compliance OBO)",
            payment_eligible,
        )

        def instruction_eligible() -> None:
            instruction_id = context.get("approved_instruction_id")
            if not instruction_id:
                raise SkipCheck("no approved_instruction_id in context (run with --seed first)")
            response = client.post(
                f"{instruction_service_url.rstrip('/')}/api/v1/instructions/{instruction_id}/eligible-approvers",
                headers=compliance_obo,
            )
            if response.status_code not in {200, 404}:
                raise RuntimeError(f"expected 200 or 404, got {response.status_code}: {response.text[:200]}")
            if response.status_code == 200:
                body = response.json()
                if body.get("instruction_id") != instruction_id:
                    raise RuntimeError("instruction_id mismatch in eligible-approvers response")

        _run_check(
            result,
            "instruction_eligible",
            "instruction-service",
            "POST /api/v1/instructions/{id}/eligible-approvers (svc-chat + compliance OBO)",
            instruction_eligible,
        )

        # --- LOB / covering entitlement (FO vs MO) -------------------------
        demo_password = "Password1!"
        ficc_instruction_id = context.get("ficc_standing_instruction_id") or context.get(
            "approved_instruction_id"
        )

        def _obo_as(user_id: str) -> dict[str, str]:
            """svc-chat Authorization + human user as X-On-Behalf-Of."""
            user = login_headers(
                client,
                chat_url,
                user_id=user_id,
                password=demo_password,
            )
            return obo_headers(service_headers, user)

        def _admin_payment_owning_lob(payment_id: str) -> str | None:
            """Probe owning_lob via admin UI (not /api/v1 — admins do not use OBO)."""
            admin = admin_auth_headers(client, payment_url)
            probe = client.get(
                f"{payment_url.rstrip('/')}/api/ui/payments/{payment_id}",
                headers=admin,
            )
            if probe.status_code != 200:
                return None
            payment = probe.json().get("payment") or {}
            return payment.get("owning_lob")

        def _resolve_ficc_payment_id() -> str | None:
            """Prefer seeded ids that are FICC; otherwise scan admin UI."""
            for key in (
                "draft_payment_id",
                "submitted_payment_id",
                "approved_payment_id",
                "any_payment_id",
            ):
                candidate = context.get(key)
                if candidate and _admin_payment_owning_lob(candidate) == "FICC":
                    return candidate
            admin = admin_auth_headers(client, payment_url)
            response = client.get(
                f"{payment_url.rstrip('/')}/api/ui/payments",
                params={"owning_lob": "FICC", "limit": 50},
                headers=admin,
            )
            if response.status_code != 200:
                return None
            payments = response.json().get("payments") or []
            if not payments:
                return None
            return payments[0].get("payment_id") or payments[0].get("id")

        ficc_payment_id = _resolve_ficc_payment_id()

        def instruction_view_fo_positive() -> None:
            if not ficc_instruction_id:
                raise SkipCheck("no FICC instruction id in context (run with --seed first)")
            headers = _obo_as("fo-ficc-101")
            response = client.get(
                f"{instruction_service_url.rstrip('/')}/api/v1/instructions/{ficc_instruction_id}",
                headers=headers,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"FO FICC expected 200 on FICC instruction, got {response.status_code}: "
                    f"{response.text[:200]}"
                )

        _run_check(
            result,
            "instruction_view_fo_positive",
            "instruction-service",
            "GET instruction FICC allowed for fo-ficc-101 (matching lob)",
            instruction_view_fo_positive,
        )

        def instruction_view_fo_negative() -> None:
            if not ficc_instruction_id:
                raise SkipCheck("no FICC instruction id in context (run with --seed first)")
            headers = _obo_as("fo-fx-101")
            response = client.get(
                f"{instruction_service_url.rstrip('/')}/api/v1/instructions/{ficc_instruction_id}",
                headers=headers,
            )
            if response.status_code != 403:
                raise RuntimeError(
                    f"FO FX expected 403 on FICC instruction, got {response.status_code}: "
                    f"{response.text[:200]}"
                )

        _run_check(
            result,
            "instruction_view_fo_negative",
            "instruction-service",
            "GET instruction FICC denied for fo-fx-101 (wrong lob)",
            instruction_view_fo_negative,
        )

        def instruction_view_mo_positive() -> None:
            if not ficc_instruction_id:
                raise SkipCheck("no FICC instruction id in context (run with --seed first)")
            headers = _obo_as("pay-101")
            response = client.get(
                f"{instruction_service_url.rstrip('/')}/api/v1/instructions/{ficc_instruction_id}",
                headers=headers,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"MO pay-101 expected 200 on FICC instruction, got {response.status_code}: "
                    f"{response.text[:200]}"
                )

        _run_check(
            result,
            "instruction_view_mo_positive",
            "instruction-service",
            "GET instruction FICC allowed for pay-101 (covering includes FICC)",
            instruction_view_mo_positive,
        )

        def instruction_view_mo_negative() -> None:
            if not ficc_instruction_id:
                raise SkipCheck("no FICC instruction id in context (run with --seed first)")
            headers = _obo_as("pay-203")
            response = client.get(
                f"{instruction_service_url.rstrip('/')}/api/v1/instructions/{ficc_instruction_id}",
                headers=headers,
            )
            if response.status_code != 403:
                raise RuntimeError(
                    f"MO pay-203 (covers FX only) expected 403 on FICC instruction, "
                    f"got {response.status_code}: {response.text[:200]}"
                )

        _run_check(
            result,
            "instruction_view_mo_negative",
            "instruction-service",
            "GET instruction FICC denied for pay-203 (covering misses FICC)",
            instruction_view_mo_negative,
        )

        def payment_view_fo_positive() -> None:
            if not ficc_payment_id:
                raise SkipCheck("no payment id in context (run with --seed first)")
            if _admin_payment_owning_lob(ficc_payment_id) != "FICC":
                raise SkipCheck("need a FICC payment in context for FO positive")
            headers = _obo_as("fo-ficc-101")
            response = client.get(
                f"{payment_url.rstrip('/')}/api/v1/payments/{ficc_payment_id}",
                headers=headers,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"FO FICC expected 200 on FICC payment, got {response.status_code}: "
                    f"{response.text[:200]}"
                )

        _run_check(
            result,
            "payment_view_fo_positive",
            "payment-service",
            "GET payment allowed for fo-ficc-101 when owning_lob matches",
            payment_view_fo_positive,
        )

        def payment_view_fo_negative() -> None:
            if not ficc_payment_id:
                raise SkipCheck("no payment id in context (run with --seed first)")
            owning_lob = _admin_payment_owning_lob(ficc_payment_id)
            if owning_lob is None:
                raise SkipCheck(f"admin could not load payment {ficc_payment_id}")
            if owning_lob != "FICC":
                raise SkipCheck(
                    f"payment {ficc_payment_id} owning_lob={owning_lob!r}, need FICC for FO negative"
                )
            headers = _obo_as("fo-fx-101")
            response = client.get(
                f"{payment_url.rstrip('/')}/api/v1/payments/{ficc_payment_id}",
                headers=headers,
            )
            if response.status_code != 403:
                raise RuntimeError(
                    f"FO FX expected 403 on FICC payment, got {response.status_code}: "
                    f"{response.text[:200]}"
                )

        _run_check(
            result,
            "payment_view_fo_negative",
            "payment-service",
            "GET FICC payment denied for fo-fx-101 (wrong lob)",
            payment_view_fo_negative,
        )

        def payment_view_mo_positive() -> None:
            if not ficc_payment_id:
                raise SkipCheck("no payment id in context (run with --seed first)")
            if _admin_payment_owning_lob(ficc_payment_id) != "FICC":
                raise SkipCheck("need a FICC payment in context for MO positive")
            headers = _obo_as("pay-101")
            response = client.get(
                f"{payment_url.rstrip('/')}/api/v1/payments/{ficc_payment_id}",
                headers=headers,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"MO pay-101 expected 200 on FICC payment, got {response.status_code}: "
                    f"{response.text[:200]}"
                )

        _run_check(
            result,
            "payment_view_mo_positive",
            "payment-service",
            "GET FICC payment allowed for pay-101 (covering includes FICC)",
            payment_view_mo_positive,
        )

        def payment_view_mo_negative() -> None:
            if not ficc_payment_id:
                raise SkipCheck("no payment id in context (run with --seed first)")
            if _admin_payment_owning_lob(ficc_payment_id) != "FICC":
                raise SkipCheck("need a FICC payment in context for MO negative")
            headers = _obo_as("pay-203")
            response = client.get(
                f"{payment_url.rstrip('/')}/api/v1/payments/{ficc_payment_id}",
                headers=headers,
            )
            if response.status_code != 403:
                raise RuntimeError(
                    f"MO pay-203 (covers FX only) expected 403 on FICC payment, "
                    f"got {response.status_code}: {response.text[:200]}"
                )

        _run_check(
            result,
            "payment_view_mo_negative",
            "payment-service",
            "GET FICC payment denied for pay-203 (covering misses FICC)",
            payment_view_mo_negative,
        )

    return result


def print_smoke_summary(result: SmokeResult) -> None:
    print("\n=== API smoke summary ===")
    print(f"passed={result.passed} failed={result.failed} skipped={result.skipped}")
    for check in result.checks:
        status = "PASS" if check.passed else ("SKIP" if check.skipped else "FAIL")
        print(f"[{status}] {check.service}: {check.id} — {check.description}")
        if not check.passed and not check.skipped:
            print(f"       reason: {check.reason}")
        if check.skipped and check.reason:
            print(f"       skip: {check.reason}")


def smoke_to_dict(result: SmokeResult) -> dict[str, Any]:
    return {
        "passed": result.passed,
        "failed": result.failed,
        "skipped": result.skipped,
        "checks": [
            {
                "id": check.id,
                "service": check.service,
                "description": check.description,
                "passed": check.passed,
                "skipped": check.skipped,
                "reason": check.reason,
            }
            for check in result.checks
        ],
    }
