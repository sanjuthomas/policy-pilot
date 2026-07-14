# Local development and observability

Run services outside Docker, browse logs, and find component READMEs.

## Local development

Each service can run on the host against the Docker stack (MongoDB, Kafka, Neo4j, OPA, ZITADEL). Requires **Vertex AI** credentials for ssi-indexer and ssi-chat — see [GCP setup](gcp-setup.md).

```bash
# instruction-service API
cd instruction-service && pip install -e .
uvicorn inst.main:app --reload --port 8000

# SSI indexer + search console
cd ssi-indexer && pip install -e .
ssi-indexer           # :8090

# Policy Pilot (ssi-chat)
cd ssi-chat && pip install -e .
ssi-chat              # :8092

# Authorization service
cd authorization-service && pip install -e .
authorization-service # :8094

# Payment service
cd payment-service && pip install -e .
payment-service       # :8093

# Demo harness
cd ssi-demo-harness && pip install -e .
ssi-demo-harness-ui   # :8091
```

Install shared packages before editable service installs (matches CI):

```bash
pip install -q \
  ./shared/telemetry \
  ./shared/platform_auth \
  ./shared/sequence_client \
  ./shared/authz_client \
  ./shared/cypher_builder \
  ./shared/vertex_client
```

Each service reads configuration from environment variables — see its own README.

## Observability (logs)

Application services send logs **directly over OTLP** to the OpenTelemetry Collector (`4317`). The collector forwards them to:

1. **Debug exporter** — collector stdout (`docker compose logs otel-collector`)
2. **OpenSearch** — index `otel-logs` (redacted HTTP and Vertex Gen AI log lines, startup messages, errors)

Metrics and traces still use the debug exporter only. There is no application log file on disk; optional console mirroring uses `OTEL_LOG_CONSOLE=true`.

Browse logs: open [OpenSearch Dashboards](http://localhost:5601), create an index pattern for `otel-logs*`, and use **Discover**.

## Components

| Directory | Role |
|-----------|------|
| `instruction-service` | FastAPI lifecycle API — OBO authz, Mongo persistence, eligible-approvers API |
| `payment-service` | Payment lifecycle — same authz pattern, payment UIs |
| `ssi-indexer` | Four Kafka consumers → Neo4j graph + vector indexer + search console |
| `kafka-connect` | MongoDB CDC → domain Kafka topics |
| `ssi-chat` | **Policy Pilot** — conversational investigation UI |
| `shared/cypher_builder` | Neo4j query planner — deterministic intents + Gemini plan parsing |
| `shared/vertex_client` | Vertex AI embeddings + Gemini generation |
| `authorization-service` | Stateless OPA gateway — evaluate + eligible-approvers |
| `ssi-demo-harness` | ZITADEL-authenticated scenario harness |
| `neo4j-graph-model` | Graph schema docs, constraints, example queries |
| `opa-policy-seed` | Startup gate for compiled Rego policies |
| `zitadel-seed` | Demo user seed from `users.yaml` |

## Service URLs (local Docker stack)

| URL | Service |
|-----|---------|
| http://localhost:8092 | Policy Pilot (ssi-chat) |
| http://localhost:8000/ui/ | Instruction browser |
| http://localhost:8093/ui/ | Payment browser |
| http://localhost:8090 | SSI indexer search console |
| http://localhost:8091 | Demo harness |
| http://localhost:8094 | Authorization service |
| http://localhost:7474/browser/ | Neo4j (`neo4j` / `devpassword`) |
| http://localhost:8080/ui/console | ZITADEL admin |
| http://localhost:5601 | OpenSearch Dashboards |

## Retrieval quality evaluation

The regression suite (`ssi-chat/regression/`) measures answer quality beyond keyword checks:

- **Routing accuracy** — expected path (`neo4j_direct`, `full_rag`, `eligibility`) and synthesis mode
- **Entity recall** — instruction/payment IDs grounded in sources or graph rows
- **Source precision@5** — vector-mode cases include `vector` channels
- **Groundedness / faithfulness** — token-overlap proxies against graph rows and context

Run: `python -m regression.runner --seed --report regression-report.json`. Golden set: `--eval-golden`. See `ssi-chat/regression/README.md` and [Intent Determination](intent-determination.md).
