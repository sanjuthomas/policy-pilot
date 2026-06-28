from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from telemetry import configure_telemetry, get_logger, instrument_app, shutdown_telemetry

from authz import __version__
from authz.auth_routes import router as auth_router
from authz.authorization_routes import router as authorization_router
from authz.config import settings
from authz.eligibility import EligibilityService
from authz.ilm_client import IlmClient
from authz.opa import OpaClient
from authz.payment_repository import PaymentRepository
from authz.routes import router
from authz.service_identity import service_identity
from authz.ui_routes import STATIC_DIR
from authz.ui_routes import router as ui_router
from authz.user_directory import UserDirectory

logger = get_logger(__name__)

payment_repository: PaymentRepository | None = None
user_directory: UserDirectory | None = None
eligibility_service: EligibilityService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global payment_repository, user_directory, eligibility_service

    configure_telemetry("authorization-service", service_version=__version__)
    instrument_app(app)

    payment_repository = PaymentRepository()
    await payment_repository.connect()

    user_directory = UserDirectory(settings.users_file)
    await service_identity.login()

    eligibility_service = EligibilityService(
        payments=payment_repository,
        users=user_directory,
        ilm=IlmClient(),
        opa=OpaClient(),
    )

    logger.info("authorization-service ready on port %s", settings.port)
    yield

    if payment_repository is not None:
        await payment_repository.close()
    payment_repository = None
    user_directory = None
    eligibility_service = None
    shutdown_telemetry()


app = FastAPI(
    title="Authorization Service",
    description="Policy intelligence — eligible approvers and authorization queries via OPA",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(authorization_router, prefix=settings.api_prefix)
app.include_router(router, prefix=settings.api_prefix)
app.include_router(ui_router)
app.mount("/ui/static", StaticFiles(directory=STATIC_DIR), name="ui-static")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "UP"}


def run() -> None:
    uvicorn.run(
        "authz.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
