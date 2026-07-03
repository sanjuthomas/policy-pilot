import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClientSession
from sequence_client import SequenceClient
from sequence_client.errors import SequenceClientError

from ps.config import settings
from ps.database import get_security_events_db
from ps.models.api import Subject
from ps.models.enums import PaymentAction, SecurityEventSeverity
from ps.models.payment import Payment
from ps.models.security_event import PaymentSecurityEvent
from ps.security_event_serialization import security_event_to_document

logger = logging.getLogger(__name__)


class SecurityEventRepository:
    """Write-only persistence for payment SIEM events."""

    def __init__(self, sequence_client: SequenceClient | None = None) -> None:
        self.sequence = sequence_client or SequenceClient(settings.sequence_service_url)

    @property
    def _col(self):
        return get_security_events_db()[settings.security_events_collection]

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
        await self._col.insert_one(document, session=session)
        return document

    async def insert(self, event: PaymentSecurityEvent) -> PaymentSecurityEvent:
        document_id = await self.allocate_event_id(event.resource.id)
        document = security_event_to_document(event, document_id=document_id)
        await self.insert_document(document)
        return event

    async def record_authorized_action(
        self,
        action: PaymentAction,
        subject: Subject,
        payment: Payment,
        *,
        version_number: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> PaymentSecurityEvent:
        document_id = await self.allocate_event_id(payment.payment_id)
        event = PaymentSecurityEvent.authorized_action(
            action,
            subject,
            payment,
            version_number=version_number,
            details=details,
        )
        document = security_event_to_document(event, document_id=document_id)
        await self.insert_document(document)
        return event

    async def record_policy_denial(
        self,
        action: PaymentAction,
        subject: Subject,
        payment: Payment,
        *,
        reason: str,
        details: dict[str, Any] | None = None,
        severity: SecurityEventSeverity | None = None,
    ) -> PaymentSecurityEvent:
        document_id = await self.allocate_event_id(payment.payment_id)
        event = PaymentSecurityEvent.policy_denial(
            action,
            subject,
            payment,
            reason=reason,
            details=details,
            severity=severity,
        )
        document = security_event_to_document(event, document_id=document_id)
        await self.insert_document(document)
        return event
