import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from cypher_builder import (
    GRAPH_QUERY_EXTRACTION_SYSTEM,
    build_extraction_user_prompt,
    parse_graph_query_plan,
    validate_read_only_cypher,
)
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from telemetry import (
    configure_telemetry,
    get_logger,
    instrument_app,
    shutdown_telemetry,
)
from vertex_client import VertexEmbeddingClient, VertexGenerativeClient

from etl.admin import get_admin_subject
from etl.auth_routes import router as auth_router
from etl.config import settings
from etl.health import component_status
from etl.instruction_consumer import InstructionKafkaConsumer
from etl.instruction_pipeline import InstructionPipeline
from etl.instruction_security_event_consumer import (
    InstructionSecurityEventKafkaConsumer,
)
from etl.instruction_security_event_pipeline import InstructionSecurityEventPipeline
from etl.multimodal_store import MultimodalNeo4jStore
from etl.neo4j_client import Neo4jGraphWriter
from etl.payment_consumer import (
    PaymentFactKafkaConsumer,
    PaymentSecurityEventKafkaConsumer,
)
from etl.payment_pipeline import PaymentFactPipeline, PaymentSecurityEventPipeline
from etl.search_text.builder import list_profile_fields, list_search_profiles

__version__ = "0.2.0"

logger = get_logger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"

neo4j_writer = Neo4jGraphWriter()
embedding_client = VertexEmbeddingClient(
    project_id=settings.gcp_project_id,
    region=settings.gcp_region,
    model=settings.vertex_embedding_model,
    dimension=settings.embedding_dimension,
)
generation_client = VertexGenerativeClient(
    project_id=settings.gcp_project_id,
    region=settings.gcp_region,
    model=settings.vertex_gemini_model,
)
multimodal_store = MultimodalNeo4jStore(neo4j_writer)

instruction_security_event_pipeline = InstructionSecurityEventPipeline(
    neo4j_writer=neo4j_writer,
    embedding_client=embedding_client,
    multimodal_store=multimodal_store,
)
instruction_pipeline = InstructionPipeline(
    neo4j_writer=neo4j_writer,
    embedding_client=embedding_client,
    multimodal_store=multimodal_store,
)

payment_security_event_pipeline = PaymentSecurityEventPipeline(
    neo4j_writer=neo4j_writer,
    embedding_client=embedding_client,
    multimodal_store=multimodal_store,
)
payment_fact_pipeline = PaymentFactPipeline(
    neo4j_writer=neo4j_writer,
    embedding_client=embedding_client,
    multimodal_store=multimodal_store,
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
async def lifespan(app: FastAPI):
    await neo4j_writer.connect()

    await instruction_security_event_consumer.start()
    await instruction_consumer.start()
    await payment_security_event_consumer.start()
    await payment_fact_consumer.start()

    try:
        await embedding_client.warmup()
        await multimodal_store.ensure_indexes(embedding_client.dimension)
    except Exception as exc:
        logger.warning("search backends not fully warmed up yet: %s", exc)

    logger.info("ssi-indexer started (quad consumers: instruction events, instruction facts, payment events, payment facts)")
    yield

    await instruction_security_event_consumer.close()
    await instruction_consumer.close()
    await payment_security_event_consumer.close()
    await payment_fact_consumer.close()
    await neo4j_writer.close()
    await embedding_client.close()
    await generation_client.close()
    shutdown_telemetry()


app = FastAPI(
    title="Security Event Search Console",
    description="Query Neo4j graph and multimodal search produced by the ETL pipeline",
    version=__version__,
    lifespan=lifespan,
)

configure_telemetry("ssi-indexer", service_version=__version__)
instrument_app(app)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

api_router = APIRouter(dependencies=[Depends(get_admin_subject)])


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict:
    components = await component_status(
        instruction_security_event_consumer=instruction_security_event_consumer,
        multimodal_store=multimodal_store,
        neo4j_writer=neo4j_writer,
        embedding_client=embedding_client,
    )
    overall = "UP" if all(c["ok"] for c in components.values()) else "DEGRADED"
    return {"status": overall, "components": components}


@api_router.get("/search-profiles")
async def search_profiles() -> dict:
    """YAML search_text field lists — what feeds dense embedding indexing per entity."""
    profiles = await asyncio.to_thread(list_search_profiles)
    return {"count": len(profiles), "profiles": profiles}


@api_router.get("/search-profiles/{entity}")
async def search_profile_detail(entity: str) -> dict:
    try:
        profile = await asyncio.to_thread(list_profile_fields, entity)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return profile


@api_router.get("/vector/chunk-stats")
async def vector_chunk_stats(
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """Largest indexed search_text payloads — one point per record, no semantic chunking."""
    try:
        stats_payload = await multimodal_store.search_text_chunk_stats(top_n=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    stats_payload["indexing_notes"] = {
        "chunking": "none — each multimodal document is one security event, instruction state, or payment record",
        "search_text": (
            "flattened subset of salient fields (message, authorization, actors, "
            "instruction/payment attributes) — not the full raw JSON document"
        ),
        "full_payload": "stored in Neo4j payload_json alongside search_text for retrieval",
        "sources": {
            "instruction_security_event": "one point per instruction security event",
            "instruction_state": "one point per instruction (updated in place on mutation)",
            "payment_security_event": "one point per payment security event",
            "payment_fact": "one point per payment (updated in place on mutation)",
        },
    }
    stats_payload["embedding_context_tokens"] = 32_768
    stats_payload["search_profiles"] = await asyncio.to_thread(list_search_profiles)
    return stats_payload


@api_router.get("/stats")
async def stats() -> dict:
    components = await component_status(
        instruction_security_event_consumer=instruction_security_event_consumer,
        multimodal_store=multimodal_store,
        neo4j_writer=neo4j_writer,
        embedding_client=embedding_client,
    )
    return {
        "components": components,
        "all_ok": all(component["ok"] for component in components.values()),
    }


@api_router.post("/search/vector")
async def search_vector(request: SearchRequest) -> dict:
    try:
        vector = await embedding_client.embed_query(request.query)
        results = await multimodal_store.search_dense(
            vector,
            limit=request.limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"mode": "vector", "query": request.query, "count": len(results), "results": results}


@api_router.get("/graph/events")
async def graph_search_events(
    q: str = Query(default="", max_length=500),
    action: str = Query(default="", max_length=100),
    limit: int = Query(default=settings.search_default_limit, ge=1, le=50),
) -> dict:
    events = await neo4j_writer.search_events(text=q, action=action, limit=limit)
    return {"count": len(events), "events": events}


@api_router.get("/graph/events/{event_id}")
async def graph_event_detail(event_id: str) -> dict:
    subgraph = await neo4j_writer.get_event_subgraph(event_id)
    if subgraph is None:
        raise HTTPException(status_code=404, detail=f"graph event not found: {event_id}")
    return subgraph


@api_router.get("/graph/instructions/{instruction_id}")
async def graph_instruction_detail(instruction_id: str) -> dict:
    subgraph = await neo4j_writer.get_instruction_subgraph(instruction_id)
    if subgraph is None:
        raise HTTPException(status_code=404, detail=f"graph instruction not found: {instruction_id}")
    return subgraph


class IntentExtractRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: str = Field(default="events", pattern="^(events|instructions|payments)$")


class CypherRunRequest(BaseModel):
    cypher: str = Field(min_length=1, max_length=4096)


@api_router.post("/intent/extract")
async def intent_extract(request: IntentExtractRequest) -> dict:
    """Extract a structured graph query plan from natural language via Vertex Gemini."""
    try:
        raw = await generation_client.generate_text(
            system=GRAPH_QUERY_EXTRACTION_SYSTEM,
            user=build_extraction_user_prompt(
                question=request.question,
                mode=request.mode,
            ),
            temperature=0.0,
        )
        plan = parse_graph_query_plan(raw)
    except Exception as exc:
        logger.warning("intent extraction failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "question": request.question,
        "mode": request.mode,
        "plan": plan.model_dump(mode="json"),
        "model": settings.vertex_gemini_model,
        "source": "vertex_gemini",
    }


@api_router.post("/cypher/run")
async def cypher_run(request: CypherRunRequest) -> dict:
    """Validate and execute a read-only Cypher query against Neo4j."""
    try:
        validate_read_only_cypher(request.cypher)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Cypher validation failed: {exc}") from exc

    try:
        rows = await neo4j_writer.run_read_cypher(request.cypher)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Neo4j query failed: {exc}") from exc

    return {"cypher": request.cypher, "row_count": len(rows), "rows": rows}


app.include_router(auth_router)
app.include_router(api_router, prefix="/api")


def run() -> None:
    uvicorn.run(
        "etl.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
