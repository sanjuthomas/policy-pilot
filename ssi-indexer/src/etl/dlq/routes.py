from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from etl.dlq.pause import pause_registry
from etl.dlq.scheduler import DlqScheduler
from etl.dlq.store import DlqStore


class DlqResetRequest(BaseModel):
    ids: list[str] | None = None
    statuses: list[str] | None = Field(
        default=None,
        description="Statuses to reset when ids omitted (default exhausted+pending+processing)",
    )
    reason: str = "ops_ui_retry_now"


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
        limit: int = 50,
        skip: int = 0,
    ) -> dict[str, Any]:
        limit = max(1, min(limit, 200))
        skip = max(0, skip)
        entries = await store.list_entries(status=status, limit=limit, skip=skip)
        for entry in entries:
            entry.pop("payload", None)
        return {"count": len(entries), "entries": entries}

    @router.get("/entries/{entry_id}")
    async def dlq_entry(entry_id: str) -> dict[str, Any]:
        doc = await store.get_entry(entry_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="DLQ entry not found")
        return doc

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
