from fastapi import APIRouter, Depends, Header, HTTPException, Query

from authz.dependencies import get_compliance_subject
from authz.directory import build_group_member_rows, build_user_directory_rows
from authz.evaluate_dependencies import get_service_caller, resolve_evaluate_subject
from authz.models import (
    GroupMembersResponse,
    InstructionEligibleApproversEvaluateRequest,
    InstructionEligibleApproversResponse,
    InstructionEvaluateRequest,
    PaymentAmountLimitsResponse,
    PaymentEligibleApproversEvaluateRequest,
    PaymentEligibleApproversResponse,
    PaymentEvaluateRequest,
    PersonPermissionSummaryResponse,
    PolicyDecisionResponse,
    PolicyRequirement,
    PolicySummaryResponse,
    Subject,
)
from authz.opa import OpaClient
from authz.permission_summary import (
    build_person_permission_summary,
    filter_directory_rows,
)

router = APIRouter(prefix="/authorization", tags=["authorization"])


def _eligibility_service():
    from authz.main import eligibility_service

    if eligibility_service is None:
        raise HTTPException(status_code=503, detail="eligibility service not ready")
    return eligibility_service


def _user_directory():
    from authz.main import user_directory

    if user_directory is None:
        raise HTTPException(status_code=503, detail="user directory not ready")
    return user_directory


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


@router.get("/groups/{group}/members", response_model=GroupMembersResponse)
async def list_group_members(
    group: str,
    role: str | None = Query(default=None, description="Optional role filter"),
    covering_lob: str | None = Query(
        default=None,
        description="Optional desk filter — member must list this LOB in covering_lobs",
    ),
    _subject: Subject = Depends(get_compliance_subject),
    directory=Depends(_user_directory),
) -> GroupMembersResponse:
    members = build_group_member_rows(
        directory.members_of_group(group, role=role, covering_lob=covering_lob)
    )
    return GroupMembersResponse(group=group.strip(), count=len(members), members=members)


@router.get("/policy-summary", response_model=PolicySummaryResponse)
async def get_policy_summary(
    domain: str = Query(
        ...,
        description="Policy domain: payment or instruction",
    ),
    action: str = Query(
        default="APPROVE",
        description="Lifecycle action to summarize (default APPROVE)",
    ),
    _subject: Subject = Depends(get_compliance_subject),
    opa: OpaClient = Depends(_opa_client),
) -> PolicySummaryResponse:
    normalized_domain = domain.strip().lower()
    if normalized_domain not in {"payment", "instruction"}:
        raise HTTPException(
            status_code=400,
            detail="domain must be 'payment' or 'instruction'",
        )
    normalized_action = action.strip().upper()
    if not normalized_action:
        raise HTTPException(status_code=400, detail="action is required")

    try:
        catalog = await opa.fetch_policy_summary(normalized_domain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"opa policy_summary failed: {exc}",
        ) from exc

    actions = catalog.get("actions") if isinstance(catalog, dict) else None
    if not isinstance(actions, dict):
        raise HTTPException(status_code=503, detail="OPA policy_summary missing actions")

    entry = actions.get(normalized_action)
    if not isinstance(entry, dict):
        available = ", ".join(sorted(str(key) for key in actions))
        raise HTTPException(
            status_code=404,
            detail=(
                f"action '{normalized_action}' not found for domain '{normalized_domain}' "
                f"(available: {available})"
            ),
        )

    requirements: list[PolicyRequirement] = []
    for item in entry.get("requires") or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        value = str(item.get("value") or "").strip()
        if kind and value:
            requirements.append(PolicyRequirement(kind=kind, value=value))

    return PolicySummaryResponse(
        domain=str(catalog.get("domain") or normalized_domain),
        action=normalized_action,
        title=str(entry.get("title") or normalized_action),
        narrative=str(entry.get("narrative") or ""),
        requires=requirements,
        source="opa",
    )


@router.get("/payment-amount-limits", response_model=PaymentAmountLimitsResponse)
async def get_payment_amount_limits(
    _subject: Subject = Depends(get_compliance_subject),
    opa: OpaClient = Depends(_opa_client),
) -> PaymentAmountLimitsResponse:
    """Return OPA club ceilings + absolute payment limit (policy metadata)."""
    try:
        catalog = await opa.fetch_payment_amount_limits()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"opa amount_limits_catalog failed: {exc}",
        ) from exc

    absolute_raw = catalog.get("absolute_limit")
    clubs_raw = catalog.get("club_limits")
    if absolute_raw is None or not isinstance(clubs_raw, dict) or not clubs_raw:
        raise HTTPException(
            status_code=503,
            detail="OPA amount_limits_catalog missing absolute_limit or club_limits",
        )

    club_limits: dict[str, float] = {}
    for key, value in clubs_raw.items():
        name = str(key).strip()
        if not name:
            continue
        try:
            club_limits[name] = float(value)
        except (TypeError, ValueError):
            continue
    if not club_limits:
        raise HTTPException(
            status_code=503,
            detail="OPA amount_limits_catalog has no usable club_limits",
        )

    try:
        absolute_limit = float(absolute_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="OPA amount_limits_catalog absolute_limit is not numeric",
        ) from exc

    return PaymentAmountLimitsResponse(
        absolute_limit=absolute_limit,
        club_limits=club_limits,
        source="opa",
    )


@router.get("/users/permission-summary", response_model=PersonPermissionSummaryResponse)
async def get_person_permission_summary(
    q: str = Query(..., min_length=1, description="User id, login, or display name"),
    _subject: Subject = Depends(get_compliance_subject),
    directory=Depends(_user_directory),
) -> PersonPermissionSummaryResponse:
    rows = filter_directory_rows(build_user_directory_rows(directory), q)
    matches = [build_person_permission_summary(row) for row in rows]
    return PersonPermissionSummaryResponse(
        query=q.strip(),
        count=len(matches),
        matches=matches,
        source="user_directory",
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


@router.post("/payments/eligible-approvers", response_model=PaymentEligibleApproversResponse)
async def evaluate_payment_eligible_approvers(
    request: PaymentEligibleApproversEvaluateRequest,
    _service_caller: Subject = Depends(get_service_caller),
    service=Depends(_eligibility_service),
) -> PaymentEligibleApproversResponse:
    try:
        return await service.eligible_approvers_for_payment(request)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"eligibility evaluation failed: {exc}") from exc


@router.post("/instructions/eligible-approvers", response_model=InstructionEligibleApproversResponse)
async def evaluate_instruction_eligible_approvers(
    request: InstructionEligibleApproversEvaluateRequest,
    _service_caller: Subject = Depends(get_service_caller),
    service=Depends(_eligibility_service),
) -> InstructionEligibleApproversResponse:
    try:
        return await service.eligible_approvers_for_instruction(request)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"eligibility evaluation failed: {exc}") from exc


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
