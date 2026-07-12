import time
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from telemetry import (
    configure_telemetry,
    get_logger,
    instrument_app,
    shutdown_telemetry,
)

from chat_application import __version__
from chat_application.capabilities import audience_labels
from chat_application.config import settings
from chat_application.dependencies import get_chat_subject
from chat_application.feedback_observability import (
    ChatFeedbackContext,
    get_feedback_distribution,
    record_chat_feedback,
)
from chat_application.ml_client import PolicyPilotMlClient
from chat_application.models import ChatFeedbackRequest, ChatRequest, ChatResponse
from chat_application.multimodal_search import MultimodalSearchClient
from chat_application.neo4j import Neo4jClient
from chat_application.rag import RagService
from chat_application.response_formatter import format_chat_response
from chat_application.routing_observability import (
    finalize_chat_response,
    get_routing_distribution,
)
from chat_application.service_identity import service_identity
from chat_application.skills import confirm_create_payment
from chat_application.subject import Subject
from chat_application.users import chat_users, compliance_users, load_users
from chat_application.zitadel_auth import ZitadelAuthClient, login_name_for_user

logger = get_logger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"

ml_client = PolicyPilotMlClient()
neo4j_client = Neo4jClient()
multimodal_client = MultimodalSearchClient(neo4j_client)
rag_service: RagService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_service
    await neo4j_client.connect()
    try:
        await ml_client.warmup()
    except Exception as exc:
        logger.warning("Vertex warmup failed (chat may still work): %s", exc)
    try:
        await service_identity.login()
    except Exception as exc:
        logger.warning("chat service identity login failed: %s", exc)
    rag_service = RagService(
        ml_client=ml_client,
        multimodal=multimodal_client,
        neo4j=neo4j_client,
    )
    logger.info("PolicyPilot ready on port %s", settings.port)
    yield
    await ml_client.close()
    await neo4j_client.close()
    shutdown_telemetry()


app = FastAPI(
    title="PolicyPilot",
    description="PolicyPilot — natural-language policy Q&A over security events (Neo4j multimodal + graph + Vertex Gemini)",
    version=__version__,
    lifespan=lifespan,
)

configure_telemetry("ssi-chat", service_version=__version__)
instrument_app(app)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "UP"}


@app.get("/api/routing-stats")
async def routing_stats() -> dict:
    """In-process retrieval routing distribution since process start."""
    return get_routing_distribution().to_dict()


@app.get("/api/feedback-stats")
async def feedback_stats() -> dict:
    """Thumbs-up/down satisfaction distribution by retrieval strategy since process start."""
    return get_feedback_distribution().to_dict()


class LoginRequest(BaseModel):
    user_id: str = Field(min_length=1)
    password: str = Field(min_length=1)


@app.get("/api/compliance-users")
async def list_compliance_users() -> dict:
    """Legacy endpoint — compliance-only users. Prefer ``/api/chat-users``."""
    users = compliance_users(settings.users_file, allowed_roles=settings.compliance_role_set)
    return {
        "users": [
            {
                "user_id": user.user_id,
                "display_name": f"{user.family_name}, {user.given_name}",
                "title": user.title,
                "roles": list(user.roles),
                "audiences": ["compliance"],
            }
            for user in users
        ]
    }


@app.get("/api/chat-users")
async def list_chat_users() -> dict:
    """Users allowed to sign in to Policy Pilot (compliance + operational)."""
    return {"users": chat_users(settings.users_file, allowed_roles=settings.chat_role_set)}


@app.post("/api/auth/login")
async def auth_login(request: LoginRequest) -> dict:
    if not settings.zitadel_service_pat:
        raise HTTPException(status_code=503, detail="ZITADEL service PAT not configured")
    client = ZitadelAuthClient()
    login_name = login_name_for_user(request.user_id)
    try:
        session = await client.login(login_name, request.password)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"login failed: {exc}") from exc

    audiences: list[str] = []
    roles: list[str] = []
    try:
        seed = load_users(settings.users_file)
        for user in seed.users:
            if user.user_id == session.user_id:
                roles = list(user.roles)
                audiences = audience_labels(user.roles)
                break
    except Exception:
        logger.warning("could not resolve audiences for %s", session.user_id)

    return {
        "user_id": session.user_id,
        "session_id": session.session_id,
        "session_token": session.session_token,
        "roles": roles,
        "audiences": audiences,
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    subject: Subject = Depends(get_chat_subject),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> ChatResponse:
    if rag_service is None:
        raise HTTPException(status_code=503, detail="RAG service not ready")

    bearer_token = authorization.split(" ", 1)[1].strip() if authorization else None

    try:
        return await rag_service.ask(
            request.message.strip(),
            request.history,
            mode=request.mode,
            bearer_token=bearer_token,
            session_id=x_session_id,
            subject=subject,
        )
    except Exception as exc:
        logger.exception("chat failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class CreatePaymentConfirmRequest(BaseModel):
    pending_id: str = Field(min_length=1)
    decision: str = Field(min_length=1, pattern="^(go|no_go)$")


@app.post("/api/chat/skills/create-payment/confirm", response_model=ChatResponse)
async def confirm_create_payment_skill(
    request: CreatePaymentConfirmRequest,
    subject: Subject = Depends(get_chat_subject),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> ChatResponse:
    bearer_token = authorization.split(" ", 1)[1].strip() if authorization else None
    if not bearer_token:
        raise HTTPException(status_code=401, detail="Bearer token required")

    started = time.perf_counter()
    result = await confirm_create_payment(
        pending_id=request.pending_id,
        decision=request.decision,
        subject=subject,
        user_token=bearer_token,
        user_session_id=x_session_id,
    )
    elapsed = (time.perf_counter() - started) * 1000
    return finalize_chat_response(
        f"confirm create-payment {request.pending_id} {request.decision}",
        "payments",
        answer=format_chat_response(result.answer),
        retrieval_ms=0.0,
        generation_ms=elapsed,
        path="skill",
        cypher_provenance="none",
        answer_synthesis="formatter",
        intent_id=result.intent_id,
        skill_activities=result.activities,
    )


@app.post("/api/chat/feedback")
async def chat_feedback(
    request: ChatFeedbackRequest,
    subject: Subject = Depends(get_chat_subject),
) -> dict[str, str]:
    feedback = ChatFeedbackContext.from_payload(
        rating=request.rating,
        mode=request.mode,
        path=request.path,
        cypher_provenance=request.cypher_provenance,
        answer_synthesis=request.answer_synthesis,
        retrieval_strategy=request.retrieval_strategy,
        user_id=subject.user_id,
        intent_id=request.intent_id,
        question_hash=request.question_hash,
    )
    record_chat_feedback(feedback)
    return {"status": "recorded"}


def run() -> None:
    uvicorn.run(
        "chat_application.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
