from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from authz.instruction_opa import (
    instruction_opa_context_after_submission,
    instruction_opa_context_for_approval_eligibility,
)
from authz.models import (
    EligibleApprover,
    InstructionEligibleApproversEvaluateRequest,
    InstructionEligibleApproversResponse,
    PaymentEligibilityContext,
    PaymentEligibleApproversEvaluateRequest,
    PaymentEligibleApproversResponse,
    PaymentEligibleSubmittersResponse,
    PaymentRecord,
    UserReference,
)
from authz.opa import OpaClient
from authz.payment_opa import (
    payment_approval_blocked_reason,
    payment_prospective_instruction_status,
    payment_submit_blocked_reason,
)
from authz.user_directory import UserDirectory


class EligibilityService:
    def __init__(
        self,
        *,
        users: UserDirectory,
        opa: OpaClient,
    ) -> None:
        self._users = users
        self._opa = opa

    async def _eligible_instruction_approvers_for_context(
        self,
        candidates: list,
        *,
        opa_instruction: dict[str, Any],
        opa_account: dict[str, Any],
    ) -> list[EligibleApprover]:
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
        return eligible

    @staticmethod
    def _payment_record(context: PaymentEligibilityContext) -> PaymentRecord:
        return PaymentRecord(
            payment_id=context.payment_id,
            instruction_id=context.instruction_id,
            instruction_version=context.instruction_version,
            status=context.status,
            amount=context.amount,
            currency=context.currency,
            owning_lob=context.owning_lob,
            instruction_type=context.instruction_type,
            created_by=UserReference(
                user_id=context.created_by_user_id,
                supervisor_id=context.created_by_supervisor_id,
            ),
        )

    async def _eligible_payment_approvers_for_context(
        self,
        candidates: list,
        *,
        payment: PaymentRecord,
        instruction_end_date: str,
        instruction_status: str,
    ) -> list[EligibleApprover]:
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
        return eligible

    async def eligible_approvers_for_payment(
        self,
        request: PaymentEligibleApproversEvaluateRequest,
    ) -> PaymentEligibleApproversResponse:
        payment = self._payment_record(request.payment)
        instruction_status = request.instruction_status
        instruction_end_date = request.instruction_end_date
        approval_blocked_reason = payment_approval_blocked_reason(
            payment.status,
            instruction_status,
            instruction_id=payment.instruction_id,
            instruction_type=request.payment.instruction_type,
            payment_instruction_type=request.payment.instruction_type,
        )

        candidates = self._users.funding_approver_candidates(payment.owning_lob)
        eligible = await self._eligible_payment_approvers_for_context(
            candidates,
            payment=payment,
            instruction_end_date=instruction_end_date,
            instruction_status=instruction_status,
        )

        prospective_eligible: list[EligibleApprover] = []
        prospective_instruction_status = payment_prospective_instruction_status(
            instruction_status,
            instruction_type=request.payment.instruction_type,
            payment_instruction_type=request.payment.instruction_type,
        )
        if prospective_instruction_status and payment.status == "DRAFT":
            prospective_eligible = await self._eligible_payment_approvers_for_context(
                candidates,
                payment=payment,
                instruction_end_date=instruction_end_date,
                instruction_status=prospective_instruction_status,
            )

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
            prospective_eligible=prospective_eligible,
            candidates_evaluated=len(candidates),
            approval_blocked_reason=approval_blocked_reason,
        )

    async def _eligible_payment_submitters_for_context(
        self,
        candidates: list,
        *,
        payment: PaymentRecord,
        instruction_end_date: str,
        instruction_status: str,
    ) -> list[EligibleApprover]:
        eligible: list[EligibleApprover] = []
        for candidate in candidates:
            allowed, basis = await self._opa.can_submit_payment(
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
        return eligible

    async def eligible_submitters_for_payment(
        self,
        request: PaymentEligibleApproversEvaluateRequest,
    ) -> PaymentEligibleSubmittersResponse:
        payment = self._payment_record(request.payment)
        instruction_status = request.instruction_status
        instruction_end_date = request.instruction_end_date
        submit_blocked_reason = payment_submit_blocked_reason(
            payment.status,
            instruction_status,
            instruction_id=payment.instruction_id,
        )

        candidates = self._users.payment_submitter_candidates(payment.owning_lob)
        eligible: list[EligibleApprover] = []
        if submit_blocked_reason is None:
            eligible = await self._eligible_payment_submitters_for_context(
                candidates,
                payment=payment,
                instruction_end_date=instruction_end_date,
                instruction_status=instruction_status,
            )

        return PaymentEligibleSubmittersResponse(
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
            submit_blocked_reason=submit_blocked_reason,
        )

    async def eligible_approvers_for_instruction(
        self,
        request: InstructionEligibleApproversEvaluateRequest,
    ) -> InstructionEligibleApproversResponse:
        instruction = request.instruction
        instruction_status = str(instruction.get("status") or "")
        instruction_type = str(instruction.get("instruction_type") or "")
        owning_lob = str(instruction.get("owning_lob") or "")
        created_by = instruction.get("created_by") or {}
        instruction_id = str(instruction.get("instruction_id") or "")
        opa_instruction, opa_account, approval_blocked_reason = (
            instruction_opa_context_for_approval_eligibility(instruction)
        )

        candidates = self._users.instruction_approver_candidates(owning_lob)
        eligible = await self._eligible_instruction_approvers_for_context(
            candidates,
            opa_instruction=opa_instruction,
            opa_account=opa_account,
        )

        prospective_eligible: list[EligibleApprover] = []
        prospective_opa, prospective_account = instruction_opa_context_after_submission(
            instruction
        )
        if prospective_opa is not None and prospective_account is not None:
            prospective_eligible = await self._eligible_instruction_approvers_for_context(
                candidates,
                opa_instruction=prospective_opa,
                opa_account=prospective_account,
            )

        return InstructionEligibleApproversResponse(
            instruction_id=instruction_id,
            instruction_status=instruction_status,
            instruction_type=instruction_type,
            owning_lob=owning_lob,
            created_by_user_id=str(created_by.get("user_id") or ""),
            created_by_title=str(created_by.get("title") or ""),
            evaluated_at=datetime.now(UTC).isoformat(),
            eligible=eligible,
            prospective_eligible=prospective_eligible,
            candidates_evaluated=len(candidates),
            approval_blocked_reason=approval_blocked_reason,
        )
