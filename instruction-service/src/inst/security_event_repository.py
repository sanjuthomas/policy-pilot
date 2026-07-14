from typing import Any

from motor.motor_asyncio import AsyncIOMotorClientSession
from sequence_client import SequenceClient
from sequence_client.errors import SequenceClientError

from inst.config import settings
from inst.database import get_security_events_database
from inst.models.api import Subject
from inst.models.enums import LifecycleAction
from inst.models.instruction import CashSettlementInstruction
from inst.models.security_event import SecurityEvent
from inst.security_event_serialization import security_event_to_document


class SecurityEventRepository:
    """Internal write-only persistence for SIEM events (no REST exposure)."""

    def __init__(
        self,
        collection_name: str | None = None,
        sequence_client: SequenceClient | None = None,
    ) -> None:
        self.collection_name = collection_name or settings.security_events_collection
        self.sequence = sequence_client or SequenceClient(settings.sequence_service_url)

    @property
    def collection(self):
        return get_security_events_database()[self.collection_name]

    async def allocate_event_id(self, resource_id: str) -> str:
        try:
            return await self.sequence.next_security_event_id(resource_id=resource_id)
        except SequenceClientError as exc:
            raise RuntimeError(f"security event sequence allocation failed: {exc}") from exc

    async def insert_document(
        self,
        document: dict[str, Any],
        *,
        session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any]:
        await self.collection.insert_one(document, session=session)
        return document

    async def insert(self, event: SecurityEvent) -> SecurityEvent:
        document_id = await self.allocate_event_id(event.resource.id)
        document = security_event_to_document(event, document_id=document_id)
        await self.insert_document(document)
        return event

    async def record_authorized_action(
        self,
        action: LifecycleAction,
        subject: Subject,
        instruction: CashSettlementInstruction,
        *,
        version_number: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> SecurityEvent:
        document_id = await self.allocate_event_id(instruction.instruction_id)
        event = SecurityEvent.authorized_action(
            action,
            subject,
            instruction,
            version_number=version_number,
            details=details,
        )
        document = security_event_to_document(event, document_id=document_id)
        await self.insert_document(document)
        return event

    async def record_policy_denial(
        self,
        action: LifecycleAction,
        subject: Subject,
        instruction: CashSettlementInstruction,
        *,
        reason: str,
        details: dict[str, Any] | None = None,
        version_number: int | None = None,
    ) -> SecurityEvent:
        document_id = await self.allocate_event_id(instruction.instruction_id)
        event = SecurityEvent.policy_denial(
            action,
            subject,
            instruction,
            reason=reason,
            details=details,
            version_number=version_number,
        )
        document = security_event_to_document(event, document_id=document_id)
        await self.insert_document(document)
        return event
