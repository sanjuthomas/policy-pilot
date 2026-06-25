from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClientSession

from ilm.database import get_database
from ilm.models.instruction import CashSettlementInstruction
from ilm.storage import (
    VersionedInstruction,
    document_to_versioned_instruction,
    versioned_instruction_to_document,
)


class InstructionNotFoundError(Exception):
    pass


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

        instruction.updated_at = now
        next_version = current["version_number"] + 1
        await self.collection.update_one(
            {"_id": current["_id"]},
            {"$set": {"out": now.isoformat() + "Z"}},
            session=session,
        )

        document = versioned_instruction_to_document(
            instruction,
            version_number=next_version,
            valid_in=now,
        )
        await self.collection.insert_one(document, session=session)
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
