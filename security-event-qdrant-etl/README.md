# Security Event Qdrant ETL

Kafka consumers that index instruction and payment facts into **Qdrant** (dense + BM25 hybrid) and **Neo4j** (graph projection).

Also exposes a **Search Console** UI for manual vector / BM25 / hybrid / Neo4j queries.

## URL

http://localhost:8090

## Pipelines

Four independent consumers run in the same process. Every Kafka message carries a **full snapshot** — the ETL makes no API calls to ILM or the payment service.

```mermaid
flowchart TB
    K1[instruction-security-events] --> P1[SecurityEventPipeline]
    K2[ssi-instructions] --> P2[InstructionPipeline]
    K3[payment-security-events] --> P3[PaymentSecurityEventPipeline]
    K4[ssi-payments] --> P4[PaymentFactPipeline]
    P1 --> NEO[Neo4j upsert]
    P2 --> NEO
    P3 --> NEO
    P4 --> NEO
    P1 --> OLL[Ollama embed]
    P2 --> OLL
    P3 --> OLL
    P4 --> OLL
    OLL --> QD[Qdrant ssi_search_index]
```

| Pipeline | Kafka topic | Consumer group | Qdrant `source` tag |
|----------|-------------|----------------|---------------------|
| `SecurityEventPipeline` | `instruction-security-events` | `security-event-qdrant-etl` | `security_event` |
| `InstructionPipeline` | `ssi-instructions` | `ssi-instruction-etl` | `instruction_state` |
| `PaymentSecurityEventPipeline` | `payment-security-events` | `payment-security-event-etl` | `payment_security_event` |
| `PaymentFactPipeline` | `ssi-payments` | `payment-fact-etl` | `payment_fact` |

For each message:

1. Parse the fact event (security event or state snapshot).
2. Upsert Neo4j nodes/relationships (see `neo4j-graph-model/`). User upserts also write `REPORTS_TO` from `supervisor_id`.
3. Embed `search_text` with Ollama **`bge-m3:latest`** → upsert Qdrant hybrid point.

## Enriched document shape (instruction security events)

Stored in Qdrant payload (and used for search text):

| Field | Content |
|-------|---------|
| `security_event` | Full Kafka/Mongo event (includes `instruction_snapshot`) |
| `instruction` | Instruction snapshot from the event |
| `merged` | Denormalized join (actor, creator, action, wire_scope, …) |
| `search_text` | Flattened string for embedding + BM25 |
| `source` | `security_event`, `instruction_state`, `payment_security_event`, or `payment_fact` |

## Search Console

| Mode | Backend |
|------|---------|
| Hybrid | Qdrant dense + BM25 → RRF |
| Vector | Qdrant dense only |
| BM25 | Qdrant sparse only |
| Neo4j | Text search on `SecurityEvent` nodes |

Component status bar shows Kafka, Qdrant, Neo4j, and Ollama health.

## Configuration (Docker)

| Variable | Default |
|----------|---------|
| `KAFKA_SECURITY_EVENTS_TOPIC` | `instruction-security-events` |
| `KAFKA_INSTRUCTION_TOPIC` | `ssi-instructions` |
| `KAFKA_PAYMENT_SECURITY_EVENTS_TOPIC` | `payment-security-events` |
| `KAFKA_PAYMENTS_TOPIC` | `ssi-payments` |
| `OLLAMA_EMBEDDING_MODEL` | `bge-m3:latest` |
| `QDRANT_COLLECTION` | `ssi_search_index` |
| `NEO4J_URI` | `bolt://neo4j:7687` |

Requires **host Ollama** (`OLLAMA_URL=http://host.docker.internal:11434`).

## Run locally

```bash
cd security-event-qdrant-etl
pip install -e .
security-event-search   # serves on :8090
```

## API (selected)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stats` | Component health + Qdrant point counts |
| POST | `/api/search/hybrid` | Hybrid search |
| POST | `/api/search/vector` | Dense vector search |
| POST | `/api/search/bm25` | BM25 search |
| GET | `/api/graph/events` | Neo4j event text search |
| GET | `/api/graph/events/{event_id}` | Event subgraph |

## Reset consumer offsets

If Qdrant/Neo4j are empty but Kafka has messages, reset each consumer group:

```bash
docker compose stop security-event-qdrant-etl

for TOPIC_GROUP in \
  "instruction-security-events:security-event-qdrant-etl" \
  "ssi-instructions:ssi-instruction-etl" \
  "payment-security-events:payment-security-event-etl" \
  "ssi-payments:payment-fact-etl"
do
  TOPIC="${TOPIC_GROUP%%:*}"
  GROUP="${TOPIC_GROUP##*:}"
  docker exec kafka /opt/kafka/bin/kafka-consumer-groups.sh \
    --bootstrap-server localhost:9092 \
    --group "$GROUP" \
    --reset-offsets --to-earliest \
    --topic "$TOPIC" --execute
done

docker compose up -d security-event-qdrant-etl
```
