import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ps import __version__
from ps.config import settings
from ps.database import close, connect
from ps.kafka_publisher import kafka_publisher
from ps.repository import PaymentRepository
from ps.routes import router
from ps.security_event_repository import SecurityEventRepository
from ps.security_event_watcher import SecurityEventWatcher
from ps.security_ui_routes import (
    SECURITY_EVENTS_STATIC_DIR,
    security_event_broadcaster,
    security_event_ui_store,
)
from ps.security_ui_routes import router as security_ui_router
from ps.service_identity import service_identity
from ps.ui_routes import STATIC_DIR, payment_broadcaster, router as ui_router
from ps.ui_watcher import PaymentWatcher

logger = logging.getLogger(__name__)

_payment_watcher_task: asyncio.Task | None = None
_security_event_watcher_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _payment_watcher_task, _security_event_watcher_task
    logging.basicConfig(level=logging.INFO)
    await connect()
    await PaymentRepository().ensure_indexes()
    await SecurityEventRepository().ensure_indexes()
    await kafka_publisher.start()
    await service_identity.login()
    await security_event_ui_store.connect()

    payment_watcher = PaymentWatcher()
    _payment_watcher_task = asyncio.create_task(payment_watcher.watch(payment_broadcaster))

    security_event_watcher = SecurityEventWatcher(security_event_ui_store)
    await security_event_watcher.connect()
    _security_event_watcher_task = asyncio.create_task(
        security_event_watcher.watch(security_event_broadcaster)
    )

    logger.info("payment browser and security event monitor live feeds started")
    yield

    for task in (_payment_watcher_task, _security_event_watcher_task):
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    await kafka_publisher.close()
    await close()


app = FastAPI(
    title="Payment Service",
    description="REST API for cash payment lifecycle against approved SSI instructions",
    version=__version__,
    lifespan=lifespan,
)

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
