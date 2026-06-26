from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from ps.config import settings
from ps.repository import PaymentNotFoundError, PaymentRepository
from ps.ui_broadcaster import PaymentBroadcaster

STATIC_DIR = Path(__file__).resolve().parent / "static"

router = APIRouter(tags=["ui"])
payment_broadcaster = PaymentBroadcaster()


@router.get("/ui")
@router.get("/ui/")
async def ui_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/ui/payments/{payment_id}")
async def ui_payment_detail(payment_id: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "payment.html")


@router.get("/api/ui/payments")
async def ui_list_payments(
    status: str | None = Query(default=None),
    owning_lob: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict:
    repo = PaymentRepository()
    payments = await repo.list(status=status, limit=limit)
    if owning_lob:
        payments = [p for p in payments if p.owning_lob == owning_lob]
    return {
        "payments": [p.to_mongo() for p in payments],
        "count": len(payments),
    }


@router.get("/api/ui/payments/stream")
async def ui_stream_payments() -> StreamingResponse:
    async def event_generator():
        yield "event: connected\ndata: {}\n\n"
        async for payment in payment_broadcaster.subscribe():
            yield payment_broadcaster.sse_payload(payment)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/ui/payments/{payment_id}")
async def ui_get_payment(payment_id: str) -> dict:
    repo = PaymentRepository()
    try:
        payment = await repo.find_by_id(payment_id)
    except PaymentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"payment not found: {payment_id}",
        ) from exc
    return {"payment": payment.to_mongo()}
