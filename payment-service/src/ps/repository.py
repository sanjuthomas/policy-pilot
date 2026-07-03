from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClientSession
from pymongo.errors import DuplicateKeyError, OperationFailure

from ps.config import settings
from ps.constants import PAYMENT_CURRENT_OUT
from ps.database import get_db
from ps.models.enums import PaymentStatus
from ps.models.payment import Payment
from ps.storage import (
    VersionedPayment,
    document_to_versioned_payment,
    versioned_payment_to_document,
)


class PaymentNotFoundError(Exception):
    pass


class ConcurrentModificationError(Exception):
    """Raised when optimistic locking detects a concurrent write."""


class PaymentRepository:
    @property
    def _col(self):
        return get_db()[settings.mongodb_collection]

    @staticmethod
    def _payment_id_filter(payment_id: str) -> dict[str, Any]:
        return {"_id": {"$regex": f"^{re.escape(payment_id)}\\|\\d+$"}}

    async def insert_initial(
        self,
        payment: Payment,
        *,
        session: AsyncIOMotorClientSession | None = None,
    ) -> VersionedPayment:
        now = datetime.utcnow()
        document = versioned_payment_to_document(
            payment,
            version_number=1,
            valid_in=now,
        )
        await self._col.insert_one(document, session=session)
        return document_to_versioned_payment(document)

    async def append_version(
        self,
        payment: Payment,
        *,
        session: AsyncIOMotorClientSession | None = None,
    ) -> VersionedPayment:
        now = datetime.utcnow()
        current = await self._col.find_one(
            {
                **self._payment_id_filter(payment.payment_id),
                "out": PAYMENT_CURRENT_OUT,
            },
            session=session,
        )
        if current is None:
            raise PaymentNotFoundError(payment.payment_id)

        current_version = current["version_number"]
        payment.updated_at = now
        next_version = current_version + 1

        conflict_msg = (
            f"payment {payment.payment_id} was modified concurrently "
            f"(expected version {current_version}); please retry"
        )

        try:
            closed_out = now.isoformat() + "Z"
            result = await self._col.update_one(
                {
                    "_id": current["_id"],
                    "version_number": current_version,
                    "out": PAYMENT_CURRENT_OUT,
                },
                {"$set": {"out": closed_out}},
                session=session,
            )
            if result.modified_count != 1:
                raise ConcurrentModificationError(conflict_msg)

            document = versioned_payment_to_document(
                payment,
                version_number=next_version,
                valid_in=now,
            )
            await self._col.insert_one(document, session=session)
        except DuplicateKeyError as exc:
            raise ConcurrentModificationError(conflict_msg) from exc
        except OperationFailure as exc:
            if exc.code == 112 or "TransientTransactionError" in (exc.details or {}).get(
                "errorLabels", []
            ):
                raise ConcurrentModificationError(conflict_msg) from exc
            raise

        return document_to_versioned_payment(document)

    async def get_one(
        self,
        payment_id: str,
        *,
        out: str,
        session: AsyncIOMotorClientSession | None = None,
    ) -> VersionedPayment:
        if not out:
            raise ValueError("out is required for single-document payment lookup")
        document = await self._col.find_one(
            {**self._payment_id_filter(payment_id), "out": out},
            session=session,
        )
        if document is None:
            raise PaymentNotFoundError(payment_id)
        return document_to_versioned_payment(document)

    async def get_current(self, payment_id: str) -> VersionedPayment:
        return await self.get_one(payment_id, out=PAYMENT_CURRENT_OUT)

    async def list_current(
        self,
        *,
        instruction_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
        include_deleted: bool = False,
    ) -> list[VersionedPayment]:
        query: dict[str, Any] = {"out": PAYMENT_CURRENT_OUT}
        if instruction_id:
            query["instruction_id"] = instruction_id
        if status:
            query["status"] = status

        cursor = self._col.find(query).sort("in", -1).limit(limit)
        records = [document_to_versioned_payment(doc) async for doc in cursor]
        if include_deleted:
            return records
        return [
            record
            for record in records
            if record.payment.status != PaymentStatus.DELETED
        ]

    async def list_versions(self, payment_id: str) -> list[VersionedPayment]:
        cursor = self._col.find(self._payment_id_filter(payment_id)).sort(
            "version_number", 1
        )
        return [document_to_versioned_payment(doc) async for doc in cursor]
