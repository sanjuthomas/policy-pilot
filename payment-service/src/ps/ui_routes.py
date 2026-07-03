from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from ps.admin import get_admin_subject
from ps.constants import PAYMENT_CURRENT_OUT
from ps.repository import PaymentNotFoundError, PaymentRepository
from ps.storage import VersionedPayment

STATIC_DIR = Path(__file__).resolve().parent / "static"
_UI_NO_CACHE_HEADERS = {"Cache-Control": "no-cache"}

router = APIRouter(tags=["ui"])


def _versioned_payment_to_api_dict(record: VersionedPayment) -> dict:
    doc = record.payment.model_dump(mode="json")
    doc["version_number"] = record.version_number
    doc["in"] = record.valid_in.isoformat() + "Z"
    doc["out"] = (
        PAYMENT_CURRENT_OUT
        if record.valid_out is None
        else record.valid_out.isoformat() + "Z"
    )
    return doc


@router.get("/ui")
@router.get("/ui/")
async def ui_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers=_UI_NO_CACHE_HEADERS)


@router.get("/ui/payments/{payment_id}")
async def ui_payment_detail(payment_id: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "payment.html", headers=_UI_NO_CACHE_HEADERS)


@router.get("/api/ui/payments")
async def ui_list_payments(
    status: str | None = Query(default=None),
    owning_lob: str | None = Query(default=None),
    instruction_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    _admin=Depends(get_admin_subject),
) -> dict:
    repo = PaymentRepository()
    records = await repo.list_current(
        status=status,
        instruction_id=instruction_id.strip() if instruction_id else None,
        limit=limit,
    )
    if owning_lob:
        records = [record for record in records if record.payment.owning_lob == owning_lob]
    return {
        "payments": [_versioned_payment_to_api_dict(record) for record in records],
        "count": len(records),
    }


@router.get("/api/ui/payments/{payment_id}")
async def ui_get_payment(payment_id: str, _admin=Depends(get_admin_subject)) -> dict:
    repo = PaymentRepository()
    try:
        record = await repo.get_current(payment_id)
    except PaymentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"payment not found: {payment_id}",
        ) from exc
    return {"payment": _versioned_payment_to_api_dict(record)}
