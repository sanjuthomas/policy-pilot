from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from telemetry import (
    configure_telemetry,
    get_logger,
    instrument_app,
    shutdown_telemetry,
)

from ps import __version__
from ps.auth_routes import router as auth_router
from ps.config import settings
from ps.database import close, connect
from ps.kafka_publisher import kafka_publisher
from ps.repository import PaymentRepository
from ps.routes import router
from ps.security_event_repository import SecurityEventRepository
from ps.security_ui_routes import (
    SECURITY_EVENTS_STATIC_DIR,
    security_event_ui_store,
)
from ps.security_ui_routes import router as security_ui_router
from ps.service_identity import service_identity
from ps.ui_routes import STATIC_DIR
from ps.ui_routes import router as ui_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_telemetry("payment-service", service_version=__version__)
    instrument_app(app)
    await connect()
    await PaymentRepository().ensure_indexes()
    await SecurityEventRepository().ensure_indexes()
    await kafka_publisher.start()
    await service_identity.login()
    await security_event_ui_store.connect()
    logger.info("payment browser and security event monitor ready")
    yield
    await kafka_publisher.close()
    await close()
    shutdown_telemetry()


app = FastAPI(
    title="Payment Service",
    description="REST API for cash payment lifecycle against approved SSI instructions",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(router, prefix=settings.api_prefix)
app.include_router(ui_router)
app.include_router(security_ui_router)
app.mount("/ui/static", StaticFiles(directory=STATIC_DIR), name="ui-static")
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
        "ps.main:app",
        host="0.0.0.0",
        port=8093,
        reload=False,
    )


if __name__ == "__main__":
    run()
