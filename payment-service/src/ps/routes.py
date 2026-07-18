import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query

from ps.dependencies import get_compliance_subject, get_subject
from ps.evaluate_tokens import resolve_evaluate_token_context
from ps.instruction_client import InstructionNotFoundError
from ps.models.api import (
    CancelPaymentRequest,
    CreatePaymentRequest,
    PaymentEligibleApproversResponse,
    PaymentResponse,
    RejectPaymentRequest,
    Subject,
    UpdatePaymentRequest,
)
from ps.repository import ConcurrentModificationError
from ps.service import InvalidStateTransitionError, PaymentService
from ps.storage import VersionedPayment

router = APIRouter(prefix="/payments", tags=["payments"])


def get_service() -> PaymentService:
    return PaymentService()


def _user_tokens(
    authorization: str | None,
    x_session_id: str | None,
    x_on_behalf_of: str | None,
    x_on_behalf_of_session_id: str | None,
) -> tuple[str | None, str | None]:
    ctx = resolve_evaluate_token_context(
        authorization=authorization,
        x_session_id=x_session_id,
        x_on_behalf_of=x_on_behalf_of,
        x_on_behalf_of_session_id=x_on_behalf_of_session_id,
    )
    return ctx.user_token, ctx.user_session_id


def _fmt_datetime(value) -> str | None:
    if value is None:
        return None
    return value.isoformat() + "Z"


def _to_response(record: VersionedPayment) -> PaymentResponse:
    from ps.constants import PAYMENT_CURRENT_OUT

    payment = record.payment
    return PaymentResponse(
        payment_id=payment.payment_id,
        version_number=record.version_number,
        record_in=_fmt_datetime(record.valid_in) or "",
        record_out=(
            PAYMENT_CURRENT_OUT
            if record.valid_out is None
            else _fmt_datetime(record.valid_out)
        ),
        instruction_id=payment.instruction_id,
        instruction_version=payment.instruction_version,
        status=payment.status.value,
        amount=payment.amount,
        currency=payment.currency,
        value_date=payment.value_date,
        owning_lob=payment.owning_lob,
        instruction_type=payment.instruction_type,
        created_by=payment.created_by,
        submitted_by=payment.submitted_by,
        approved_by=payment.approved_by,
        rejected_by=payment.rejected_by,
        cancelled_by=payment.cancelled_by,
        rejection_reason=payment.rejection_reason,
        cancellation_reason=payment.cancellation_reason,
        created_at=_fmt_datetime(payment.created_at) or "",
        updated_at=_fmt_datetime(payment.updated_at) or "",
        submitted_at=_fmt_datetime(payment.submitted_at),
        approved_at=_fmt_datetime(payment.approved_at),
        rejected_at=_fmt_datetime(payment.rejected_at),
        cancelled_at=_fmt_datetime(payment.cancelled_at),
        lifecycle_events=payment.lifecycle_events,
    )


@router.post("", response_model=PaymentResponse, status_code=201)
async def create_payment(
    request: CreatePaymentRequest,
    subject: Subject = Depends(get_subject),
    service: PaymentService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> PaymentResponse:
    user_token, user_session_id = _user_tokens(
        authorization, x_session_id, x_on_behalf_of, x_on_behalf_of_session_id
    )
    try:
        record = await service.create(
            instruction_id=request.instruction_id,
            value_date=request.value_date,
            amount=request.amount,
            subject=subject,
            bearer_token=user_token,
            session_id=user_session_id,
        )
        return _to_response(record)
    except InstructionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("", response_model=list[PaymentResponse])
async def list_payments(
    instruction_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    subject: Subject = Depends(get_subject),
    service: PaymentService = Depends(get_service),
) -> list[PaymentResponse]:
    records = await service.list(
        subject,
        instruction_id=instruction_id,
        status=status,
        limit=limit,
    )
    return [_to_response(record) for record in records]


@router.put("/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    payment_id: str,
    request: UpdatePaymentRequest,
    subject: Subject = Depends(get_subject),
    service: PaymentService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> PaymentResponse:
    user_token, user_session_id = _user_tokens(
        authorization, x_session_id, x_on_behalf_of, x_on_behalf_of_session_id
    )
    try:
        record = await service.update(
            payment_id,
            instruction_id=request.instruction_id,
            value_date=request.value_date,
            amount=request.amount,
            subject=subject,
            bearer_token=user_token,
            session_id=user_session_id,
        )
        return _to_response(record)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ConcurrentModificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    subject: Subject = Depends(get_subject),
    service: PaymentService = Depends(get_service),
) -> PaymentResponse:
    try:
        return _to_response(await service.get(payment_id, subject))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{payment_id}/submit", response_model=PaymentResponse)
async def submit_payment(
    payment_id: str,
    subject: Subject = Depends(get_subject),
    service: PaymentService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> PaymentResponse:
    user_token, user_session_id = _user_tokens(
        authorization, x_session_id, x_on_behalf_of, x_on_behalf_of_session_id
    )
    return await _lifecycle_action(
        service.submit,
        payment_id,
        subject,
        bearer_token=user_token,
        session_id=user_session_id,
    )


@router.post("/{payment_id}/approve", response_model=PaymentResponse)
async def approve_payment(
    payment_id: str,
    subject: Subject = Depends(get_subject),
    service: PaymentService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> PaymentResponse:
    user_token, user_session_id = _user_tokens(
        authorization, x_session_id, x_on_behalf_of, x_on_behalf_of_session_id
    )
    return await _lifecycle_action(
        service.approve,
        payment_id,
        subject,
        bearer_token=user_token,
        session_id=user_session_id,
    )


@router.post("/{payment_id}/reject", response_model=PaymentResponse)
async def reject_payment(
    payment_id: str,
    request: RejectPaymentRequest,
    subject: Subject = Depends(get_subject),
    service: PaymentService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> PaymentResponse:
    user_token, user_session_id = _user_tokens(
        authorization, x_session_id, x_on_behalf_of, x_on_behalf_of_session_id
    )
    return await _lifecycle_action(
        service.reject,
        payment_id,
        subject,
        request,
        bearer_token=user_token,
        session_id=user_session_id,
    )


@router.post("/{payment_id}/cancel", response_model=PaymentResponse)
async def cancel_payment(
    payment_id: str,
    request: CancelPaymentRequest | None = None,
    subject: Subject = Depends(get_subject),
    service: PaymentService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> PaymentResponse:
    user_token, user_session_id = _user_tokens(
        authorization, x_session_id, x_on_behalf_of, x_on_behalf_of_session_id
    )
    return await _lifecycle_action(
        service.cancel,
        payment_id,
        subject,
        request,
        bearer_token=user_token,
        session_id=user_session_id,
    )


@router.post("/{payment_id}/eligible-approvers", response_model=PaymentEligibleApproversResponse)
async def payment_eligible_approvers(
    payment_id: str,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
    _subject: Subject = Depends(get_compliance_subject),
    service: PaymentService = Depends(get_service),
) -> PaymentEligibleApproversResponse:
    user_token, user_session_id = _user_tokens(
        authorization, x_session_id, x_on_behalf_of, x_on_behalf_of_session_id
    )
    try:
        data = await service.eligible_approvers(
            payment_id,
            bearer_token=user_token,
            session_id=user_session_id,
        )
        return PaymentEligibleApproversResponse.model_validate(data)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InstructionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.text,
        ) from exc


async def _lifecycle_action(
    handler,
    payment_id: str,
    subject: Subject,
    *args,
    bearer_token: str | None = None,
    session_id: str | None = None,
):
    try:
        record = await handler(
            payment_id,
            subject,
            *args,
            bearer_token=bearer_token,
            session_id=session_id,
        )
        return _to_response(record)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ConcurrentModificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
