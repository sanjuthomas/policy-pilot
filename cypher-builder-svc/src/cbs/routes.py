from __future__ import annotations

from fastapi import APIRouter

from cbs import planner
from cbs.models import PlanRequest, PlanResponse, ValidateRequest, ValidateResponse

router = APIRouter()


@router.post("/v1/plan", response_model=PlanResponse)
async def plan_endpoint(body: PlanRequest) -> PlanResponse:
    return planner.plan(body)


@router.post("/v1/validate", response_model=ValidateResponse)
async def validate_endpoint(body: ValidateRequest) -> ValidateResponse:
    return planner.validate(body)
