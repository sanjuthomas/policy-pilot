# Local development and observability

Run services outside Docker, browse logs, and find component READMEs.

## Local development

Each service can run on the host against the Docker stack (MongoDB, Kafka, Neo4j, OPA, ZITADEL). Requires **Vertex AI** credentials for **ssi-indexer** and **ssi-chat-j** — see [GCP setup](gcp-setup.md).

```bash
# instruction-service API
cd instruction-service && pip install -e .
uvicorn inst.main:app --reload --port 8000

# SSI indexer + search console
cd ssi-indexer && pip install -e .
ssi-indexer           # :8090

# Policy Pilot (ssi-chat-j) — needs a warm Compose mesh for deps
cd ssi-chat-j
mvn spring-boot:run   # :8096

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

Or run chat from Compose: `docker compose up -d --build ssi-chat-j`.

Install shared Python packages before editable service installs (matches CI):

```bash
pip install -q \
  ./shared/telemetry \
  ./shared/platform_auth \
  ./shared/sequence_client \
  ./shared/authz_client \
  ./shared/cypher_builder \
  ./shared/vertex_client
```

(`shared/cypher_builder` is for the **indexer** Search Console planner — not for `ssi-chat-j`.)

Each service reads configuration from environment variables — see its own README.

## Observability mesh

All services emit **OTLP** (logs, metrics, traces) to the OpenTelemetry Collector (`4317`), which fans the three signals out to a Grafana-centric backend modeled on [observability-mesh-demo](https://github.com/sanjuthomas/observability-mesh-demo):

| Signal | Path | Backend |
|--------|------|---------|
| **Metrics** | Collector `prometheus` exporter (`:8889`) → Prometheus scrape | Prometheus → Grafana |
| **Logs** | Collector `otlphttp` → Loki OTLP ingest | Loki → Grafana (replaces OpenSearch) |
| **Traces** | Collector `otlp` → Tempo | Tempo → Grafana |
| **SLOs** | OpenSLO docs in the catalog → Sloth recording rules → Prometheus | Grafana SLO dashboard |

Everything is provisioned — no manual dashboard/datasource setup. See the full guide in [observability.md](observability.md).

Quick checks after `docker compose up`:

- **Grafana** [http://localhost:3000](http://localhost:3000) (`admin`/`admin`) — folder **Policy Pilot** has *SLO Overview*, *HTTP SLIs*, and *Domain SLIs* dashboards.
- **Prometheus targets** [http://localhost:9099/targets](http://localhost:9099/targets) — `otel-collector` should be **UP**.
- **SLO provisioner** [http://localhost:9097/ui/](http://localhost:9097/ui/) — the six seeded SLOs compile to Sloth rules.
- **Collector metrics** `curl http://localhost:8889/metrics` — raw re-exported series.

There is no application log file on disk; optional console mirroring uses `OTEL_LOG_CONSOLE=true`.

## Components

| Directory | Role |
|-----------|------|
| `instruction-service` | FastAPI lifecycle API — OBO authz, Mongo persistence, eligible-approvers API |
| `payment-service` | Payment lifecycle — same authz pattern, payment UIs |
| `ssi-indexer` | Four Kafka consumers → Neo4j graph + vector indexer + search console |
| `kafka-connect` | MongoDB CDC → domain Kafka topics |
| `ssi-chat-j` | **Policy Pilot** — conversational investigation UI (Java / Spring AI) |
| `shared/cypher_builder` | Neo4j query planner for indexer Search Console |
| `shared/vertex_client` | Vertex AI embeddings + Gemini generation (Python services) |
| `authorization-service` | Stateless OPA gateway — evaluate + eligible-approvers |
| `ssi-demo-harness` | ZITADEL-authenticated scenario harness |
| `neo4j-graph-model` | Graph schema docs, constraints, example queries |
| `opa-policy-seed` | Startup gate for compiled Rego policies |
| `zitadel-seed` | Demo user seed from `users.yaml` |

## Service URLs (local Docker stack)

| URL | Service |
|-----|---------|
| http://localhost:8096 | Policy Pilot (`ssi-chat-j`) |
| http://localhost:8000/ui/ | Instruction browser |
| http://localhost:8093/ui/ | Payment browser |
| http://localhost:8090 | SSI indexer search console |
| http://localhost:8091 | Demo harness |
| http://localhost:8094 | Authorization service |
| http://localhost:7474/browser/ | Neo4j Browser (admin `neo4j` / `devpassword`; apps use `svc_*`) |
| http://localhost:8080/ui/console | ZITADEL admin |
| http://localhost:3000 | Grafana (SLO / HTTP / domain dashboards) |
| http://localhost:9099 | Prometheus |
| http://localhost:9096/ui/ | SLO catalog author |
| http://localhost:9097/ui/ | SLO provisioner |

## Retrieval quality evaluation

Golden evals for chat live under [`ssi-chat-j/eval/`](../ssi-chat-j/eval/) (**98** HTTP black-box cases). Prove against a warm stack:

```bash
./ssi-chat-j/scripts/prove-eligibility.sh
```

See [`ssi-chat-j/eval/README.md`](../ssi-chat-j/eval/README.md) and [Intent Determination](intent-determination.md).
