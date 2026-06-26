from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from chat_application import __version__
from chat_application.config import settings
from chat_application.cypher import (
    load_graph_schema,
    normalize_read_only_cypher,
    validate_read_only_cypher,
)
from chat_application.models import ChatRequest, ChatResponse
from chat_application.neo4j import Neo4jClient
from chat_application.ollama import OllamaClient
from chat_application.qdrant import QdrantSearchClient
from chat_application.rag import RagService

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"

ollama_client = OllamaClient()
qdrant_client = QdrantSearchClient()
neo4j_client = Neo4jClient()
rag_service: RagService | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global rag_service
    logging.basicConfig(level=logging.INFO)
    qdrant_client.connect()
    await neo4j_client.connect()
    try:
        await ollama_client.embed("warmup")
    except Exception as exc:
        logger.warning("Ollama warmup failed (chat may still work): %s", exc)
    rag_service = RagService(
        ollama=ollama_client,
        qdrant=qdrant_client,
        neo4j=neo4j_client,
    )
    logger.info("security event chat ready on port %s", settings.port)
    yield
    qdrant_client.close()
    await neo4j_client.close()


app = FastAPI(
    title="Security Event Chat",
    description="Natural-language Q&A over security events (vector + BM25 + Neo4j + Ollama)",
    version=__version__,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "UP"}


@app.get("/api/status")
async def status() -> dict:
    return {
        "ollama_chat_model": settings.ollama_chat_model,
        "ollama_embedding_model": settings.ollama_embedding_model,
        "qdrant_collection_exists": qdrant_client.has_collection(),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if rag_service is None:
        raise HTTPException(status_code=503, detail="RAG service not ready")
    try:
        return await rag_service.ask(
            request.message.strip(),
            request.history,
            mode=request.mode,
        )
    except Exception as exc:
        logger.exception("chat failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class CypherGenerateRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: str = Field(default="events", pattern="^(events|instructions|payments)$")


@app.post("/api/cypher/generate")
async def cypher_generate(request: CypherGenerateRequest) -> dict:
    """Translate a natural-language question to a read-only Cypher query."""
    schema = load_graph_schema()
    try:
        cypher = await ollama_client.generate_cypher(
            request.question, schema, mode=request.mode
        )
        cypher = normalize_read_only_cypher(cypher)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Cypher generation failed: {exc}") from exc

    valid = True
    error: str | None = None
    try:
        validate_read_only_cypher(cypher)
    except ValueError as exc:
        valid = False
        error = str(exc)

    return {
        "question": request.question,
        "mode": request.mode,
        "cypher": cypher,
        "valid": valid,
        "error": error,
        "model": settings.ollama_chat_model,
    }


def run() -> None:
    uvicorn.run(
        "chat_application.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
