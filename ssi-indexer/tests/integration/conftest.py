"""Live-stack DLQ integration helpers (skipped unless RUN_DLQ_INTEGRATION=1)."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

INDEXER_URL = os.environ.get("INDEXER_URL", "http://localhost:8090").rstrip("/")
HARNESS_URL = os.environ.get("HARNESS_URL", "http://localhost:8091").rstrip("/")
ADMIN_USER = os.environ.get("DLQ_IT_ADMIN_USER", "admin-001")
ADMIN_PASSWORD = os.environ.get("DLQ_IT_ADMIN_PASSWORD", "Password1!")
COMPOSE_FILE = os.environ.get(
    "DLQ_IT_COMPOSE_FILE",
    str(REPO_ROOT / "docker-compose.yml"),
)


def integration_enabled() -> bool:
    return os.environ.get("RUN_DLQ_INTEGRATION") == "1"


def require_integration() -> None:
    if not integration_enabled():
        pytest.skip("set RUN_DLQ_INTEGRATION=1 to run live Neo4j/Kafka/Mongo DLQ tests")


def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["docker", "compose", "-f", COMPOSE_FILE, *args]
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def wait_until(
    predicate,
    *,
    timeout_seconds: float,
    interval_seconds: float = 2.0,
    description: str = "condition",
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(interval_seconds)
    detail = f" timed out after {timeout_seconds:.0f}s"
    if last_error is not None:
        detail += f" (last error: {last_error})"
    raise AssertionError(f"{description}{detail}")


def neo4j_status() -> str:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Status}}{{if .State.Health}}/{{.State.Health.Status}}{{end}}",
            "neo4j",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return (result.stdout or "").strip() or "missing"


def stop_neo4j() -> None:
    compose("stop", "neo4j")
    wait_until(
        lambda: neo4j_status().split("/", 1)[0] in {"exited", "created"},
        timeout_seconds=60,
        description="neo4j stop",
    )


def start_neo4j_healthy() -> None:
    compose("start", "neo4j")
    wait_until(
        lambda: neo4j_status() == "running/healthy",
        timeout_seconds=120,
        description="neo4j healthy",
    )


def admin_headers(client: httpx.Client, base_url: str) -> dict[str, str]:
    response = client.post(
        f"{base_url}/api/auth/login",
        json={"user_id": ADMIN_USER, "password": ADMIN_PASSWORD},
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    return {
        "Authorization": f"Bearer {payload['session_token']}",
        "X-Session-Id": payload["session_id"],
    }


def index_integrity(client: httpx.Client) -> dict:
    response = client.get(f"{INDEXER_URL}/api/index-integrity", timeout=30.0)
    response.raise_for_status()
    return response.json()


def dlq_depth(client: httpx.Client) -> int:
    return int((index_integrity(client).get("dlq") or {}).get("depth") or 0)


def dlq_stats(client: httpx.Client, headers: dict[str, str]) -> dict:
    response = client.get(f"{INDEXER_URL}/api/dlq/stats", headers=headers, timeout=30.0)
    response.raise_for_status()
    return response.json()


def retry_now(client: httpx.Client, headers: dict[str, str]) -> dict:
    response = client.post(
        f"{INDEXER_URL}/api/dlq/retry-now",
        headers=headers,
        json={"reason": "dlq_integration_test"},
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()


def seed_instructions(client: httpx.Client, *, count: int = 2) -> None:
    headers = admin_headers(client, HARNESS_URL)
    response = client.post(
        f"{HARNESS_URL}/api/actions/create-instructions",
        headers=headers,
        json={"count": count},
        timeout=180.0,
    )
    response.raise_for_status()
    body = response.json()
    # Harness wraps differently depending on route; accept either shape.
    ok = body.get("ok")
    if ok is False:
        raise AssertionError(f"create-instructions failed: {body}")
    if isinstance(body.get("succeeded"), int) and body["succeeded"] < 1:
        raise AssertionError(f"create-instructions created nothing: {body}")


@pytest.fixture(scope="module")
def http_client():
    require_integration()
    with httpx.Client(timeout=60.0) as client:
        # Fail fast if stack is not up.
        client.get(f"{INDEXER_URL}/health").raise_for_status()
        client.get(f"{HARNESS_URL}/health").raise_for_status()
        yield client
