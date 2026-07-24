# ssi-chat-j

Java / Spring Boot + Spring AI **A/B** chat experiment. Python `ssi-chat` stays on **8092**; this service listens on **8096**.

Not wired into the root `docker-compose.yml` yet — run locally with Maven against a warm stack.

## Current surface

- `GET /health`
- `POST /api/auth/login` (ZITADEL session; roles/audiences from seed directory)
- `GET /api/index-integrity` (proxies ssi-indexer for the shared integrity banner)
- Shared PolicyPilot static UI (build-time copy of assets)
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
- `POST /api/chat` neo4j_direct (in-process Cypher planner + Neo4j as `svc_chat`):
  - alert/denial counts, alert lists, top-denial ranking (Thymeleaf templates)
  - SoD / compliance graph questions (self-approval, mutual, subordinate, duplicates, cross-entity, timeline)
  - subject LOB scope for FO/MO (parity with Python issue #63)
- Observability (Micrometer → OTLP, same chat SLI names as Python; **no Prometheus scrape**):
  - `POST /api/chat/feedback`
  - `GET /api/routing-stats`, `GET /api/feedback-stats`

## Run (Maven)

With the usual Compose stack up (Python chat, payment, instruction, authz, ZITADEL, Neo4j, …):

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

Metrics leave via **OTLP** (`micrometer-registry-otlp` + Micrometer Tracing → OTel). Actuator exposes **health only** — Prometheus registry / `/actuator/prometheus` is intentionally not wired. Series names match Python chat SLIs (`chat.answer.count`, `chat.feedback.count`, `http.server.request.duration`, …) under `service.name=ssi-chat-j`.

## Eligibility golden eval (HTTP black-box)

Cases live under [`eval/`](eval/) (owned by this module — not loaded at Java runtime).

Warm stack with harness entity context (`submitted_payment_id`, `draft_payment_id`, `pending_instruction_id`) and Java chat on `:8096`:

```bash
./ssi-chat-j/scripts/prove-eligibility.sh
```

That runs the three goldens via the temporary Python regression CLI (`--golden` points at `eval/eligibility_golden.yaml`).

Plan / todo: [`docs/ssi-chat-j-plan.md`](../docs/ssi-chat-j-plan.md), [`docs/ssi-chat-j-todo.md`](../docs/ssi-chat-j-todo.md).
