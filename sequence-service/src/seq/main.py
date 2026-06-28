from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from telemetry import (
    configure_telemetry,
    get_logger,
    instrument_app,
    shutdown_telemetry,
)

from seq import __version__
from seq.config import settings
from seq.repository import SequenceRepository
from seq.routes import router
from seq.service import SequenceService

logger = get_logger(__name__)

sequence_repository: SequenceRepository | None = None
sequence_service: SequenceService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global sequence_repository, sequence_service

    configure_telemetry("sequence-service", service_version=__version__)
    instrument_app(app)

    sequence_repository = SequenceRepository()
    await sequence_repository.connect()
    await sequence_repository.ensure_indexes()
    sequence_service = SequenceService(sequence_repository)

    logger.info("sequence-service ready on port %s", settings.port)
    yield

    if sequence_repository is not None:
        await sequence_repository.close()
    sequence_repository = None
    sequence_service = None
    shutdown_telemetry()


app = FastAPI(
    title="Sequence Service",
    description="Atomic business ID allocation for instructions and payments",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(router, prefix=settings.api_prefix)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "UP"}


def run() -> None:
    uvicorn.run(
        "seq.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
