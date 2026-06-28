from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClientSession
from pymongo.errors import DuplicateKeyError, OperationFailure

from inst.database import get_database
from inst.models.instruction import CashSettlementInstruction
from inst.storage import (
    VersionedInstruction,
    document_to_versioned_instruction,
    versioned_instruction_to_document,
)


class InstructionNotFoundError(Exception):
    pass


class ConcurrentModificationError(Exception):
    """Raised when optimistic locking detects a concurrent write.

    The caller should retry the operation from a fresh read of the current
    version, or surface a 409 Conflict to the API client.
    """


class InstructionRepository:
    collection_name = "instructions"

    @property
    def collection(self):
        return get_database()[self.collection_name]

    async def insert_initial(
        self,
        instruction: CashSettlementInstruction,
        *,
        session: AsyncIOMotorClientSession | None = None,
    ) -> VersionedInstruction:
        now = datetime.utcnow()
        document = versioned_instruction_to_document(
            instruction,
            version_number=1,
            valid_in=now,
        )
        await self.collection.insert_one(document, session=session)
        return document_to_versioned_instruction(document)

    async def append_version(
        self,
        instruction: CashSettlementInstruction,
        *,
        session: AsyncIOMotorClientSession | None = None,
    ) -> VersionedInstruction:
        now = datetime.utcnow()
        current = await self.collection.find_one(
            {"instruction_id": instruction.instruction_id, "out": None},
            session=session,
        )
        if current is None:
            raise InstructionNotFoundError(instruction.instruction_id)

        current_version = current["version_number"]
        instruction.updated_at = now
        next_version = current_version + 1

        _conflict_msg = (
            f"instruction {instruction.instruction_id} was modified concurrently "
            f"(expected version {current_version}); please retry"
        )

        try:
            # Optimistic locking: close the current version only if its version_number
            # still matches what we read.  A concurrent writer will have already
            # incremented it, so modified_count will be 0.
            result = await self.collection.update_one(
                {"_id": current["_id"], "version_number": current_version, "out": None},
                {"$set": {"out": now.isoformat() + "Z"}},
                session=session,
            )
            if result.modified_count != 1:
                raise ConcurrentModificationError(_conflict_msg)

            document = versioned_instruction_to_document(
                instruction,
                version_number=next_version,
                valid_in=now,
            )
            await self.collection.insert_one(document, session=session)
        except DuplicateKeyError as exc:
            # The partial unique index on (instruction_id, out=None) fired — another
            # transaction already inserted the next version while we were in flight.
            raise ConcurrentModificationError(_conflict_msg) from exc
        except OperationFailure as exc:
            # MongoDB raises WriteConflict (code 112) with label TransientTransactionError
            # when two transactions race to write the same document.
            if exc.code == 112 or "TransientTransactionError" in (exc.details or {}).get(
                "errorLabels", []
            ):
                raise ConcurrentModificationError(_conflict_msg) from exc
            raise

        return document_to_versioned_instruction(document)

    async def get_current(self, instruction_id: str) -> VersionedInstruction:
        document = await self.collection.find_one(
            {"instruction_id": instruction_id, "out": None}
        )
        if document is None:
            raise InstructionNotFoundError(instruction_id)
        return document_to_versioned_instruction(document)

    async def list_current(
        self,
        *,
        owning_lob: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[VersionedInstruction]:
        query: dict[str, Any] = {"out": None}
        if owning_lob:
            query["owning_lob"] = owning_lob
        if status:
            query["status"] = status

        cursor = self.collection.find(query).sort("in", -1).limit(limit)
        return [document_to_versioned_instruction(doc) async for doc in cursor]

    async def list_versions(self, instruction_id: str) -> list[VersionedInstruction]:
        cursor = self.collection.find({"instruction_id": instruction_id}).sort(
            "version_number", 1
        )
        return [document_to_versioned_instruction(doc) async for doc in cursor]
