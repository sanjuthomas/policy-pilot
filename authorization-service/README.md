# Authorization Service

Stateless **OPA gateway** for the demo stack. Only this service talks to OPA at runtime.

Domain services (instruction-service, payment-service) call authz for lifecycle allow/deny and batch eligible-approvers evaluation. Authz reads candidate users from `zitadel-seed/users.yaml` — it has **no MongoDB** and does not call instruction-service or payment APIs.

## URLs (Docker)

| URL | Description |
|-----|-------------|
| http://localhost:8094/docs | OpenAPI |
| http://localhost:8094/ui/ | User directory browser (platform admin) |
| http://localhost:8094/api/v1/authorization/* | Policy evaluation API (service accounts only) |

## Who calls authz

| Caller | Endpoints | Auth |
|--------|-----------|------|
| **instruction-service** | `POST …/instructions/evaluate`, `POST …/instructions/eligible-approvers` | `svc-instruction` bearer token; user JWT in `X-On-Behalf-Of` for lifecycle evaluate |
| **payment-service** | `POST …/payments/evaluate`, `POST …/payments/eligible-approvers` | `svc-payment` bearer token; user JWT in `X-On-Behalf-Of` for lifecycle evaluate |
| **Platform admin** | `/ui/*`, `/api/ui/users` | `admin-001` (ZITADEL JWT) |

**Not callers:** ssi-chat (uses domain eligible-approvers APIs), ssi-indexer (Kafka consumer only; projects graph from streamed events), demo harness, Kafka Connect, sequence-service.

Policy denials evaluated here surface as `ALERT` security events in Mongo and, after Kafka Connect + ssi-indexer, as `SecurityEvent` nodes linked via `FOR` → version in Neo4j. See [neo4j-graph-model/PHASE-0.md](../neo4j-graph-model/PHASE-0.md).

## Service API (programmatic)

All routes under `/api/v1/authorization` require a bearer token for an authorized service account (`svc-instruction` or `svc-payment`).

### Lifecycle evaluate (On-Behalf-Of)

When the domain service forwards a user session:

```
Authorization: Bearer <svc-instruction|svc-payment token>
X-Session-Id: <service session>
X-On-Behalf-Of: <user access token>
X-On-Behalf-Of-Session-Id: <user session>   # optional
```

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/instructions/evaluate` | Instruction lifecycle allow/deny |
| POST | `/payments/evaluate` | Payment lifecycle allow/deny |

Without `X-On-Behalf-Of`, the request body must include an inline `subject` (used only for non-interactive paths).

### Eligible approvers (service-only)

Batch OPA evaluation over candidates from `users.yaml`. No user OBO — compliance auth is enforced on the domain service before it calls authz.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/instructions/eligible-approvers` | Who can approve this instruction? |
| POST | `/payments/eligible-approvers` | Who can approve this payment? |

## OPA

Authz posts to OPA Data API (`/v1/data/instruction/lifecycle/…`, `/v1/data/payment/lifecycle/…`).

| Variable | Default (Docker) |
|----------|------------------|
| `OPA_URL` | `http://opa:8181` |

OPA itself is **unauthenticated** in this demo — see root README for production guidance.

## Configuration

| Variable | Default |
|----------|---------|
| `USERS_FILE` | `/app/zitadel-seed/users.yaml` |
| `AUTHORIZED_SERVICE_USER_IDS` | `svc-instruction,svc-payment` |
| `OIDC_ISSUER_URL` | `http://localhost:8080` |
| `ZITADEL_SERVICE_PAT_FILE` | `/zitadel/bootstrap/login-client.pat` |

## Run locally

```bash
cd authorization-service
pip install -e .
authorization-service   # :8094
```

Requires OPA (with policies seeded), ZITADEL, and `users.yaml` mounted or on disk.

## Docker

```bash
docker compose up -d authorization-service
```

Depends on `opa-policy-seed` completing successfully (OPA policies compiled and smoke-tested). `/health` reports `DEGRADED` when OPA has fewer than 11 policies or the CREATE smoke evaluation fails.
