import asyncio
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from etl.config import settings
from etl.health import component_status
from etl.instruction_consumer import InstructionKafkaConsumer
from etl.instruction_pipeline import InstructionPipeline
from etl.instruction_security_event_consumer import (
    InstructionSecurityEventKafkaConsumer,
)
from etl.instruction_security_event_pipeline import InstructionSecurityEventPipeline
from etl.neo4j_client import Neo4jGraphWriter
from etl.ollama_client import OllamaEmbeddingClient
from etl.payment_consumer import (
    PaymentFactKafkaConsumer,
    PaymentSecurityEventKafkaConsumer,
)
from etl.payment_pipeline import PaymentFactPipeline, PaymentSecurityEventPipeline
from etl.qdrant_store import QdrantHybridStore

__version__ = "0.2.0"

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"

neo4j_writer = Neo4jGraphWriter()
ollama_client = OllamaEmbeddingClient()
qdrant_store = QdrantHybridStore()

instruction_security_event_pipeline = InstructionSecurityEventPipeline(
    neo4j_writer=neo4j_writer,
    ollama_client=ollama_client,
    qdrant_store=qdrant_store,
)
instruction_pipeline = InstructionPipeline(
    neo4j_writer=neo4j_writer,
    ollama_client=ollama_client,
    qdrant_store=qdrant_store,
)

payment_security_event_pipeline = PaymentSecurityEventPipeline(
    neo4j_writer=neo4j_writer,
    ollama_client=ollama_client,
    qdrant_store=qdrant_store,
)
payment_fact_pipeline = PaymentFactPipeline(
    neo4j_writer=neo4j_writer,
    ollama_client=ollama_client,
    qdrant_store=qdrant_store,
)

instruction_security_event_consumer = InstructionSecurityEventKafkaConsumer(
    instruction_security_event_pipeline
)
instruction_consumer = InstructionKafkaConsumer(instruction_pipeline)
payment_security_event_consumer = PaymentSecurityEventKafkaConsumer(payment_security_event_pipeline)
payment_fact_consumer = PaymentFactKafkaConsumer(payment_fact_pipeline)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=settings.search_default_limit, ge=1, le=50)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=logging.INFO)
    await neo4j_writer.connect()
    qdrant_store.connect()

    await instruction_security_event_consumer.start()
    await instruction_consumer.start()
    await payment_security_event_consumer.start()
    await payment_fact_consumer.start()

    try:
        await ollama_client.warmup()
        if qdrant_store.has_collection():
            qdrant_store.ensure_collection(ollama_client.dimension)
    except Exception as exc:
        logger.warning("search backends not fully warmed up yet: %s", exc)

    logger.info("security-event-qdrant-etl started (quad consumers: instruction events, instruction facts, payment events, payment facts)")
    yield

    await instruction_security_event_consumer.close()
    await instruction_consumer.close()
    await payment_security_event_consumer.close()
    await payment_fact_consumer.close()
    await neo4j_writer.close()
    await ollama_client.close()
    qdrant_store.close()


app = FastAPI(
    title="Security Event Search Console",
    description="Query Neo4j graph and Qdrant hybrid vectors produced by the ETL pipeline",
    version=__version__,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict:
    components = await component_status(
        instruction_security_event_consumer=instruction_security_event_consumer,
        qdrant_store=qdrant_store,
        neo4j_writer=neo4j_writer,
        ollama_client=ollama_client,
    )
    overall = "UP" if all(c["ok"] for c in components.values()) else "DEGRADED"
    return {"status": overall, "components": components}


@app.get("/api/stats")
async def stats() -> dict:
    components = await component_status(
        instruction_security_event_consumer=instruction_security_event_consumer,
        qdrant_store=qdrant_store,
        neo4j_writer=neo4j_writer,
        ollama_client=ollama_client,
    )
    return {
        "components": components,
        "all_ok": all(component["ok"] for component in components.values()),
    }


@app.get("/api/components")
async def components() -> dict:
    return await component_status(
        instruction_security_event_consumer=instruction_security_event_consumer,
        qdrant_store=qdrant_store,
        neo4j_writer=neo4j_writer,
        ollama_client=ollama_client,
    )


@app.post("/api/search/vector")
async def search_vector(request: SearchRequest) -> dict:
    try:
        vector = await ollama_client.embed(request.query)
        results = await asyncio.to_thread(
            qdrant_store.search_dense,
            vector,
            limit=request.limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"mode": "vector", "query": request.query, "count": len(results), "results": results}


@app.post("/api/search/bm25")
async def search_bm25(request: SearchRequest) -> dict:
    try:
        results = await asyncio.to_thread(
            qdrant_store.search_bm25,
            request.query,
            limit=request.limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"mode": "bm25", "query": request.query, "count": len(results), "results": results}


@app.post("/api/search/hybrid")
async def search_hybrid(request: SearchRequest) -> dict:
    try:
        vector = await ollama_client.embed(request.query)
        results = await asyncio.to_thread(
            qdrant_store.search_hybrid,
            request.query,
            vector,
            limit=request.limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"mode": "hybrid", "query": request.query, "count": len(results), "results": results}


@app.get("/api/graph/events")
async def graph_search_events(
    q: str = Query(default="", max_length=500),
    action: str = Query(default="", max_length=100),
    limit: int = Query(default=settings.search_default_limit, ge=1, le=50),
) -> dict:
    events = await neo4j_writer.search_events(text=q, action=action, limit=limit)
    return {"count": len(events), "events": events}


@app.get("/api/graph/events/{event_id}")
async def graph_event_detail(event_id: str) -> dict:
    subgraph = await neo4j_writer.get_event_subgraph(event_id)
    if subgraph is None:
        raise HTTPException(status_code=404, detail=f"graph event not found: {event_id}")
    return subgraph


@app.get("/api/graph/instructions/{instruction_id}")
async def graph_instruction_detail(instruction_id: str) -> dict:
    subgraph = await neo4j_writer.get_instruction_subgraph(instruction_id)
    if subgraph is None:
        raise HTTPException(status_code=404, detail=f"graph instruction not found: {instruction_id}")
    return subgraph


# ---------------------------------------------------------------------------
# Cypher validation (read-only guard — same rules as the chat service)
# ---------------------------------------------------------------------------

_WRITE_KEYWORD = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DROP|DETACH|FOREACH|LOAD)\b", re.IGNORECASE
)
_WRITE_PROCEDURE = re.compile(
    r"\bCALL\s+(db\.\w+|apoc\.create\.|apoc\.periodic\.|apoc\.merge\.|apoc\.refactor\.)",
    re.IGNORECASE,
)
_READ_START = re.compile(
    r"^\s*(MATCH|OPTIONAL\s+MATCH|WITH|RETURN|UNWIND)\b", re.IGNORECASE
)
_LIMIT_CLAUSE = re.compile(r"\bLIMIT\s+\d+\b", re.IGNORECASE)
_LINE_COMMENT = re.compile(r"//[^\n]*", re.MULTILINE)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING_LITERAL = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")


def _validate_read_only_cypher(cypher: str) -> None:
    s = cypher.strip()
    if not s:
        raise ValueError("empty query")
    if len(s) > 4096:
        raise ValueError("query exceeds 4096 characters")
    if ";" in s.rstrip(";"):
        raise ValueError("multiple statements not allowed")
    n = _LINE_COMMENT.sub("", s)
    n = _BLOCK_COMMENT.sub("", n)
    n = _STRING_LITERAL.sub("''", n)
    if not _READ_START.match(n):
        raise ValueError("query must begin with MATCH, OPTIONAL MATCH, WITH, RETURN, or UNWIND")
    m = _WRITE_KEYWORD.search(n)
    if m:
        raise ValueError(f"disallowed write keyword '{m.group(0).upper()}'")
    if _WRITE_PROCEDURE.search(n):
        raise ValueError("CALL to a write-capable procedure not allowed")
    if not _LIMIT_CLAUSE.search(n):
        raise ValueError("query must include a LIMIT clause")


class CypherGenerateRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: str = Field(default="events", pattern="^(events|instructions|payments)$")


class CypherRunRequest(BaseModel):
    cypher: str = Field(min_length=1, max_length=4096)


@app.post("/api/cypher/generate")
async def cypher_generate(request: CypherGenerateRequest) -> dict:
    """Proxy to the chat service — translates natural language to Cypher."""
    url = f"{settings.chat_service_url.rstrip('/')}/api/cypher/generate"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                url,
                json={"question": request.question, "mode": request.mode},
            )
        if resp.status_code == 503:
            raise HTTPException(status_code=503, detail=resp.json().get("detail", "chat service unavailable"))
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"chat service unreachable at {settings.chat_service_url}: {exc}",
        ) from exc


@app.post("/api/cypher/run")
async def cypher_run(request: CypherRunRequest) -> dict:
    """Validate and execute a read-only Cypher query against Neo4j."""
    try:
        _validate_read_only_cypher(request.cypher)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Cypher validation failed: {exc}") from exc

    try:
        rows = await neo4j_writer.run_read_cypher(request.cypher)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Neo4j query failed: {exc}") from exc

    return {"cypher": request.cypher, "row_count": len(rows), "rows": rows}


def run() -> None:
    uvicorn.run(
        "etl.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
