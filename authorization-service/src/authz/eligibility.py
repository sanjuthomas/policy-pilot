from __future__ import annotations

from datetime import UTC, datetime

from authz.ilm_client import IlmClient, InstructionNotFoundError
from authz.instruction_opa import build_instruction_opa_context
from authz.models import (
    EligibleApprover,
    InstructionEligibleApproversResponse,
    PaymentEligibleApproversResponse,
)
from authz.opa import OpaClient
from authz.payment_repository import PaymentNotFoundError, PaymentRepository
from authz.user_directory import UserDirectory


class EligibilityService:
    def __init__(
        self,
        *,
        payments: PaymentRepository,
        users: UserDirectory,
        ilm: IlmClient,
        opa: OpaClient,
    ) -> None:
        self._payments = payments
        self._users = users
        self._ilm = ilm
        self._opa = opa

    async def eligible_approvers_for_payment(self, payment_id: str) -> PaymentEligibleApproversResponse:
        try:
            payment = await self._payments.get_payment(payment_id)
        except PaymentNotFoundError as exc:
            raise exc

        try:
            instruction = await self._ilm.get_instruction(payment.instruction_id)
        except InstructionNotFoundError as exc:
            raise exc

        instruction_status = str(instruction.get("status") or "")
        instruction_end_date = str(instruction.get("end_date") or "")

        candidates = self._users.funding_approver_candidates(payment.owning_lob)
        eligible: list[EligibleApprover] = []

        for candidate in candidates:
            allowed, basis = await self._opa.can_approve_payment(
                candidate,
                payment,
                instruction_end_date=instruction_end_date,
                instruction_status=instruction_status,
            )
            if allowed:
                eligible.append(
                    EligibleApprover(
                        user_id=candidate.user_id,
                        display_name=candidate.display_name,
                        title=candidate.title,
                        allow_basis=basis,
                    )
                )

        eligible.sort(key=lambda row: row.display_name)

        return PaymentEligibleApproversResponse(
            payment_id=payment.payment_id,
            instruction_id=payment.instruction_id,
            payment_status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            owning_lob=payment.owning_lob,
            instruction_status=instruction_status,
            evaluated_at=datetime.now(UTC).isoformat(),
            eligible=eligible,
            candidates_evaluated=len(candidates),
        )

    async def eligible_approvers_for_instruction(
        self, instruction_id: str
    ) -> InstructionEligibleApproversResponse:
        try:
            instruction = await self._ilm.get_instruction(instruction_id)
        except InstructionNotFoundError as exc:
            raise exc

        instruction_status = str(instruction.get("status") or "")
        instruction_type = str(instruction.get("instruction_type") or "")
        owning_lob = str(instruction.get("owning_lob") or "")
        created_by = instruction.get("created_by") or {}
        opa_instruction, opa_account = build_instruction_opa_context(instruction)

        candidates = self._users.instruction_approver_candidates(owning_lob)
        eligible: list[EligibleApprover] = []

        for candidate in candidates:
            allowed, basis = await self._opa.can_approve_instruction(
                candidate,
                opa_instruction=opa_instruction,
                opa_account=opa_account,
            )
            if allowed:
                eligible.append(
                    EligibleApprover(
                        user_id=candidate.user_id,
                        display_name=candidate.display_name,
                        title=candidate.title,
                        allow_basis=basis,
                    )
                )

        eligible.sort(key=lambda row: row.display_name)

        return InstructionEligibleApproversResponse(
            instruction_id=instruction_id,
            instruction_status=instruction_status,
            instruction_type=instruction_type,
            owning_lob=owning_lob,
            created_by_user_id=str(created_by.get("user_id") or ""),
            created_by_title=str(created_by.get("title") or ""),
            evaluated_at=datetime.now(UTC).isoformat(),
            eligible=eligible,
            candidates_evaluated=len(candidates),
        )
