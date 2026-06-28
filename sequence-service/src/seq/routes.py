from fastapi import APIRouter, Depends, HTTPException

from seq.models import NextSequenceRequest, NextSequenceResponse
from seq.repository import SequenceRepositoryError
from seq.service import SequenceService

router = APIRouter()


def _sequence_service() -> SequenceService:
    from seq.main import sequence_service

    if sequence_service is None:
        raise HTTPException(status_code=503, detail="sequence service not ready")
    return sequence_service


@router.post("/sequences/next", response_model=NextSequenceResponse)
async def next_sequence(
    request: NextSequenceRequest,
    service: SequenceService = Depends(_sequence_service),
) -> NextSequenceResponse:
    try:
        return await service.next_sequence(request)
    except SequenceRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
