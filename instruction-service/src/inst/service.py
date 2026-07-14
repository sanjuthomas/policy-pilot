from datetime import datetime, timezone
from uuid import uuid4

from authz_client import AuthzClient
from sequence_client import SequenceClient
from sequence_client.errors import SequenceClientError

from inst.authorization import (
    build_authorization_block,
    details_with_authorization,
    instruction_resource_context,
)
from inst.config import settings
from inst.constants import INSTRUCTION_CURRENT_OUT
from inst.database import mongo_transaction
from inst.models.api import (
    CancelInstructionRequest,
    CreateInstructionRequest,
    InstructionResponse,
    RejectInstructionRequest,
    ReleaseUseInstructionRequest,
    Subject,
    UpdateInstructionRequest,
    UseInstructionRequest,
)
from inst.models.enums import (
    InstructionStatus,
    InstructionType,
    LifecycleAction,
)
from inst.models.instruction import (
    CashSettlementInstruction,
    LifecycleEvent,
    UserReference,
)
from inst.models.security_event import SecurityEvent
from inst.repository import InstructionRepository
from inst.security_event_repository import SecurityEventRepository
from inst.security_event_serialization import security_event_to_document
from inst.service_identity import service_identity
from inst.storage import VersionedInstruction


class InvalidStateTransitionError(Exception):
    pass


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).replace(tzinfo=None)


def _fmt_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat() + "Z"


def _to_response(record: VersionedInstruction) -> InstructionResponse:
    instruction = record.instruction

    return InstructionResponse(
        instruction_id=instruction.instruction_id,
        version_number=record.version_number,
        record_in=_fmt_datetime(record.valid_in) or "",
        record_out=(
            INSTRUCTION_CURRENT_OUT
            if record.valid_out is None
            else _fmt_datetime(record.valid_out)
        ),
        instruction_type=instruction.instruction_type.value,
        status=instruction.status.value,
        owning_lob=instruction.owning_lob,
        wire_scope=instruction.wire_scope.value,
        currency=instruction.currency,
        funding_account=instruction.funding_account,
        initiating_party=instruction.initiating_party,
        ultimate_debtor=instruction.ultimate_debtor,
        debtor=instruction.debtor,
        debtor_account=instruction.debtor_account,
        debtor_agent=instruction.debtor_agent,
        debtor_agent_account=instruction.debtor_agent_account,
        instructing_agent=instruction.instructing_agent,
        instructed_agent=instruction.instructed_agent,
        previous_instructing_agents=instruction.previous_instructing_agents,
        intermediary_agents=instruction.intermediary_agents,
        creditor_agent=instruction.creditor_agent,
        creditor_agent_account=instruction.creditor_agent_account,
        creditor=instruction.creditor,
        creditor_account=instruction.creditor_account,
        ultimate_creditor=instruction.ultimate_creditor,
        charge_bearer=instruction.charge_bearer.value,
        instructions_for_creditor_agent=instruction.instructions_for_creditor_agent,
        instructions_for_next_agent=instruction.instructions_for_next_agent,
        effective_date=_fmt_datetime(instruction.effective_date) or "",
        end_date=_fmt_datetime(instruction.end_date) or "",
        created_by=instruction.created_by,
        created_at=_fmt_datetime(instruction.created_at) or "",
        updated_at=_fmt_datetime(instruction.updated_at) or "",
        submitted_at=_fmt_datetime(instruction.submitted_at),
        approved_by=instruction.approved_by,
        approved_at=_fmt_datetime(instruction.approved_at),
        rejected_by=instruction.rejected_by,
        rejected_at=_fmt_datetime(instruction.rejected_at),
        rejection_reason=instruction.rejection_reason,
        cancelled_at=_fmt_datetime(instruction.cancelled_at),
        suspended_by=instruction.suspended_by,
        suspended_at=_fmt_datetime(instruction.suspended_at),
        last_used_at=_fmt_datetime(instruction.last_used_at),
        usage_count=instruction.usage_count,
        used_by=instruction.used_by,
    )


def _instruction_from_request(
    request: CreateInstructionRequest,
    subject: Subject,
    *,
    instruction_id: str | None = None,
    status: InstructionStatus = InstructionStatus.DRAFT,
    created_by: UserReference | None = None,
) -> CashSettlementInstruction:
    return CashSettlementInstruction(
        instruction_id=instruction_id or str(uuid4()),
        instruction_type=request.instruction_type,
        status=status,
        owning_lob=request.owning_lob,
        wire_scope=request.wire_scope,
        currency=request.currency,
        funding_account=request.funding_account,
        initiating_party=request.initiating_party,
        ultimate_debtor=request.ultimate_debtor,
        debtor=request.debtor,
        debtor_account=request.debtor_account,
        debtor_agent=request.debtor_agent,
        debtor_agent_account=request.debtor_agent_account,
        instructing_agent=request.instructing_agent,
        instructed_agent=request.instructed_agent,
        previous_instructing_agents=request.previous_instructing_agents,
        intermediary_agents=request.intermediary_agents,
        creditor_agent=request.creditor_agent,
        creditor_agent_account=request.creditor_agent_account,
        creditor=request.creditor,
        creditor_account=request.creditor_account,
        ultimate_creditor=request.ultimate_creditor,
        charge_bearer=request.charge_bearer,
        instructions_for_creditor_agent=request.instructions_for_creditor_agent,
        instructions_for_next_agent=request.instructions_for_next_agent,
        effective_date=_parse_datetime(request.effective_date),
        end_date=_parse_datetime(request.end_date),
        created_by=created_by
        or UserReference(
            user_id=subject.user_id,
            given_name=subject.given_name,
            family_name=subject.family_name,
            title=subject.title,
            lob=subject.lob,
            roles=subject.roles,
            supervisor_id=subject.supervisor_id,
        ),
    )


class InstructionService:
    def __init__(
        self,
        repository: InstructionRepository | None = None,
        authz_client: AuthzClient | None = None,
        security_events: SecurityEventRepository | None = None,
        sequence_client: SequenceClient | None = None,
    ) -> None:
        self.repository = repository or InstructionRepository()
        self.authz = authz_client or AuthzClient(settings.authorization_service_url)
        self.security_events = security_events or SecurityEventRepository()
        self.sequence = sequence_client or SequenceClient(settings.sequence_service_url)

    @staticmethod
    def _should_record_security_event(subject: Subject) -> bool:
        return subject.user_id not in settings.security_event_excluded_user_id_set

    @staticmethod
    def _should_record_view_security_event(subject: Subject) -> bool:
        if subject.user_id in settings.security_event_view_excluded_user_id_set:
            return False
        return InstructionService._should_record_security_event(subject)

    async def _evaluate_policy(
        self,
        action: LifecycleAction,
        subject: Subject,
        instruction: CashSettlementInstruction,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
        authz_service_token: str | None = None,
        authz_service_session_id: str | None = None,
    ):
        """Evaluate lifecycle policy via authz with a verified user OBO token.

        ``bearer_token`` is the human JWT when provided by the caller. Routes may
        also bind :mod:`inst.evaluate_tokens` so nested OBO (payment → instruction)
        forwards the calling service account to authz and preserves
        ``INSTRUCTION_MARKER`` on ``delegated_by_roles``.
        """
        from inst.evaluate_tokens import current_evaluate_token_context

        ctx = current_evaluate_token_context()
        user_token = bearer_token or (ctx.user_token if ctx else None)
        user_session_id = session_id or (ctx.user_session_id if ctx else None)
        service_override = authz_service_token or (
            ctx.authz_service_token if ctx else None
        )
        service_session_override = authz_service_session_id or (
            ctx.authz_service_session_id if ctx else None
        )

        if not user_token:
            raise PermissionError(
                "user token required for policy evaluation "
                "(pass the caller's JWT for X-On-Behalf-Of)"
            )
        await service_identity.ensure_logged_in()
        service_token = service_override or service_identity.token
        service_session_id = (
            service_session_override if service_override else service_identity.session_id
        )
        if not service_token:
            raise PermissionError("service identity token required for policy evaluation")
        return await self.authz.evaluate_instruction(
            action=action.value,
            instruction=instruction.to_opa_instruction(),
            account=instruction.to_opa_account(),
            service_token=service_token,
            service_session_id=service_session_id,
            user_token=user_token,
            user_session_id=user_session_id,
            subject=subject.model_dump(mode="json"),
        )

    async def _authorize(
        self,
        action: LifecycleAction,
        subject: Subject,
        instruction: CashSettlementInstruction,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
        record_security_event: bool = False,
        security_event_details: dict | None = None,
    ) -> dict:
        decision = await self._evaluate_policy(
            action,
            subject,
            instruction,
            bearer_token=bearer_token,
            session_id=session_id,
        )
        authorization = build_authorization_block(
            decision,
            subject,
            action,
            resource_context=instruction_resource_context(instruction),
        )
        if not decision.allowed:
            if record_security_event and self._should_record_security_event(subject):
                await self.security_events.record_policy_denial(
                    action,
                    subject,
                    instruction,
                    reason=authorization["summary"],
                    details=details_with_authorization(
                        security_event_details, authorization
                    ),
                )
            raise PermissionError(authorization["summary"])
        return authorization

    async def _record_authorized_action(
        self,
        action: LifecycleAction,
        subject: Subject,
        instruction: CashSettlementInstruction,
        *,
        version_number: int | None = None,
        details: dict | None = None,
    ) -> None:
        if action == LifecycleAction.VIEW and not self._should_record_view_security_event(
            subject
        ):
            return
        if not self._should_record_security_event(subject):
            return
        await self.security_events.record_authorized_action(
            action,
            subject,
            instruction,
            version_number=version_number,
            details=details,
        )

    def _record_event(
        self,
        instruction: CashSettlementInstruction,
        action: LifecycleAction,
        subject: Subject,
        details: dict | None = None,
    ) -> None:
        instruction.lifecycle_events.append(
            LifecycleEvent(
                action=action.value,
                actor_user_id=subject.user_id,
                details=details or {},
            )
        )

    async def _save_instruction_with_security_event(
        self,
        instruction: CashSettlementInstruction,
        action: LifecycleAction,
        subject: Subject,
        *,
        details: dict | None = None,
        initial: bool = False,
    ) -> VersionedInstruction:
        """Persist instruction version and matching security event atomically."""
        async with mongo_transaction() as session:
            if initial:
                saved = await self.repository.insert_initial(instruction, session=session)
            else:
                saved = await self.repository.append_version(instruction, session=session)

            if self._should_record_security_event(subject):
                event_id = await self.security_events.allocate_event_id(
                    saved.instruction.instruction_id
                )
                event = SecurityEvent.authorized_action(
                    action,
                    subject,
                    saved.instruction,
                    version_number=saved.version_number,
                    details=details,
                )
                await self.security_events.insert_document(
                    security_event_to_document(event, document_id=event_id),
                    session=session,
                )

        return saved

    async def _persist_new_version(
        self,
        instruction: CashSettlementInstruction,
        action: LifecycleAction,
        subject: Subject,
        details: dict | None = None,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
        skip_authorize: bool = False,
    ) -> VersionedInstruction:
        if not skip_authorize:
            authorization = await self._authorize(
                action,
                subject,
                instruction,
                bearer_token=bearer_token,
                session_id=session_id,
                record_security_event=True,
                security_event_details=details,
            )
            details = details_with_authorization(details, authorization)
        self._record_event(instruction, action, subject, details)
        return await self._save_instruction_with_security_event(
            instruction,
            action,
            subject,
            details=details,
        )

    async def create(
        self,
        request: CreateInstructionRequest,
        subject: Subject,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> InstructionResponse:
        business_date = datetime.now(timezone.utc).date()
        try:
            instruction_id = await self.sequence.next_instruction_id(
                business_date=business_date,
                owning_lob=request.owning_lob,
            )
        except SequenceClientError as exc:
            raise RuntimeError(f"sequence allocation failed: {exc}") from exc

        instruction = _instruction_from_request(
            request,
            subject,
            instruction_id=instruction_id,
        )
        authorization = await self._authorize(
            LifecycleAction.CREATE,
            subject,
            instruction,
            bearer_token=bearer_token,
            session_id=session_id,
            record_security_event=True,
        )
        details = details_with_authorization(None, authorization)
        self._record_event(instruction, LifecycleAction.CREATE, subject, details)
        saved = await self._save_instruction_with_security_event(
            instruction,
            LifecycleAction.CREATE,
            subject,
            details=details,
            initial=True,
        )
        return _to_response(saved)

    async def update(
        self,
        instruction_id: str,
        request: UpdateInstructionRequest,
        subject: Subject,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> InstructionResponse:
        current = await self.repository.get_current(instruction_id)
        instruction = current.instruction

        if instruction.status != InstructionStatus.DRAFT:
            raise InvalidStateTransitionError("only DRAFT instructions can be updated")

        updated = _instruction_from_request(
            request,
            subject,
            instruction_id=instruction.instruction_id,
            status=instruction.status,
            created_by=instruction.created_by,
        )
        updated.lifecycle_events = list(instruction.lifecycle_events)
        updated.created_at = instruction.created_at
        updated.submitted_at = instruction.submitted_at
        updated.approved_by = instruction.approved_by
        updated.approved_at = instruction.approved_at
        updated.rejected_by = instruction.rejected_by
        updated.rejected_at = instruction.rejected_at
        updated.rejection_reason = instruction.rejection_reason
        updated.cancelled_at = instruction.cancelled_at
        updated.suspended_by = instruction.suspended_by
        updated.suspended_at = instruction.suspended_at
        updated.last_used_at = instruction.last_used_at
        updated.usage_count = instruction.usage_count
        updated.used_by = instruction.used_by

        saved = await self._persist_new_version(
            updated,
            LifecycleAction.UPDATE,
            subject,
            bearer_token=bearer_token,
            session_id=session_id,
        )
        return _to_response(saved)

    async def cancel(
        self,
        instruction_id: str,
        subject: Subject,
        request: CancelInstructionRequest | None = None,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> InstructionResponse:
        current = await self.repository.get_current(instruction_id)
        instruction = current.instruction.model_copy(deep=True)

        if instruction.status == InstructionStatus.CANCELLED:
            raise InvalidStateTransitionError("instruction is already cancelled")

        if instruction.status not in {
            InstructionStatus.DRAFT,
            InstructionStatus.SUBMITTED,
        }:
            raise InvalidStateTransitionError(
                "only DRAFT or SUBMITTED instructions can be cancelled"
            )

        details = {"reason": request.reason} if request and request.reason else {}
        await self._authorize(
            LifecycleAction.CANCEL,
            subject,
            instruction,
            bearer_token=bearer_token,
            session_id=session_id,
            record_security_event=True,
            security_event_details=details,
        )
        now = datetime.now(timezone.utc)
        instruction.status = InstructionStatus.CANCELLED
        instruction.cancelled_at = now
        saved = await self._persist_new_version(
            instruction,
            LifecycleAction.CANCEL,
            subject,
            details,
            bearer_token=bearer_token,
            session_id=session_id,
            skip_authorize=True,
        )
        return _to_response(saved)

    async def get(
        self,
        instruction_id: str,
        subject: Subject,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> InstructionResponse:
        record = await self.repository.get_current(instruction_id)
        record_view = self._should_record_view_security_event(subject)
        authorization = await self._authorize(
            LifecycleAction.VIEW,
            subject,
            record.instruction,
            bearer_token=bearer_token,
            session_id=session_id,
            record_security_event=record_view,
        )
        if record_view:
            await self._record_authorized_action(
                LifecycleAction.VIEW,
                subject,
                record.instruction,
                version_number=record.version_number,
                details=details_with_authorization(None, authorization),
            )
        return _to_response(record)

    async def list_versions(
        self,
        instruction_id: str,
        subject: Subject,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> list[InstructionResponse]:
        await self.get(
            instruction_id,
            subject,
            bearer_token=bearer_token,
            session_id=session_id,
        )
        records = await self.repository.list_versions(instruction_id)
        return [_to_response(record) for record in records]

    async def list(
        self,
        subject: Subject,
        *,
        owning_lob: str | None = None,
        status: str | None = None,
        limit: int = 100,
        include_cancelled: bool = False,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> list[InstructionResponse]:
        records = await self.repository.list_current(
            owning_lob=owning_lob, status=status, limit=limit
        )
        visible = []
        for record in records:
            if (
                not include_cancelled
                and record.instruction.status == InstructionStatus.CANCELLED
            ):
                continue
            try:
                record_view = self._should_record_view_security_event(subject)
                authorization = await self._authorize(
                    LifecycleAction.VIEW,
                    subject,
                    record.instruction,
                    bearer_token=bearer_token,
                    session_id=session_id,
                    record_security_event=record_view,
                )
            except PermissionError:
                continue
            if record_view:
                await self._record_authorized_action(
                    LifecycleAction.VIEW,
                    subject,
                    record.instruction,
                    version_number=record.version_number,
                    details=details_with_authorization(None, authorization),
                )
            visible.append(_to_response(record))
        return visible

    async def eligible_approvers(self, instruction_id: str) -> dict:
        record = await self.repository.get_current(instruction_id)
        instruction = record.instruction.model_dump(mode="json")
        await service_identity.ensure_logged_in()
        return await self.authz.eligible_instruction_approvers(
            instruction=instruction,
            service_token=service_identity.token,
            service_session_id=service_identity.session_id,
        )

    async def submit(
        self,
        instruction_id: str,
        subject: Subject,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> InstructionResponse:
        current = await self.repository.get_current(instruction_id)
        instruction = current.instruction.model_copy(deep=True)
        if instruction.status != InstructionStatus.DRAFT:
            raise InvalidStateTransitionError("only DRAFT instructions can be submitted")

        authorization = await self._authorize(
            LifecycleAction.SUBMIT,
            subject,
            instruction,
            bearer_token=bearer_token,
            session_id=session_id,
            record_security_event=True,
        )
        instruction.status = InstructionStatus.SUBMITTED
        instruction.submitted_at = datetime.utcnow()
        details = details_with_authorization(None, authorization)
        saved = await self._persist_new_version(
            instruction,
            LifecycleAction.SUBMIT,
            subject,
            details=details,
            bearer_token=bearer_token,
            session_id=session_id,
            skip_authorize=True,
        )
        return _to_response(saved)

    async def approve(
        self,
        instruction_id: str,
        subject: Subject,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> InstructionResponse:
        current = await self.repository.get_current(instruction_id)
        instruction = current.instruction.model_copy(deep=True)
        if instruction.status != InstructionStatus.SUBMITTED:
            raise InvalidStateTransitionError("only SUBMITTED instructions can be approved")

        authorization = await self._authorize(
            LifecycleAction.APPROVE,
            subject,
            instruction,
            bearer_token=bearer_token,
            session_id=session_id,
            record_security_event=True,
        )
        instruction.status = InstructionStatus.APPROVED
        instruction.approved_by = UserReference(
            user_id=subject.user_id,
            given_name=subject.given_name,
            family_name=subject.family_name,
            title=subject.title,
            lob=subject.lob,
            roles=subject.roles,
            supervisor_id=subject.supervisor_id,
        )
        instruction.approved_at = datetime.utcnow()
        details = details_with_authorization(None, authorization)
        saved = await self._persist_new_version(
            instruction,
            LifecycleAction.APPROVE,
            subject,
            details=details,
            bearer_token=bearer_token,
            session_id=session_id,
            skip_authorize=True,
        )
        return _to_response(saved)

    async def reject(
        self,
        instruction_id: str,
        subject: Subject,
        request: RejectInstructionRequest,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> InstructionResponse:
        current = await self.repository.get_current(instruction_id)
        instruction = current.instruction.model_copy(deep=True)
        if instruction.status != InstructionStatus.SUBMITTED:
            raise InvalidStateTransitionError("only SUBMITTED instructions can be rejected")

        authorization = await self._authorize(
            LifecycleAction.REJECT,
            subject,
            instruction,
            bearer_token=bearer_token,
            session_id=session_id,
            record_security_event=True,
            security_event_details={"reason": request.reason},
        )
        instruction.status = InstructionStatus.REJECTED
        instruction.rejected_by = UserReference(
            user_id=subject.user_id,
            given_name=subject.given_name,
            family_name=subject.family_name,
            title=subject.title,
            lob=subject.lob,
            roles=subject.roles,
            supervisor_id=subject.supervisor_id,
        )
        instruction.rejected_at = datetime.utcnow()
        instruction.rejection_reason = request.reason
        details = details_with_authorization({"reason": request.reason}, authorization)
        saved = await self._persist_new_version(
            instruction,
            LifecycleAction.REJECT,
            subject,
            details=details,
            bearer_token=bearer_token,
            session_id=session_id,
            skip_authorize=True,
        )
        return _to_response(saved)

    async def suspend(
        self,
        instruction_id: str,
        subject: Subject,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> InstructionResponse:
        current = await self.repository.get_current(instruction_id)
        instruction = current.instruction.model_copy(deep=True)
        if instruction.status != InstructionStatus.APPROVED:
            raise InvalidStateTransitionError(
                "only APPROVED instructions can be suspended"
            )

        authorization = await self._authorize(
            LifecycleAction.SUSPEND,
            subject,
            instruction,
            bearer_token=bearer_token,
            session_id=session_id,
            record_security_event=True,
        )
        instruction.status = InstructionStatus.SUSPENDED
        instruction.suspended_by = subject.user_id
        instruction.suspended_at = datetime.utcnow()
        details = details_with_authorization(None, authorization)
        saved = await self._persist_new_version(
            instruction,
            LifecycleAction.SUSPEND,
            subject,
            details=details,
            bearer_token=bearer_token,
            session_id=session_id,
            skip_authorize=True,
        )
        return _to_response(saved)

    async def reactivate(
        self,
        instruction_id: str,
        subject: Subject,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> InstructionResponse:
        current = await self.repository.get_current(instruction_id)
        instruction = current.instruction.model_copy(deep=True)
        if instruction.status != InstructionStatus.SUSPENDED:
            raise InvalidStateTransitionError("only SUSPENDED instructions can be reactivated")

        authorization = await self._authorize(
            LifecycleAction.REACTIVATE,
            subject,
            instruction,
            bearer_token=bearer_token,
            session_id=session_id,
            record_security_event=True,
        )
        instruction.status = InstructionStatus.APPROVED
        instruction.suspended_by = None
        instruction.suspended_at = None
        details = details_with_authorization(None, authorization)
        saved = await self._persist_new_version(
            instruction,
            LifecycleAction.REACTIVATE,
            subject,
            details=details,
            bearer_token=bearer_token,
            session_id=session_id,
            skip_authorize=True,
        )
        return _to_response(saved)

    async def use(
        self,
        instruction_id: str,
        subject: Subject,
        request: UseInstructionRequest,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> InstructionResponse:
        current = await self.repository.get_current(instruction_id)
        instruction = current.instruction.model_copy(deep=True)
        if instruction.status != InstructionStatus.APPROVED:
            raise InvalidStateTransitionError(
                "only APPROVED instructions can be used"
            )

        instruction.usage_count += 1
        instruction.last_used_at = datetime.utcnow()

        use_details = {
            "payment_reference": request.payment_reference,
            "end_to_end_identification": request.end_to_end_identification,
            "currency": instruction.currency,
        }
        authorization = await self._authorize(
            LifecycleAction.USE,
            subject,
            instruction,
            bearer_token=bearer_token,
            session_id=session_id,
            record_security_event=True,
            security_event_details=use_details,
        )

        if instruction.instruction_type == InstructionType.SINGLE_USE:
            instruction.status = InstructionStatus.USED
            instruction.used_by = request.payment_reference

        details = details_with_authorization(use_details, authorization)
        saved = await self._persist_new_version(
            instruction,
            LifecycleAction.USE,
            subject,
            details=details,
            skip_authorize=True,
        )
        return _to_response(saved)

    async def release_use(
        self,
        instruction_id: str,
        subject: Subject,
        request: ReleaseUseInstructionRequest,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> InstructionResponse:
        current = await self.repository.get_current(instruction_id)
        instruction = current.instruction.model_copy(deep=True)
        if instruction.instruction_type != InstructionType.SINGLE_USE:
            raise InvalidStateTransitionError(
                "only SINGLE_USE instructions support release"
            )
        if instruction.status != InstructionStatus.USED:
            raise InvalidStateTransitionError(
                "only USED instructions can be released"
            )
        if instruction.used_by != request.payment_reference:
            raise InvalidStateTransitionError(
                "instruction used_by does not match the releasing payment"
            )

        release_details = {
            "payment_reference": request.payment_reference,
        }
        authorization = await self._authorize(
            LifecycleAction.RELEASE_USE,
            subject,
            instruction,
            bearer_token=bearer_token,
            session_id=session_id,
            record_security_event=True,
            security_event_details=release_details,
        )

        instruction.status = InstructionStatus.APPROVED
        instruction.used_by = None
        if instruction.usage_count > 0:
            instruction.usage_count -= 1

        details = details_with_authorization(release_details, authorization)
        saved = await self._persist_new_version(
            instruction,
            LifecycleAction.RELEASE_USE,
            subject,
            details=details,
            skip_authorize=True,
        )
        return _to_response(saved)
