"""Payment service — business logic with Saga for SINGLE_USE instructions."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from authz_client import AuthzClient
from platform_auth import is_platform_admin
from sequence_client import SequenceClient
from sequence_client.errors import SequenceClientError

from ps.authorization import (
    build_authorization_block,
    details_with_authorization,
    payment_resource_context,
)
from ps.config import settings
from ps.database import mongo_transaction
from ps.instruction_client import (
    InstructionNotFoundError,
    InstructionServiceClient,
    InstructionStateError,
)
from ps.models.api import (
    DeletePaymentRequest,
    LifecycleEvent,
    RejectPaymentRequest,
    Subject,
    UserReference,
)
from ps.models.enums import PaymentAction, PaymentStatus
from ps.models.payment import Payment
from ps.models.security_event import PaymentSecurityEvent
from ps.repository import (
    PaymentNotFoundError,
    PaymentRepository,
)
from ps.security_event_repository import SecurityEventRepository
from ps.security_event_serialization import security_event_to_document
from ps.service_identity import service_identity
from ps.storage import VersionedPayment

logger = logging.getLogger(__name__)

_APPROVED_STATUSES = {"APPROVED"}


class InvalidStateTransitionError(Exception):
    pass


def _fmt_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat() + "Z"


def _covers_payment_lob(subject: Subject, owning_lob: str) -> bool:
    return owning_lob in subject.covering_lobs


def _can_view_payment(subject: Subject, payment: Payment) -> bool:
    if is_platform_admin(subject):
        return True
    if subject.user_id == payment.created_by.user_id:
        return True
    lob = payment.owning_lob
    roles = set(subject.roles)
    if "PAYMENT_CREATOR" in roles and (
        _covers_payment_lob(subject, lob) or subject.lob == lob
    ):
        return True
    if "FUNDING_APPROVER" in roles and _covers_payment_lob(subject, lob):
        return True
    return False


def _user_ref(subject: Subject) -> UserReference:
    return UserReference(
        user_id=subject.user_id,
        given_name=subject.given_name,
        family_name=subject.family_name,
        title=subject.title,
        lob=subject.lob,
        roles=subject.roles,
        supervisor_id=subject.supervisor_id,
    )


def _validate_instruction_at_create(instruction: dict) -> None:
    """Basic validation at payment creation time."""
    status = instruction.get("status", "")
    if status not in _APPROVED_STATUSES:
        raise ValueError(
            f"instruction is not in an approved state (status={status}). "
            "Only APPROVED instructions can be used for payments."
        )
    end_date_raw = instruction.get("end_date") or ""
    if end_date_raw:
        end_dt = datetime.fromisoformat(end_date_raw.replace("Z", "+00:00")).replace(tzinfo=None)
        if end_dt < datetime.now(timezone.utc).replace(tzinfo=None):
            raise ValueError(f"instruction has expired (end_date={end_date_raw})")


def _check_instruction_validity_for_approval(payment: Payment, instruction: dict) -> str | None:
    """Comprehensive instruction validity check at approval time."""
    now = datetime.now(timezone.utc)

    current_version = int(instruction.get("version_number") or 0)
    if current_version != payment.instruction_version:
        return (
            f"instruction was modified after payment creation — "
            f"payment was created against version {payment.instruction_version} "
            f"but the current version is {current_version}; "
            "please review the instruction changes and create a new payment if still valid"
        )

    status = instruction.get("status", "")
    if status not in _APPROVED_STATUSES:
        return (
            f"instruction is no longer in an approvable state "
            f"(current status={status!r}); it must be APPROVED to approve a payment"
        )

    end_date_raw = instruction.get("end_date") or ""
    if end_date_raw:
        try:
            end_dt = datetime.fromisoformat(end_date_raw.replace("Z", "+00:00"))
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            if end_dt < now:
                return (
                    f"instruction has expired (end_date={end_date_raw}); "
                    "the payment cannot be approved against an expired instruction"
                )
        except ValueError:
            return f"instruction has an unparseable end_date value: {end_date_raw!r}"

    effective_date_raw = instruction.get("effective_date") or ""
    if effective_date_raw:
        try:
            eff_dt = datetime.fromisoformat(effective_date_raw.replace("Z", "+00:00"))
            if eff_dt.tzinfo is None:
                eff_dt = eff_dt.replace(tzinfo=timezone.utc)
            if eff_dt > now:
                return (
                    f"instruction is not yet effective (effective_date={effective_date_raw}); "
                    "payments cannot be approved before the instruction becomes active"
                )
        except ValueError:
            return f"instruction has an unparseable effective_date value: {effective_date_raw!r}"

    # Instruction type consistency (status is separate from type).
    current_type = instruction.get("instruction_type") or ""
    if current_type and payment.instruction_type and current_type != payment.instruction_type:
        return (
            f"instruction type changed since payment creation "
            f"(payment snapshot={payment.instruction_type!r}, current={current_type!r})"
        )

    return None


class PaymentService:
    def __init__(self, sequence_client: SequenceClient | None = None) -> None:
        self.repo = PaymentRepository()
        self.event_repo = SecurityEventRepository()
        self.authz = AuthzClient(settings.authorization_service_url)
        self.instruction_service = InstructionServiceClient()
        self.sequence = sequence_client or SequenceClient(settings.sequence_service_url)

    @staticmethod
    def _should_record_security_event(subject: Subject) -> bool:
        return subject.user_id not in settings.security_event_excluded_user_id_set

    @staticmethod
    def _should_record_view_security_event(subject: Subject) -> bool:
        if subject.user_id in settings.security_event_view_excluded_user_id_set:
            return False
        return PaymentService._should_record_security_event(subject)

    async def _evaluate_policy(
        self,
        action: PaymentAction,
        subject: Subject,
        payment: Payment,
        *,
        instruction_end_date: str = "",
        instruction_status: str = "",
        bearer_token: str | None = None,
        session_id: str | None = None,
    ):
        await service_identity.ensure_logged_in()
        common = {
            "action": action.value,
            "payment": payment.to_opa_payment(
                instruction_end_date=instruction_end_date,
                instruction_status=instruction_status,
            ),
            "instruction_end_date": instruction_end_date,
            "instruction_status": instruction_status,
            "service_token": service_identity.token,
            "service_session_id": service_identity.session_id,
        }
        if bearer_token and service_identity.token:
            return await self.authz.evaluate_payment(
                **common,
                user_token=bearer_token,
                user_session_id=session_id,
            )
        return await self.authz.evaluate_payment(
            **common,
            subject=subject.model_dump(mode="json"),
        )

    async def _authorize(
        self,
        action: PaymentAction,
        subject: Subject,
        payment: Payment,
        *,
        instruction_end_date: str = "",
        instruction_status: str = "",
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        decision = await self._evaluate_policy(
            action,
            subject,
            payment,
            instruction_end_date=instruction_end_date,
            instruction_status=instruction_status,
            bearer_token=bearer_token,
            session_id=session_id,
        )
        authorization = build_authorization_block(
            decision,
            subject,
            action,
            resource_context=payment_resource_context(
                payment,
                instruction_status=instruction_status,
                instruction_end_date=instruction_end_date,
            ),
        )
        if not decision.allowed:
            if self._should_record_security_event(subject):
                await self.event_repo.record_policy_denial(
                    action,
                    subject,
                    payment,
                    reason=authorization["summary"],
                    details=details_with_authorization(None, authorization),
                )
            raise PermissionError(authorization["summary"])
        return authorization

    async def _save_payment_with_security_event(
        self,
        payment: Payment,
        action: PaymentAction,
        subject: Subject,
        *,
        details: dict | None = None,
        initial: bool = False,
    ) -> VersionedPayment:
        """Persist payment version and matching security event atomically."""
        async with mongo_transaction() as session:
            if initial:
                saved = await self.repo.insert_initial(payment, session=session)
            else:
                saved = await self.repo.append_version(payment, session=session)

            if self._should_record_security_event(subject):
                event_id = await self.event_repo.allocate_event_id(payment.payment_id)
                event = PaymentSecurityEvent.authorized_action(
                    action,
                    subject,
                    saved.payment,
                    version_number=saved.version_number,
                    details=details,
                )
                await self.event_repo.insert_document(
                    security_event_to_document(event, document_id=event_id),
                    session=session,
                )

        return saved

    async def _persist_new_version(
        self,
        payment: Payment,
        action: PaymentAction,
        subject: Subject,
        details: dict | None = None,
        *,
        instruction_end_date: str = "",
        instruction_status: str = "",
        bearer_token: str | None = None,
        session_id: str | None = None,
        skip_authorize: bool = False,
    ) -> VersionedPayment:
        if not skip_authorize:
            authorization = await self._authorize(
                action,
                subject,
                payment,
                instruction_end_date=instruction_end_date,
                instruction_status=instruction_status,
                bearer_token=bearer_token,
                session_id=session_id,
            )
            details = details_with_authorization(details, authorization)
        self._record_event(payment, action, subject, details)
        return await self._save_payment_with_security_event(
            payment,
            action,
            subject,
            details=details,
        )

    def _record_event(
        self,
        payment: Payment,
        action: PaymentAction,
        subject: Subject,
        details: dict | None = None,
    ) -> None:
        payment.lifecycle_events.append(
            LifecycleEvent(
                event_id=str(uuid4()),
                action=action.value,
                actor_user_id=subject.user_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                details=details or {},
            )
        )

    # ── Create ────────────────────────────────────────────────────────────────

    async def create(
        self,
        *,
        instruction_id: str,
        value_date: str,
        amount: float,
        subject: Subject,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> VersionedPayment:
        try:
            instruction = await self.instruction_service.get_instruction(
                instruction_id, bearer_token=bearer_token, session_id=session_id
            )
        except InstructionNotFoundError:
            raise

        _validate_instruction_at_create(instruction)

        instruction_status = instruction["status"]
        instruction_type = instruction["instruction_type"]
        instruction_version = int(instruction.get("version_number") or 1)
        end_date = instruction.get("end_date") or ""

        lifecycle_event_id = str(uuid4())
        business_date = datetime.now(timezone.utc).date()
        try:
            payment_id = await self.sequence.next_payment_id(
                business_date=business_date,
                owning_lob=instruction["owning_lob"],
            )
        except SequenceClientError as exc:
            raise RuntimeError(f"sequence allocation failed: {exc}") from exc

        payment = Payment.create(
            payment_id=payment_id,
            instruction_id=instruction_id,
            instruction_version=instruction_version,
            amount=amount,
            currency=instruction["currency"],
            value_date=value_date,
            owning_lob=instruction["owning_lob"],
            instruction_type=instruction_type,
            subject=subject,
            event_id=lifecycle_event_id,
        )

        try:
            authorization = await self._authorize(
                PaymentAction.CREATE_PAYMENT,
                subject,
                payment,
                instruction_end_date=end_date,
                instruction_status=instruction_status,
                bearer_token=bearer_token,
                session_id=session_id,
            )
        except PermissionError:
            raise

        # Saga: for SINGLE_USE type mark instruction USED first
        if instruction_type == "SINGLE_USE":
            try:
                await self.instruction_service.mark_used(
                    instruction_id,
                    payment.payment_id,
                    bearer_token=bearer_token,
                    session_id=session_id,
                )
            except InstructionStateError as exc:
                if self._should_record_security_event(subject):
                    await self.event_repo.record_policy_denial(
                        PaymentAction.CREATE_PAYMENT,
                        subject,
                        payment,
                        reason=f"Saga step failed — instruction cannot be marked USED: {exc}",
                        details={"saga_step": "mark_used", "saga_error": str(exc)},
                    )
                raise ValueError(str(exc)) from exc
            except Exception as exc:
                if self._should_record_security_event(subject):
                    await self.event_repo.record_policy_denial(
                        PaymentAction.CREATE_PAYMENT,
                        subject,
                        payment,
                        reason=f"Saga step failed — instruction-service unreachable: {exc}",
                        details={"saga_step": "mark_used", "saga_error": str(exc)},
                    )
                raise RuntimeError(
                    f"Could not mark instruction as USED before creating payment: {exc}"
                ) from exc

        details = details_with_authorization(None, authorization)
        self._record_event(payment, PaymentAction.CREATE_PAYMENT, subject, details)
        saved = await self._save_payment_with_security_event(
            payment,
            PaymentAction.CREATE_PAYMENT,
            subject,
            details=details,
            initial=True,
        )

        logger.info(
            "payment created (DRAFT) payment_id=%s instruction_id=%s amount=%s currency=%s",
            payment.payment_id, instruction_id, amount, payment.currency,
        )
        return saved

    # ── Submit ────────────────────────────────────────────────────────────────

    async def submit(
        self,
        payment_id: str,
        subject: Subject,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> VersionedPayment:
        current = await self._get_current_or_404(payment_id)
        payment = current.payment.model_copy(deep=True)
        if payment.status != PaymentStatus.DRAFT:
            raise InvalidStateTransitionError(
                "only DRAFT payments can be submitted"
            )

        try:
            instruction = await self.instruction_service.get_instruction(
                payment.instruction_id, bearer_token=bearer_token, session_id=session_id
            )
        except InstructionNotFoundError:
            raise ValueError(f"backing instruction {payment.instruction_id} not found")

        instruction_end_date = instruction.get("end_date") or ""
        instruction_status = instruction.get("status", "")

        now = datetime.now(timezone.utc)
        payment.status = PaymentStatus.SUBMITTED
        payment.submitted_by = _user_ref(subject)
        payment.updated_at = now

        saved = await self._persist_new_version(
            payment,
            PaymentAction.SUBMIT_PAYMENT,
            subject,
            instruction_end_date=instruction_end_date,
            instruction_status=instruction_status,
            bearer_token=bearer_token,
            session_id=session_id,
        )

        logger.info("payment submitted payment_id=%s by=%s", payment_id, subject.user_id)
        return saved

    # ── Approve ───────────────────────────────────────────────────────────────

    async def approve(
        self,
        payment_id: str,
        subject: Subject,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> VersionedPayment:
        current = await self._get_current_or_404(payment_id)
        payment = current.payment.model_copy(deep=True)
        if payment.status != PaymentStatus.SUBMITTED:
            raise InvalidStateTransitionError(
                "only SUBMITTED payments can be approved"
            )

        try:
            instruction = await self.instruction_service.get_instruction(
                payment.instruction_id, bearer_token=bearer_token, session_id=session_id
            )
        except InstructionNotFoundError:
            cancellation_reason = (
                f"backing instruction {payment.instruction_id} could not be found at approval time"
            )
            return await self._cancel(payment, subject, cancellation_reason)

        invalid_reason = _check_instruction_validity_for_approval(payment, instruction)
        if invalid_reason:
            return await self._cancel(payment, subject, invalid_reason)

        instruction_end_date = instruction.get("end_date") or ""
        instruction_status = instruction.get("status", "")

        now = datetime.now(timezone.utc)
        payment.status = PaymentStatus.APPROVED
        payment.approved_by = _user_ref(subject)
        payment.updated_at = now

        saved = await self._persist_new_version(
            payment,
            PaymentAction.APPROVE_PAYMENT,
            subject,
            instruction_end_date=instruction_end_date,
            instruction_status=instruction_status,
            bearer_token=bearer_token,
            session_id=session_id,
        )

        logger.info("payment approved payment_id=%s by=%s", payment_id, subject.user_id)
        return saved

    # ── Reject ────────────────────────────────────────────────────────────────

    async def reject(
        self,
        payment_id: str,
        subject: Subject,
        request: RejectPaymentRequest,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> VersionedPayment:
        current = await self._get_current_or_404(payment_id)
        payment = current.payment.model_copy(deep=True)
        if payment.status != PaymentStatus.SUBMITTED:
            raise InvalidStateTransitionError(
                "only SUBMITTED payments can be rejected"
            )

        try:
            instruction = await self.instruction_service.get_instruction(
                payment.instruction_id, bearer_token=bearer_token, session_id=session_id
            )
        except InstructionNotFoundError:
            raise ValueError(f"backing instruction {payment.instruction_id} not found")

        instruction_end_date = instruction.get("end_date") or ""
        instruction_status = instruction.get("status", "")

        now = datetime.now(timezone.utc)
        payment.status = PaymentStatus.REJECTED
        payment.rejected_by = _user_ref(subject)
        payment.rejection_reason = request.reason
        payment.updated_at = now

        saved = await self._persist_new_version(
            payment,
            PaymentAction.REJECT_PAYMENT,
            subject,
            details={"reason": request.reason},
            instruction_end_date=instruction_end_date,
            instruction_status=instruction_status,
            bearer_token=bearer_token,
            session_id=session_id,
        )

        logger.info("payment rejected payment_id=%s by=%s", payment_id, subject.user_id)
        return saved

    async def delete(
        self,
        payment_id: str,
        subject: Subject,
        request: DeletePaymentRequest | None = None,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> VersionedPayment:
        current = await self._get_current_or_404(payment_id)
        payment = current.payment.model_copy(deep=True)

        if payment.status == PaymentStatus.DELETED:
            raise InvalidStateTransitionError("payment is already deleted")

        if payment.status not in {PaymentStatus.DRAFT, PaymentStatus.SUBMITTED}:
            raise InvalidStateTransitionError(
                "only DRAFT or SUBMITTED payments can be soft deleted"
            )

        try:
            instruction = await self.instruction_service.get_instruction(
                payment.instruction_id, bearer_token=bearer_token, session_id=session_id
            )
        except InstructionNotFoundError:
            raise ValueError(f"backing instruction {payment.instruction_id} not found")

        instruction_end_date = instruction.get("end_date") or ""
        instruction_status = instruction.get("status", "")

        payment.status = PaymentStatus.DELETED
        payment.updated_at = datetime.now(timezone.utc)
        details = {"reason": request.reason} if request and request.reason else {}

        saved = await self._persist_new_version(
            payment,
            PaymentAction.DELETE_PAYMENT,
            subject,
            details=details,
            instruction_end_date=instruction_end_date,
            instruction_status=instruction_status,
            bearer_token=bearer_token,
            session_id=session_id,
        )

        logger.info("payment soft-deleted payment_id=%s by=%s", payment_id, subject.user_id)
        return saved

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get(self, payment_id: str, subject: Subject) -> VersionedPayment:
        record = await self._get_current_or_404(payment_id)
        if not _can_view_payment(subject, record.payment):
            raise PermissionError("not authorized to view payment")
        return record

    async def list(
        self,
        subject: Subject,
        *,
        instruction_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[VersionedPayment]:
        records = await self.repo.list_current(
            instruction_id=instruction_id,
            status=status,
            limit=limit,
        )
        visible = []
        for record in records:
            if _can_view_payment(subject, record.payment):
                visible.append(record)
        return visible

    async def eligible_approvers(self, payment_id: str) -> dict:
        record = await self._get_current_or_404(payment_id)
        payment = record.payment
        instruction = await self.instruction_service.get_instruction_as_service(payment.instruction_id)
        await service_identity.ensure_logged_in()
        return await self.authz.eligible_payment_approvers(
            payment={
                "payment_id": payment.payment_id,
                "instruction_id": payment.instruction_id,
                "instruction_version": payment.instruction_version,
                "status": payment.status.value,
                "amount": payment.amount,
                "currency": payment.currency,
                "owning_lob": payment.owning_lob,
                "created_by_user_id": payment.created_by.user_id,
                "created_by_supervisor_id": payment.created_by.supervisor_id,
            },
            instruction_status=str(instruction.get("status") or ""),
            instruction_end_date=str(instruction.get("end_date") or ""),
            service_token=service_identity.token,
            service_session_id=service_identity.session_id,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _cancel(self, payment: Payment, subject: Subject, reason: str) -> VersionedPayment:
        """Move a payment to CANCELLED and record a security event with the approver's identity."""
        now = datetime.now(timezone.utc)
        payment.status = PaymentStatus.CANCELLED
        payment.cancelled_by = _user_ref(subject)
        payment.cancellation_reason = reason
        payment.updated_at = now
        self._record_event(
            payment,
            PaymentAction.CANCEL_PAYMENT,
            subject,
            details={"reason": reason},
        )

        saved = await self._save_payment_with_security_event(
            payment,
            PaymentAction.CANCEL_PAYMENT,
            subject,
            details={"reason": reason},
        )

        logger.warning(
            "payment cancelled payment_id=%s by=%s reason=%s",
            payment.payment_id, subject.user_id, reason,
        )
        return saved

    async def _get_current_or_404(self, payment_id: str) -> VersionedPayment:
        try:
            return await self.repo.get_current(payment_id)
        except PaymentNotFoundError as exc:
            raise LookupError(f"payment {payment_id} not found") from exc
