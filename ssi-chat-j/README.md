# ssi-chat-j

Java / Spring Boot + Spring AI **PolicyPilot chat** — the product chat surface. Listens on **8096** (Compose service `ssi-chat-j`).

The former Python `ssi-chat` UI and `cypher-builder-svc` HTTP bridge are retired (local-only archives). Chat plans Neo4j Cypher **in-process** (`com.sanjuthomas.policypilot.cypher`). `shared/cypher_builder` remains for the **indexer** Search Console only.

## Current surface

- `GET /health`
- `POST /api/auth/login` (ZITADEL session; roles/audiences from seed directory)
- `GET /api/index-integrity` (proxies ssi-indexer for the shared integrity banner)
- PolicyPilot static UI under `src/main/resources/static/`
- `POST /api/chat` eligibility lanes:
  - payment APPROVE → payment-service `eligible-approvers`
  - payment SUBMIT → authz `eligible-submitters`
  - instruction APPROVE → instruction-service `eligible-approvers`
- `POST /api/chat` document extraction (`path=document_extraction`):
  - instruction → instruction-service `GET /api/v1/instructions/{id}` (OBO)
  - payment → payment-service `GET /api/v1/payments/{id}` (OBO)
- `POST /api/chat` policy directory (amount club):
  - authz `payment-amount-limits` + `groups/{club}/members`
- `POST /api/chat` policy summary (normative OPA):
  - authz `policy-summary?domain=&action=`
- `POST /api/chat` me-centric lane (`path=me` → recorded as `eligibility` + `me.*` intents)
- `POST /api/chat` neo4j_direct (in-process Cypher planner + Neo4j as `svc_chat`)
- `POST /api/chat` payment skills (`path=skill`) — create / submit / approve / cancel
- Observability (Micrometer → OTLP; **no Prometheus scrape**):
  - `POST /api/chat/feedback`
  - `GET /api/routing-stats`, `GET /api/feedback-stats`

## Intent routing

Natural-language intent uses Spring AI structured `RouterDecision` (path + LLM slots). Open-vocabulary filters (status, type, amounts, skill dates) are **slots**, not synonym tables or free-text amount/date regex. Regex is OK for stable tokens (sequence ids, explicit clubs) after path is known. Details: [`docs/intent-determination.md`](../docs/intent-determination.md), [`AGENTS.md`](AGENTS.md).

## Run (Compose)

```bash
docker compose up -d --build ssi-chat-j
curl -s http://localhost:8096/health
```

## Run (Maven)

With the usual Compose stack up (payment, instruction, authz, ZITADEL, Neo4j, indexer, …):

```bash
cd ssi-chat-j
# Optional: point at the mesh collector (defaults match Python OTEL_* )
# export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
# export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
# export OTEL_SDK_DISABLED=true   # local only — still records in-process meters
# export NEO4J_URI=bolt://localhost:7687
# export INDEXER_URL=http://localhost:8090   # integrity banner proxy (default)
mvn -q spring-boot:run
curl -s http://localhost:8096/health
```

Coverage: `mvn verify` (≥ 80% JaCoCo). See [`AGENTS.md`](AGENTS.md).

## Golden eval (HTTP black-box)

**98** cases in [`eval/eligibility_golden.yaml`](eval/eligibility_golden.yaml). Prove against a warm stack:

```bash
./ssi-chat-j/scripts/prove-eligibility.sh
```

Family breakdown: [`eval/README.md`](eval/README.md).

Historical plan / todo: [`docs/ssi-chat-j-plan.md`](../docs/ssi-chat-j-plan.md), [`docs/ssi-chat-j-todo.md`](../docs/ssi-chat-j-todo.md).
