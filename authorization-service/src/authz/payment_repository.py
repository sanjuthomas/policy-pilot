from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from authz.config import settings
from authz.models import PaymentRecord


class PaymentNotFoundError(Exception):
    pass


class PaymentRepository:
    def __init__(self) -> None:
        self._client: AsyncIOMotorClient | None = None
        self._collection: AsyncIOMotorCollection | None = None

    async def connect(self) -> None:
        self._client = AsyncIOMotorClient(settings.mongodb_uri)
        db = self._client[settings.mongodb_database]
        self._collection = db[settings.mongodb_collection]

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            self._collection = None

    async def get_payment(self, payment_id: str) -> PaymentRecord:
        if self._collection is None:
            raise RuntimeError("payment repository not connected")
        doc = await self._collection.find_one({"payment_id": payment_id})
        if doc is None:
            raise PaymentNotFoundError(f"payment {payment_id} not found")
        return PaymentRecord.from_mongo(doc)
