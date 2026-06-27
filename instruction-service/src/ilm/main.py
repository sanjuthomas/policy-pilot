import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from telemetry import configure_telemetry, get_logger, instrument_app, shutdown_telemetry

from ilm import __version__
from ilm.auth_routes import router as auth_router
from ilm.config import settings
from ilm.database import close, connect
from ilm.kafka_publisher import kafka_publisher
from ilm.maintenance_routes import router as maintenance_router
from ilm.routes import router
from ilm.security_ui_routes import (
    SECURITY_EVENTS_STATIC_DIR,
    security_event_ui_store,
)
from ilm.security_ui_routes import (
    router as security_ui_router,
)
from ilm.ui_routes import STATIC_DIR
from ilm.ui_routes import router as ui_router

UI_STATIC_DIR = STATIC_DIR
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_telemetry("instruction-service", service_version=__version__)
    instrument_app(app)
    await connect()
    await kafka_publisher.start()
    await security_event_ui_store.connect()
    logger.info("instruction browser and security event monitor ready")
    yield
    await kafka_publisher.close()
    await close()
    shutdown_telemetry()


app = FastAPI(
    title="Instruction Lifecycle Manager",
    description="REST API for canonical cash wire settlement instruction lifecycle (ISO 20022)",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(router, prefix=settings.api_prefix)
app.include_router(maintenance_router, prefix=settings.api_prefix)
app.include_router(ui_router)
app.include_router(security_ui_router)
app.mount("/ui/static", StaticFiles(directory=UI_STATIC_DIR), name="ui-static")
app.mount(
    "/ui/security-events/static",
    StaticFiles(directory=SECURITY_EVENTS_STATIC_DIR),
    name="security-events-static",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "UP"}


def run() -> None:
    uvicorn.run(
        "ilm.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    run()
