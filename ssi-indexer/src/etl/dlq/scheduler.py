from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

from etl.config import settings
from etl.dlq.metrics import record_dlq_event
from etl.dlq.models import PipelineKind
from etl.dlq.pause import pause_registry
from etl.dlq.store import DlqStore

logger = logging.getLogger(__name__)


class DlqScheduler:
    """Replays quarantined payloads through registered pipeline handlers."""

    def __init__(self, store: DlqStore) -> None:
        self._store = store
        self._task: asyncio.Task | None = None
        self._worker_id = f"{socket.gethostname()}:{id(self)}"

    async def start(self) -> None:
        if not self._store.enabled:
            logger.info("DLQ scheduler disabled (no DLQ_MONGODB_URI)")
            return
        self._task = asyncio.create_task(self._run())
        logger.info(
            "DLQ scheduler started interval=%ss worker=%s",
            settings.dlq_scheduler_interval_seconds,
            self._worker_id,
        )

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        try:
            while True:
                try:
                    await self.drain_once()
                except Exception:
                    logger.exception("DLQ scheduler cycle failed")
                await asyncio.sleep(settings.dlq_scheduler_interval_seconds)
        except asyncio.CancelledError:
            raise

    async def drain_once(self, *, max_items: int | None = None) -> int:
        limit = max_items or settings.dlq_scheduler_batch_size
        processed = 0
        for _ in range(limit):
            doc = await self._store.claim_next(worker_id=self._worker_id)
            if doc is None:
                break
            await self._replay(doc)
            processed += 1
        return processed

    async def _replay(self, doc: dict[str, Any]) -> None:
        kind = PipelineKind(str(doc["pipeline_kind"]))
        handler = pause_registry.get_replay(kind)
        if handler is None:
            await self._store.mark_retry_or_exhausted(
                doc,
                error_message=f"no replay handler registered for {kind}",
            )
            record_dlq_event("etl.dlq.replay_failed", pipeline=str(kind), reason="no_handler")
            return

        payload = doc.get("payload")
        if not isinstance(payload, dict):
            await self._store.mark_retry_or_exhausted(
                doc,
                error_message="DLQ payload missing or invalid",
            )
            record_dlq_event("etl.dlq.replay_failed", pipeline=str(kind), reason="bad_payload")
            return

        try:
            await handler(payload)  # type: ignore[misc]
            await self._store.mark_processed(doc["_id"])
            record_dlq_event("etl.dlq.replay_ok", pipeline=str(kind))
            logger.info(
                "DLQ replay ok id=%s pipeline=%s event_id=%s",
                doc.get("_id"),
                kind,
                doc.get("event_id"),
            )
        except Exception as exc:  # noqa: BLE001
            status = await self._store.mark_retry_or_exhausted(doc, error_message=str(exc))
            record_dlq_event(
                "etl.dlq.replay_failed",
                pipeline=str(kind),
                status=status,
            )
            logger.exception(
                "DLQ replay failed id=%s pipeline=%s status=%s",
                doc.get("_id"),
                kind,
                status,
            )
