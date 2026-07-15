from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from etl.dlq.pause import pause_registry
from etl.dlq.scheduler import DlqScheduler
from etl.dlq.store import DlqStore


class DlqRetryNowRequest(BaseModel):
    ids: list[str] | None = Field(
        default=None,
        description="Optional subset of DLQ entry ids; omit to act on all active rows",
    )
    reason: str = "ops_ui_retry_now"


class DlqResetRequest(BaseModel):
    ids: list[str] | None = None
    statuses: list[str] | None = Field(
        default=None,
        description=(
            "Statuses to fully reset (attempts=0) when ids omitted. "
            "Prefer POST /dlq/retry-now for Ops UI."
        ),
    )
    reason: str = "manual_reset"


class DlqResumeRequest(BaseModel):
    consumer_name: str | None = Field(
        default=None,
        description="Resume one consumer; omit to clear all pause flags",
    )


def build_dlq_router(store: DlqStore, scheduler: DlqScheduler) -> APIRouter:
    router = APIRouter(prefix="/dlq", tags=["dlq"])

    @router.get("/stats")
    async def dlq_stats() -> dict[str, Any]:
        stats = await store.stats()
        stats["consumers"] = pause_registry.snapshot()
        stats["any_paused"] = pause_registry.any_paused()
        return stats

    @router.get("/entries")
    async def dlq_entries(
        status: str | None = None,
        active_only: bool = True,
        limit: int = 50,
        skip: int = 0,
    ) -> dict[str, Any]:
        """List DLQ rows. Defaults to unresolved rows (excludes processed)."""
        limit = max(1, min(limit, 200))
        skip = max(0, skip)
        entries = await store.list_entries(
            status=status,
            active_only=active_only and status is None,
            limit=limit,
            skip=skip,
        )
        for entry in entries:
            entry.pop("payload", None)
        return {"count": len(entries), "entries": entries, "active_only": active_only and status is None}

    @router.get("/entries/{entry_id}")
    async def dlq_entry(entry_id: str) -> dict[str, Any]:
        doc = await store.get_entry(entry_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="DLQ entry not found")
        return doc

    @router.post("/retry-now")
    async def dlq_retry_now(body: DlqRetryNowRequest) -> dict[str, Any]:
        """Ops: immediately retry active DLQ rows; scheduler still runs until max attempts."""
        if not store.enabled or store._col is None:
            raise HTTPException(status_code=503, detail="DLQ store unavailable")
        prepared = await store.prepare_retry_now(ids=body.ids, reason=body.reason)
        drained = await scheduler.drain_once()
        return {**prepared, "drained": drained}

    @router.post("/reset")
    async def dlq_reset(body: DlqResetRequest) -> dict[str, Any]:
        if not store.enabled or store._col is None:
            raise HTTPException(status_code=503, detail="DLQ store unavailable")
        modified = await store.reset_entries(
            statuses=body.statuses,
            ids=body.ids,
            reason=body.reason,
        )
        drained = await scheduler.drain_once()
        return {"reset": modified, "drained": drained}

    @router.post("/resume-consumers")
    async def resume_consumers(body: DlqResumeRequest) -> dict[str, Any]:
        if body.consumer_name:
            pause_registry.clear_paused(body.consumer_name)
        else:
            for name in list(pause_registry.snapshot()):
                pause_registry.clear_paused(name)
        return {"consumers": pause_registry.snapshot()}

    return router
