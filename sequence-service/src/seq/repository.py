from __future__ import annotations

import logging
from datetime import datetime, timezone

from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from seq.config import settings
from seq.database import get_db

logger = logging.getLogger(__name__)


class SequenceRepositoryError(Exception):
    pass


class SequenceRepository:
    async def connect(self) -> None:
        from seq.database import connect

        await connect()

    async def close(self) -> None:
        from seq.database import close

        await close()

    def _collection(self):
        return get_db()[settings.mongodb_collection]

    async def ensure_indexes(self) -> None:
        await self._collection().create_index("updated_at")

    async def allocate_next(self, counter_key: str) -> int:
        now = datetime.now(timezone.utc)
        try:
            doc = await self._collection().find_one_and_update(
                {"_id": counter_key},
                {
                    "$inc": {"seq": 1},
                    "$set": {"updated_at": now},
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            logger.exception("failed to allocate sequence for counter_key=%s", counter_key)
            raise SequenceRepositoryError("sequence allocation failed") from exc

        if doc is None or "seq" not in doc:
            raise SequenceRepositoryError("sequence allocation returned no counter")

        return int(doc["seq"])
