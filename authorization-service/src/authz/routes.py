from fastapi import APIRouter, Depends, HTTPException

from authz.dependencies import get_compliance_subject
from authz.eligibility import EligibilityService
from authz.ilm_client import InstructionNotFoundError
from authz.models import (
    InstructionEligibleApproversResponse,
    PaymentEligibleApproversResponse,
    Subject,
)
from authz.payment_repository import PaymentNotFoundError

router = APIRouter()


def _eligibility_service() -> EligibilityService:
    from authz.main import eligibility_service

    if eligibility_service is None:
        raise HTTPException(status_code=503, detail="eligibility service not ready")
    return eligibility_service


@router.post(
    "/payments/{payment_id}/eligible-approvers",
    response_model=PaymentEligibleApproversResponse,
)
async def payment_eligible_approvers(
    payment_id: str,
    _subject: Subject = Depends(get_compliance_subject),
    service: EligibilityService = Depends(_eligibility_service),
) -> PaymentEligibleApproversResponse:
    try:
        return await service.eligible_approvers_for_payment(payment_id)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InstructionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/instructions/{instruction_id}/eligible-approvers",
    response_model=InstructionEligibleApproversResponse,
)
async def instruction_eligible_approvers(
    instruction_id: str,
    _subject: Subject = Depends(get_compliance_subject),
    service: EligibilityService = Depends(_eligibility_service),
) -> InstructionEligibleApproversResponse:
    try:
        return await service.eligible_approvers_for_instruction(instruction_id)
    except InstructionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
