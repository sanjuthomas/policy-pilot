from fastapi import APIRouter, Depends, Header, HTTPException, Query

from inst.dependencies import get_compliance_subject, get_subject
from inst.evaluate_tokens import (
    bind_evaluate_token_context,
    reset_evaluate_token_context,
    resolve_evaluate_token_context,
)
from inst.models.api import (
    CancelInstructionRequest,
    CreateInstructionRequest,
    InstructionEligibleApproversResponse,
    InstructionResponse,
    RejectInstructionRequest,
    ReleaseUseInstructionRequest,
    Subject,
    UpdateInstructionRequest,
    UseInstructionRequest,
)
from inst.repository import ConcurrentModificationError, InstructionNotFoundError
from inst.service import InstructionService, InvalidStateTransitionError

router = APIRouter(prefix="/instructions", tags=["instructions"])


def get_service() -> InstructionService:
    return InstructionService()


def _bind_tokens(
    authorization: str | None,
    x_session_id: str | None,
    x_on_behalf_of: str | None,
    x_on_behalf_of_session_id: str | None,
):
    ctx = resolve_evaluate_token_context(
        authorization=authorization,
        x_session_id=x_session_id,
        x_on_behalf_of=x_on_behalf_of,
        x_on_behalf_of_session_id=x_on_behalf_of_session_id,
    )
    return bind_evaluate_token_context(ctx), ctx


@router.post("", response_model=InstructionResponse, status_code=201)
async def create_instruction(
    request: CreateInstructionRequest,
    subject: Subject = Depends(get_subject),
    service: InstructionService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> InstructionResponse:
    token, ctx = _bind_tokens(
        authorization, x_session_id, x_on_behalf_of, x_on_behalf_of_session_id
    )
    try:
        return await service.create(
            request,
            subject,
            bearer_token=ctx.user_token,
            session_id=ctx.user_session_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        reset_evaluate_token_context(token)


@router.get("", response_model=list[InstructionResponse])
async def list_instructions(
    owning_lob: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    subject: Subject = Depends(get_subject),
    service: InstructionService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> list[InstructionResponse]:
    token, ctx = _bind_tokens(
        authorization, x_session_id, x_on_behalf_of, x_on_behalf_of_session_id
    )
    try:
        return await service.list(
            subject,
            owning_lob=owning_lob,
            status=status,
            limit=limit,
            bearer_token=ctx.user_token,
            session_id=ctx.user_session_id,
        )
    finally:
        reset_evaluate_token_context(token)


@router.get("/{instruction_id}/versions", response_model=list[InstructionResponse])
async def list_instruction_versions(
    instruction_id: str,
    subject: Subject = Depends(get_subject),
    service: InstructionService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> list[InstructionResponse]:
    token, ctx = _bind_tokens(
        authorization, x_session_id, x_on_behalf_of, x_on_behalf_of_session_id
    )
    try:
        return await service.list_versions(
            instruction_id,
            subject,
            bearer_token=ctx.user_token,
            session_id=ctx.user_session_id,
        )
    except InstructionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="instruction not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    finally:
        reset_evaluate_token_context(token)


@router.put("/{instruction_id}", response_model=InstructionResponse)
async def update_instruction(
    instruction_id: str,
    request: UpdateInstructionRequest,
    subject: Subject = Depends(get_subject),
    service: InstructionService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> InstructionResponse:
    token, ctx = _bind_tokens(
        authorization, x_session_id, x_on_behalf_of, x_on_behalf_of_session_id
    )
    try:
        return await service.update(
            instruction_id,
            request,
            subject,
            bearer_token=ctx.user_token,
            session_id=ctx.user_session_id,
        )
    except InstructionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="instruction not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ConcurrentModificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        reset_evaluate_token_context(token)


@router.get("/{instruction_id}", response_model=InstructionResponse)
async def get_instruction(
    instruction_id: str,
    subject: Subject = Depends(get_subject),
    service: InstructionService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> InstructionResponse:
    token, ctx = _bind_tokens(
        authorization, x_session_id, x_on_behalf_of, x_on_behalf_of_session_id
    )
    try:
        return await service.get(
            instruction_id,
            subject,
            bearer_token=ctx.user_token,
            session_id=ctx.user_session_id,
        )
    except InstructionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="instruction not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    finally:
        reset_evaluate_token_context(token)


@router.post("/{instruction_id}/eligible-approvers", response_model=InstructionEligibleApproversResponse)
async def instruction_eligible_approvers(
    instruction_id: str,
    _subject: Subject = Depends(get_compliance_subject),
    service: InstructionService = Depends(get_service),
) -> InstructionEligibleApproversResponse:
    try:
        data = await service.eligible_approvers(instruction_id)
        return InstructionEligibleApproversResponse.model_validate(data)
    except InstructionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="instruction not found") from exc


@router.post("/{instruction_id}/submit", response_model=InstructionResponse)
async def submit_instruction(
    instruction_id: str,
    subject: Subject = Depends(get_subject),
    service: InstructionService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> InstructionResponse:
    return await _lifecycle_action(
        service.submit,
        instruction_id,
        subject,
        authorization=authorization,
        x_session_id=x_session_id,
        x_on_behalf_of=x_on_behalf_of,
        x_on_behalf_of_session_id=x_on_behalf_of_session_id,
    )


@router.post("/{instruction_id}/approve", response_model=InstructionResponse)
async def approve_instruction(
    instruction_id: str,
    subject: Subject = Depends(get_subject),
    service: InstructionService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> InstructionResponse:
    return await _lifecycle_action(
        service.approve,
        instruction_id,
        subject,
        authorization=authorization,
        x_session_id=x_session_id,
        x_on_behalf_of=x_on_behalf_of,
        x_on_behalf_of_session_id=x_on_behalf_of_session_id,
    )


@router.post("/{instruction_id}/cancel", response_model=InstructionResponse)
async def cancel_instruction(
    instruction_id: str,
    request: CancelInstructionRequest | None = None,
    subject: Subject = Depends(get_subject),
    service: InstructionService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> InstructionResponse:
    return await _lifecycle_action(
        service.cancel,
        instruction_id,
        subject,
        request,
        authorization=authorization,
        x_session_id=x_session_id,
        x_on_behalf_of=x_on_behalf_of,
        x_on_behalf_of_session_id=x_on_behalf_of_session_id,
    )


@router.post("/{instruction_id}/reject", response_model=InstructionResponse)
async def reject_instruction(
    instruction_id: str,
    request: RejectInstructionRequest,
    subject: Subject = Depends(get_subject),
    service: InstructionService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> InstructionResponse:
    return await _lifecycle_action(
        service.reject,
        instruction_id,
        subject,
        request,
        authorization=authorization,
        x_session_id=x_session_id,
        x_on_behalf_of=x_on_behalf_of,
        x_on_behalf_of_session_id=x_on_behalf_of_session_id,
    )


@router.post("/{instruction_id}/suspend", response_model=InstructionResponse)
async def suspend_instruction(
    instruction_id: str,
    subject: Subject = Depends(get_subject),
    service: InstructionService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> InstructionResponse:
    return await _lifecycle_action(
        service.suspend,
        instruction_id,
        subject,
        authorization=authorization,
        x_session_id=x_session_id,
        x_on_behalf_of=x_on_behalf_of,
        x_on_behalf_of_session_id=x_on_behalf_of_session_id,
    )


@router.post("/{instruction_id}/reactivate", response_model=InstructionResponse)
async def reactivate_instruction(
    instruction_id: str,
    subject: Subject = Depends(get_subject),
    service: InstructionService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> InstructionResponse:
    return await _lifecycle_action(
        service.reactivate,
        instruction_id,
        subject,
        authorization=authorization,
        x_session_id=x_session_id,
        x_on_behalf_of=x_on_behalf_of,
        x_on_behalf_of_session_id=x_on_behalf_of_session_id,
    )


@router.post("/{instruction_id}/use", response_model=InstructionResponse)
async def use_instruction(
    instruction_id: str,
    request: UseInstructionRequest,
    subject: Subject = Depends(get_subject),
    service: InstructionService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> InstructionResponse:
    return await _lifecycle_action(
        service.use,
        instruction_id,
        subject,
        request,
        authorization=authorization,
        x_session_id=x_session_id,
        x_on_behalf_of=x_on_behalf_of,
        x_on_behalf_of_session_id=x_on_behalf_of_session_id,
    )


@router.post("/{instruction_id}/release-use", response_model=InstructionResponse)
async def release_use_instruction(
    instruction_id: str,
    request: ReleaseUseInstructionRequest,
    subject: Subject = Depends(get_subject),
    service: InstructionService = Depends(get_service),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> InstructionResponse:
    return await _lifecycle_action(
        service.release_use,
        instruction_id,
        subject,
        request,
        authorization=authorization,
        x_session_id=x_session_id,
        x_on_behalf_of=x_on_behalf_of,
        x_on_behalf_of_session_id=x_on_behalf_of_session_id,
    )


async def _lifecycle_action(
    handler,
    instruction_id: str,
    subject: Subject,
    *args,
    authorization: str | None = None,
    x_session_id: str | None = None,
    x_on_behalf_of: str | None = None,
    x_on_behalf_of_session_id: str | None = None,
):
    token, ctx = _bind_tokens(
        authorization, x_session_id, x_on_behalf_of, x_on_behalf_of_session_id
    )
    try:
        return await handler(
            instruction_id,
            subject,
            *args,
            bearer_token=ctx.user_token,
            session_id=ctx.user_session_id,
        )
    except InstructionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="instruction not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ConcurrentModificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        reset_evaluate_token_context(token)
