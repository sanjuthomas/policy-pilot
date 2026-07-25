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
from ps.audit_routes import router as audit_router
from ps.auth_routes import router as auth_router
from ps.config import settings
from ps.database import close, connect
from ps.routes import router
from ps.service_identity import service_identity
from ps.ui_routes import STATIC_DIR
from ps.ui_routes import router as ui_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect()
    await service_identity.login()
    logger.info("payment browser ready")
    yield
    await close()
    shutdown_telemetry()


app = FastAPI(
    title="Payment Service",
    description="REST API for cash payment lifecycle against approved SSI instructions",
    version=__version__,
    lifespan=lifespan,
)

configure_telemetry("payment-service", service_version=__version__)
instrument_app(app)

app.include_router(auth_router)
app.include_router(router, prefix=settings.api_prefix)
app.include_router(audit_router, prefix=settings.api_prefix)
app.include_router(ui_router)
app.mount("/ui/static", StaticFiles(directory=STATIC_DIR), name="ui-static")


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
