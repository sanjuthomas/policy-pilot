from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ps.audit_repository import AuditExecutionRepository
from ps.authorization import subject_at_decision
from ps.dependencies import get_subject
from ps.models.api import Subject
from ps.models.audit import CreateAuditExecutionRequest, PatchAuditExecutionRequest

router = APIRouter(prefix="/audit-executions", tags=["audit-executions"])
_repo = AuditExecutionRepository()


def get_audit_repo() -> AuditExecutionRepository:
    return _repo


@router.post("", status_code=201)
async def create_audit_execution(
    body: CreateAuditExecutionRequest,
    subject: Subject = Depends(get_subject),
    repo: AuditExecutionRepository = Depends(get_audit_repo),
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "capability": body.capability,
        "skill": body.skill,
        "channel": body.channel,
        "status": body.status,
        "outcome": body.outcome,
        "actor": subject_at_decision(subject),
        "request": body.request,
        "interpretation": body.interpretation,
        "timeline": [step.model_dump(mode="json") for step in body.timeline],
        "timings_ms": body.timings_ms,
        "result": body.result,
        "governance": (
            body.governance.model_dump(mode="json", exclude_none=True)
            if body.governance
            else {}
        ),
    }
    if body.execution_id:
        document["execution_id"] = body.execution_id
    return await repo.create(document)


@router.patch("/{execution_id}")
async def patch_audit_execution(
    execution_id: str,
    body: PatchAuditExecutionRequest,
    subject: Subject = Depends(get_subject),
    repo: AuditExecutionRepository = Depends(get_audit_repo),
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    if body.status is not None:
        updates["status"] = body.status
    if body.outcome is not None:
        updates["outcome"] = body.outcome
    if body.timeline is not None:
        updates["timeline"] = [step.model_dump(mode="json") for step in body.timeline]
    if body.timings_ms is not None:
        updates["timings_ms"] = body.timings_ms
    if body.result is not None:
        updates["result"] = body.result
    if body.governance is not None:
        updates["governance"] = body.governance.model_dump(mode="json", exclude_none=True)

    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")

    expected_actor = None if _is_admin(subject) else subject.user_id
    doc = await repo.patch(
        execution_id,
        updates,
        expected_actor_user_id=expected_actor,
    )
    if doc is None:
        existing = await repo.get(execution_id)
        if existing is None:
            raise HTTPException(
                status_code=404, detail=f"audit execution not found: {execution_id}"
            )
        raise HTTPException(status_code=403, detail="not authorized to update this audit execution")
    return doc


def _is_admin(subject: Subject) -> bool:
    return "PLATFORM_ADMIN" in subject.roles
