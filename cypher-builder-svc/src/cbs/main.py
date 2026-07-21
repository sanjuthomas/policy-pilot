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

from cbs import __version__
from cbs.config import settings
from cbs.routes import router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("cypher-builder-svc ready on port %s", settings.port)
    yield
    shutdown_telemetry()


app = FastAPI(
    title="Cypher Builder Service",
    description="HTTP bridge wrapping shared/cypher_builder for deterministic neo4j_direct plans",
    version=__version__,
    lifespan=lifespan,
)

configure_telemetry("cypher-builder-svc", service_version=__version__)
instrument_app(app)

app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "UP"}


def run() -> None:
    uvicorn.run(
        "cbs.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
