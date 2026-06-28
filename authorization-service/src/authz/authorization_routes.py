from fastapi import APIRouter, Depends, Header, HTTPException

from authz.evaluate_dependencies import get_service_caller, resolve_evaluate_subject
from authz.models import (
    InstructionEvaluateRequest,
    PaymentEvaluateRequest,
    PolicyDecisionResponse,
    Subject,
)
from authz.opa import OpaClient

router = APIRouter(prefix="/authorization", tags=["authorization"])


def _opa_client() -> OpaClient:
    return OpaClient()


def _parse_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authorization Bearer token required")
    return authorization.split(" ", 1)[1].strip()


def _to_response(decision) -> PolicyDecisionResponse:
    return PolicyDecisionResponse(
        allowed=decision.allowed,
        allow_basis=list(decision.allow_basis),
        violations=list(decision.violations),
        is_alert=decision.is_alert,
    )


@router.post("/instructions/evaluate", response_model=PolicyDecisionResponse)
async def evaluate_instruction(
    request: InstructionEvaluateRequest,
    _service_caller: Subject = Depends(get_service_caller),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
    opa: OpaClient = Depends(_opa_client),
) -> PolicyDecisionResponse:
    subject = resolve_evaluate_subject(
        service_token=_parse_bearer(authorization),
        service_session_id=x_session_id,
        x_on_behalf_of=x_on_behalf_of,
        x_on_behalf_of_session_id=x_on_behalf_of_session_id,
        inline_subject=request.subject,
    )
    try:
        decision = await opa.evaluate_instruction(
            action=request.action,
            subject=subject,
            instruction=request.instruction,
            account=request.account,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"opa evaluation failed: {exc}") from exc
    return _to_response(decision)


@router.post("/payments/evaluate", response_model=PolicyDecisionResponse)
async def evaluate_payment(
    request: PaymentEvaluateRequest,
    _service_caller: Subject = Depends(get_service_caller),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
    opa: OpaClient = Depends(_opa_client),
) -> PolicyDecisionResponse:
    subject = resolve_evaluate_subject(
        service_token=_parse_bearer(authorization),
        service_session_id=x_session_id,
        x_on_behalf_of=x_on_behalf_of,
        x_on_behalf_of_session_id=x_on_behalf_of_session_id,
        inline_subject=request.subject,
    )
    try:
        decision = await opa.evaluate_payment(
            action=request.action,
            subject=subject,
            payment=request.payment,
            instruction_end_date=request.instruction_end_date,
            instruction_status=request.instruction_status,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"opa evaluation failed: {exc}") from exc
    return _to_response(decision)
