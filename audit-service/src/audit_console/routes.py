from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from platform_auth import LoginRequest

from audit_console.auth import AuditorSubject, login, resolve_auditor
from audit_console.config import settings
from audit_console.repository import EventSource, EvidenceRepository

STATIC_DIR = Path(__file__).resolve().parent / "static"
router = APIRouter()
repository = EvidenceRepository()


@router.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/events/{source}/{event_id}")
async def event_page(source: EventSource, event_id: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "event.html")


@router.get("/audit/{execution_id}")
async def audit_page(execution_id: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "audit.html")


@router.post("/api/auth/login")
async def login_route(request: LoginRequest) -> dict[str, str]:
    return await login(request)


@router.get("/api/me")
async def me(subject: AuditorSubject = Depends(resolve_auditor)) -> AuditorSubject:
    return subject


@router.get("/api/security-events")
async def list_security_events(
    source: EventSource | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=settings.initial_limit, ge=1, le=1000),
    _subject: AuditorSubject = Depends(resolve_auditor),
) -> dict:
    events = await repository.list_events(
        source=source,
        severity=severity,
        limit=limit,
    )
    return {"events": events, "count": len(events)}


@router.get("/api/security-events/{source}/{event_id}")
async def get_security_event(
    source: EventSource,
    event_id: str,
    _subject: AuditorSubject = Depends(resolve_auditor),
) -> dict:
    event = await repository.get_event(source, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"security event not found: {event_id}")
    return {"event": event}


@router.get("/api/audit-executions")
async def list_audit_executions(
    limit: int = Query(default=settings.initial_limit, ge=1, le=1000),
    _subject: AuditorSubject = Depends(resolve_auditor),
) -> dict:
    executions = await repository.list_executions(limit=limit)
    return {"executions": executions, "count": len(executions)}


@router.get("/api/audit-executions/{execution_id}")
async def get_audit_execution(
    execution_id: str,
    _subject: AuditorSubject = Depends(resolve_auditor),
) -> dict:
    execution = await repository.get_execution(execution_id)
    if execution is None:
        raise HTTPException(
            status_code=404, detail=f"audit execution not found: {execution_id}"
        )
    return {"execution": execution}


@router.get("/api/audit-executions/{execution_id}/opa")
async def get_opa_evidence(
    execution_id: str,
    _subject: AuditorSubject = Depends(resolve_auditor),
) -> dict:
    evidence = await repository.get_opa_evidence(execution_id)
    if evidence is None:
        raise HTTPException(
            status_code=404, detail=f"audit execution not found: {execution_id}"
        )
    return evidence
