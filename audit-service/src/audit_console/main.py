from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from telemetry import configure_telemetry, instrument_app, shutdown_telemetry

from audit_console import __version__
from audit_console.database import close, connect
from audit_console.routes import STATIC_DIR, router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await connect()
    yield
    await close()
    shutdown_telemetry()


app = FastAPI(
    title="Technology Auditor Console",
    description="Read-only security-event and governed-activity evidence",
    version=__version__,
    lifespan=lifespan,
)
configure_telemetry("audit-service", service_version=__version__)
instrument_app(app)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "UP"}
