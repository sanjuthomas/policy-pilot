# Authorization Service

Stateless **OPA gateway** for the demo stack. Only this service talks to OPA at runtime.

Domain services (instruction-service, payment-service) call authz for lifecycle allow/deny and batch eligible-approvers evaluation. Authz loads the user directory from **ZITADEL** (seeded from `zitadel-seed/users.yaml`) — it has **no MongoDB** and does not call instruction-service or payment APIs.

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
| **ssi-chat** | `GET …/groups/{group}/members`, `GET …/policy-summary` | Compliance analyst JWT |
| **Platform admin** | `/ui/*`, `/api/ui/users` | `admin-001` (ZITADEL JWT) |

**Not callers:** ssi-indexer (Kafka consumer only; projects graph from streamed events), demo harness, Kafka Connect, sequence-service.

Policy denials evaluated here surface as `ALERT` security events in Mongo and, after Kafka Connect + ssi-indexer, as `SecurityEvent` nodes linked via `FOR` → version in Neo4j. See [neo4j-graph-model/README.md](../neo4j-graph-model/README.md).

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

Lifecycle evaluate **requires** `X-On-Behalf-Of` (verified user JWT). An optional inline `subject` may also be sent; when present, identity fields must match the OBO-derived subject. Inline subject alone is rejected (see issue #14).

### Eligible approvers (service-only)

Batch OPA evaluation over candidates from the live ZITADEL directory ("who can approve?"). No user OBO — service account auth only; compliance auth is enforced on the domain service before it calls authz. This is discovery/reporting, not an approval action.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/instructions/eligible-approvers` | Who can approve this instruction? |
| POST | `/payments/eligible-approvers` | Who can approve this payment? |
| GET | `/groups/{group}/members` | Members of a ZITADEL group (compliance JWT) — includes `lob` and `covering_lobs` |
| GET | `/policy-summary` | Normative OPA policy summary for `payment` or `instruction` (compliance JWT) |

Query params for group members: `role`, `covering_lob`.

Query params for policy summary: `domain` (`payment`|`instruction`), `action` (default `APPROVE`).

## OPA

Authz posts to OPA Data API (`/v1/data/instruction/lifecycle/…`, `/v1/data/payment/lifecycle/…`).

| Variable | Default (Docker) |
|----------|------------------|
| `OPA_URL` | `http://opa:8181` |

OPA itself is **unauthenticated** in this demo — see root README for production guidance.

## Configuration

| Variable | Default |
|----------|---------|
| `EMAIL_DOMAIN` | `ssi.local` (login name suffix for directory UI) |
| `USER_DIRECTORY_CACHE_TTL_SECONDS` | `60` |
| `AUTHORIZED_SERVICE_USER_IDS` | `svc-instruction,svc-payment` |
| `OIDC_ISSUER_URL` | `http://localhost:8080` |
| `ZITADEL_SERVICE_PAT_FILE` | `/zitadel/bootstrap/login-client.pat` |

## Run locally

```bash
cd authorization-service
pip install -e .
authorization-service   # :8094
```

Requires OPA (with policies seeded) and ZITADEL with demo users seeded (`zitadel-seed`).

## Docker

```bash
docker compose up -d authorization-service
```

Depends on `opa-policy-seed` completing successfully (OPA policies compiled and smoke-tested). `/health` reports `DEGRADED` when OPA has fewer than 15 policies or the CREATE smoke evaluation fails.
