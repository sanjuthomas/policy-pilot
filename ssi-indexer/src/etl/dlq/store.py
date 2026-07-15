from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from pymongo import ASCENDING, ReturnDocument

from etl.config import settings
from etl.dlq.models import DlqStatus, FailureClass, PipelineKind


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DlqStore:
    """Durable quarantine store — scheduler and consumers use only this Mongo DB."""

    def __init__(self) -> None:
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None
        self._col: AsyncIOMotorCollection | None = None

    @property
    def enabled(self) -> bool:
        return bool(settings.dlq_mongodb_uri.strip())

    async def connect(self) -> None:
        if not self.enabled:
            return
        self._client = AsyncIOMotorClient(settings.dlq_mongodb_uri)
        self._db = self._client[settings.dlq_mongodb_database]
        self._col = self._db[settings.dlq_mongodb_collection]
        await self._col.create_index(
            [("status", ASCENDING), ("next_attempt_at", ASCENDING)],
            name="status_next_attempt",
        )
        await self._col.create_index(
            [("kafka.topic", ASCENDING), ("kafka.partition", ASCENDING), ("kafka.offset", ASCENDING)],
            name="kafka_coords",
            unique=True,
        )
        await self._col.create_index([("pipeline_kind", ASCENDING), ("event_id", ASCENDING)])
        await self._col.create_index([("status", ASCENDING), ("created_at", ASCENDING)])

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._db = None
        self._col = None

    async def ping(self) -> bool:
        if self._client is None:
            return False
        try:
            await self._client.admin.command("ping")
            return True
        except Exception:
            return False

    def _require(self) -> AsyncIOMotorCollection:
        if self._col is None:
            raise RuntimeError("DLQ store is not connected")
        return self._col

    async def insert_failure(
        self,
        *,
        pipeline_kind: PipelineKind,
        consumer_name: str,
        topic: str,
        partition: int,
        offset: int,
        consumer_group: str,
        payload: dict[str, Any],
        event_id: str | None,
        entity_id: str | None,
        failure_class: FailureClass,
        error_message: str,
        stage: str,
        realtime_attempts: int,
        status: DlqStatus | None = None,
    ) -> str:
        col = self._require()
        now = _utc_now()
        initial_status = (status or DlqStatus.PENDING).value
        doc = {
            "pipeline_kind": str(pipeline_kind),
            "consumer_name": consumer_name,
            "kafka": {
                "topic": topic,
                "partition": partition,
                "offset": offset,
                "consumer_group": consumer_group,
            },
            "payload": payload,
            "event_id": event_id,
            "entity_id": entity_id,
            "failure_class": str(failure_class),
            "error_message": error_message[:4000],
            "stage": stage,
            "status": initial_status,
            "attempts": 0,
            "realtime_attempts": realtime_attempts,
            "max_attempts": settings.dlq_scheduler_max_attempts,
            "next_attempt_at": now,
            "locked_by": None,
            "lock_until": None,
            "created_at": now,
            "updated_at": now,
            "processed_at": None,
            "last_error": error_message[:4000],
            "audit": [
                {
                    "at": now,
                    "action": "quarantined",
                    "detail": f"{failure_class}: {error_message[:500]}",
                }
            ],
        }
        try:
            result = await col.insert_one(doc)
            return str(result.inserted_id)
        except Exception:
            # Idempotent reclaim if same kafka coords already quarantined.
            existing = await col.find_one(
                {
                    "kafka.topic": topic,
                    "kafka.partition": partition,
                    "kafka.offset": offset,
                }
            )
            if existing is not None:
                return str(existing["_id"])
            raise

    async def claim_next(self, *, worker_id: str) -> dict[str, Any] | None:
        col = self._require()
        now = _utc_now()
        lock_until = now + timedelta(seconds=settings.dlq_lock_ttl_seconds)
        doc = await col.find_one_and_update(
            {
                "status": {"$in": [DlqStatus.PENDING.value, DlqStatus.PROCESSING.value]},
                "next_attempt_at": {"$lte": now},
                "$or": [
                    {"lock_until": None},
                    {"lock_until": {"$lte": now}},
                ],
            },
            {
                "$set": {
                    "status": DlqStatus.PROCESSING.value,
                    "locked_by": worker_id,
                    "lock_until": lock_until,
                    "updated_at": now,
                },
                "$inc": {"attempts": 1},
                "$push": {
                    "audit": {
                        "at": now,
                        "action": "claimed",
                        "detail": f"worker={worker_id}",
                    }
                },
            },
            sort=[("next_attempt_at", ASCENDING), ("created_at", ASCENDING)],
            return_document=ReturnDocument.AFTER,
        )
        return doc

    async def mark_processed(self, doc_id: Any) -> None:
        col = self._require()
        now = _utc_now()
        await col.update_one(
            {"_id": doc_id},
            {
                "$set": {
                    "status": DlqStatus.PROCESSED.value,
                    "processed_at": now,
                    "updated_at": now,
                    "locked_by": None,
                    "lock_until": None,
                    "last_error": None,
                },
                "$push": {"audit": {"at": now, "action": "processed", "detail": "replay ok"}},
            },
        )

    async def mark_retry_or_exhausted(
        self,
        doc: dict[str, Any],
        *,
        error_message: str,
    ) -> str:
        col = self._require()
        now = _utc_now()
        attempts = int(doc.get("attempts") or 0)
        max_attempts = int(doc.get("max_attempts") or settings.dlq_scheduler_max_attempts)
        if attempts >= max_attempts:
            status = DlqStatus.EXHAUSTED.value
            next_at = now
        else:
            status = DlqStatus.PENDING.value
            delay = settings.dlq_scheduler_backoff_seconds * (2 ** max(attempts - 1, 0))
            delay = min(delay, settings.dlq_scheduler_max_backoff_seconds)
            next_at = now + timedelta(seconds=delay)

        await col.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "status": status,
                    "next_attempt_at": next_at,
                    "updated_at": now,
                    "locked_by": None,
                    "lock_until": None,
                    "last_error": error_message[:4000],
                },
                "$push": {
                    "audit": {
                        "at": now,
                        "action": "exhausted" if status == DlqStatus.EXHAUSTED.value else "retry_scheduled",
                        "detail": error_message[:500],
                    }
                },
            },
        )
        return status

    async def reset_entries(
        self,
        *,
        statuses: list[str] | None = None,
        ids: list[str] | None = None,
        reason: str = "manual_reset",
    ) -> int:
        col = self._require()
        now = _utc_now()
        query: dict[str, Any] = {}
        if ids:
            query["_id"] = {"$in": [ObjectId(i) for i in ids]}
        else:
            query["status"] = {
                "$in": statuses
                or [DlqStatus.EXHAUSTED.value, DlqStatus.PENDING.value, DlqStatus.PROCESSING.value]
            }

        result = await col.update_many(
            query,
            {
                "$set": {
                    "status": DlqStatus.PENDING.value,
                    "attempts": 0,
                    "next_attempt_at": now,
                    "locked_by": None,
                    "lock_until": None,
                    "updated_at": now,
                    "last_error": None,
                },
                "$push": {
                    "audit": {
                        "at": now,
                        "action": "manual_reset",
                        "detail": reason,
                    }
                },
            },
        )
        return int(result.modified_count)

    async def list_entries(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        col = self._require()
        query: dict[str, Any] = {}
        if status:
            query["status"] = status
        cursor = (
            col.find(query)
            .sort([("created_at", -1)])
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        for doc in docs:
            doc["id"] = str(doc.pop("_id"))
            # Keep payload available but mark size for UI.
            payload = doc.get("payload")
            doc["payload_keys"] = sorted(payload.keys()) if isinstance(payload, dict) else []
        return docs

    async def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        col = self._require()
        doc = await col.find_one({"_id": ObjectId(entry_id)})
        if doc is None:
            return None
        doc["id"] = str(doc.pop("_id"))
        return doc

    async def stats(self) -> dict[str, Any]:
        if self._col is None:
            return {
                "enabled": self.enabled,
                "connected": False,
                "by_status": {},
                "depth": 0,
                "oldest_pending_age_seconds": None,
            }
        col = self._col
        pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
        rows = await col.aggregate(pipeline).to_list(length=20)
        by_status = {str(r["_id"]): int(r["count"]) for r in rows}
        active = (
            by_status.get(DlqStatus.PENDING.value, 0)
            + by_status.get(DlqStatus.PROCESSING.value, 0)
            + by_status.get(DlqStatus.EXHAUSTED.value, 0)
        )
        oldest = await col.find_one(
            {"status": {"$in": [DlqStatus.PENDING.value, DlqStatus.EXHAUSTED.value]}},
            sort=[("created_at", ASCENDING)],
        )
        age = None
        if oldest and oldest.get("created_at"):
            created = oldest["created_at"]
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            age = max(0, int((_utc_now() - created).total_seconds()))
        return {
            "enabled": True,
            "connected": True,
            "by_status": by_status,
            "depth": active,
            "oldest_pending_age_seconds": age,
            "database": settings.dlq_mongodb_database,
            "collection": settings.dlq_mongodb_collection,
        }
