"""
DLQ live-stack integration cases (manual Neo4j outage flow).

Cases (env-gated with RUN_DLQ_INTEGRATION=1):

1. **quarantine_when_neo4j_down** — stop Neo4j, seed instructions via harness,
   wait until DLQ depth > 0 and chat integrity banner would show.
2. **drain_after_neo4j_recovery** — start Neo4j, Retry Now until depth == 0,
   assert banner cleared / no unresolved entries.

Optional knobs:
  INDEXER_URL, HARNESS_URL, DLQ_IT_ADMIN_USER, DLQ_IT_ADMIN_PASSWORD,
  DLQ_IT_SEED_COUNT (default 2), DLQ_IT_QUARANTINE_TIMEOUT_SECONDS (default 420),
  DLQ_IT_DRAIN_TIMEOUT_SECONDS (default 420), DLQ_IT_COMPOSE_FILE
"""

from __future__ import annotations

import os

import httpx
import pytest

from .conftest import (
    INDEXER_URL,
    admin_headers,
    dlq_depth,
    dlq_stats,
    index_integrity,
    require_integration,
    retry_now,
    seed_instructions,
    start_neo4j_healthy,
    stop_neo4j,
    wait_until,
)

pytestmark = pytest.mark.integration


def _seed_count() -> int:
    return max(1, int(os.environ.get("DLQ_IT_SEED_COUNT", "2")))


def _quarantine_timeout() -> float:
    return float(os.environ.get("DLQ_IT_QUARANTINE_TIMEOUT_SECONDS", "420"))


def _drain_timeout() -> float:
    return float(os.environ.get("DLQ_IT_DRAIN_TIMEOUT_SECONDS", "420"))


@pytest.fixture(scope="module")
def neo4j_outage_session(http_client: httpx.Client):
    """Stop Neo4j once for the module; always restore afterward."""
    require_integration()
    was_healthy = True
    try:
        stop_neo4j()
        was_healthy = False
        yield http_client
    finally:
        # Always try to leave the stack usable for other local work.
        try:
            start_neo4j_healthy()
            was_healthy = True
        except Exception:  # noqa: BLE001
            if not was_healthy:
                raise


def test_01_quarantine_when_neo4j_down(neo4j_outage_session: httpx.Client) -> None:
    """Neo4j down + seed ⇒ messages land in Mongo DLQ (depth > 0)."""
    client = neo4j_outage_session
    before = dlq_depth(client)
    seed_instructions(client, count=_seed_count())

    wait_until(
        lambda: dlq_depth(client) > before,
        timeout_seconds=_quarantine_timeout(),
        interval_seconds=5.0,
        description="DLQ depth increase after seed with Neo4j down",
    )

    integrity = index_integrity(client)
    assert integrity.get("show_banner") is True
    assert int((integrity.get("dlq") or {}).get("depth") or 0) > before
    # Offsets should still advance (quarantine-before-commit), so lag stays low
    # once CDC has caught up — allow some transient lag while Kafka Connect publishes.
    wait_until(
        lambda: int(index_integrity(client).get("kafka_lag_total") or 0) < 50,
        timeout_seconds=120,
        interval_seconds=5.0,
        description="kafka lag settles after quarantine commits",
    )


def test_02_drain_after_neo4j_recovery(neo4j_outage_session: httpx.Client) -> None:
    """Neo4j up + Retry Now ⇒ unresolved DLQ empties."""
    client = neo4j_outage_session
    depth_before_recovery = dlq_depth(client)
    if depth_before_recovery <= 0:
        pytest.skip("no DLQ entries to drain (prior quarantine step may have been skipped)")

    start_neo4j_healthy()
    headers = admin_headers(client, INDEXER_URL)

    def _drain_progress() -> bool:
        depth = dlq_depth(client)
        if depth <= 0:
            return True
        retry_now(client, headers)
        return dlq_depth(client) <= 0

    wait_until(
        _drain_progress,
        timeout_seconds=_drain_timeout(),
        interval_seconds=3.0,
        description="DLQ drain via Retry Now after Neo4j recovery",
    )

    integrity = index_integrity(client)
    assert int((integrity.get("dlq") or {}).get("depth") or 0) == 0
    assert integrity.get("show_banner") is False

    stats = dlq_stats(client, headers)
    assert int(stats.get("depth") or 0) == 0
    by = stats.get("by_status") or {}
    assert int(by.get("pending") or 0) == 0
    assert int(by.get("processing") or 0) == 0
    assert int(by.get("exhausted") or 0) == 0

    entries = client.get(
        f"{INDEXER_URL}/api/dlq/entries",
        headers=headers,
        params={"active_only": "true", "limit": 50},
        timeout=30.0,
    )
    entries.raise_for_status()
    assert entries.json().get("count") == 0
