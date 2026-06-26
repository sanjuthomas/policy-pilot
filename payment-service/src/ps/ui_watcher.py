import asyncio
import logging
from typing import Any

from ps.config import settings
from ps.database import get_db
from ps.ui_broadcaster import PaymentBroadcaster

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 2.0


class PaymentWatcher:
    """Watches the payments collection for new/updated documents via MongoDB change stream,
    falling back to polling if the replica set change stream is unavailable."""

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()

    @property
    def _col(self):
        return get_db()[settings.mongodb_collection]

    async def watch(self, broadcaster: PaymentBroadcaster) -> None:
        try:
            await self._watch_change_stream(broadcaster)
        except Exception as exc:
            logger.warning(
                "payment change stream unavailable (%s); falling back to polling every %ss",
                exc,
                _POLL_INTERVAL,
            )
            await self._poll_loop(broadcaster)

    async def _watch_change_stream(self, broadcaster: PaymentBroadcaster) -> None:
        pipeline = [{"$match": {"operationType": {"$in": ["insert", "replace", "update"]}}}]
        async with self._col.watch(pipeline, full_document="updateLookup") as stream:
            logger.info("listening on MongoDB change stream for payments")
            async for change in stream:
                document = change.get("fullDocument")
                if not document:
                    continue
                document.pop("_id", None)
                await broadcaster.publish(document)

    async def _poll_loop(self, broadcaster: PaymentBroadcaster) -> None:
        while True:
            cursor = self._col.find({}).sort("updated_at", -1).limit(20)
            async for doc in cursor:
                payment_id = doc.get("payment_id", "")
                sig = f"{payment_id}:{doc.get('updated_at', '')}"
                if sig in self._seen_ids:
                    continue
                self._seen_ids.add(sig)
                doc.pop("_id", None)
                await broadcaster.publish(doc)
            await asyncio.sleep(_POLL_INTERVAL)
