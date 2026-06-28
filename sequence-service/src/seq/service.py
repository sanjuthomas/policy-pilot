from __future__ import annotations

from seq.formatting import build_counter_key, build_sequence_id
from seq.models import NextSequenceRequest, NextSequenceResponse
from seq.repository import SequenceRepository


class SequenceService:
    def __init__(self, repository: SequenceRepository) -> None:
        self._repository = repository

    async def next_sequence(self, request: NextSequenceRequest) -> NextSequenceResponse:
        counter_key = build_counter_key(
            request.business_date,
            request.owning_lob,
            request.entity_type,
        )
        sequence_number = await self._repository.allocate_next(counter_key)
        return NextSequenceResponse(
            sequence_id=build_sequence_id(counter_key, sequence_number),
            business_date=request.business_date,
            owning_lob=request.owning_lob,
            entity_type=request.entity_type,
            sequence_number=sequence_number,
            counter_key=counter_key,
        )
