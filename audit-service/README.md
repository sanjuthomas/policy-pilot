# Technology Auditor Console

Standalone, read-only evidence application for members of the ZITADEL
`TECH_AUDITORS` group. It runs on **http://localhost:8097** as Compose service
`audit-service`.

The console centralizes the read surfaces that used to live on instruction-service,
payment-service, and chat. Those services still create the source records; this
application only reads and presents them.

## What auditors can inspect

| UI | Contents |
|----|----------|
| **Security events** | One filterable feed across instruction and payment events, with full Mongo event detail |
| **Audit records** | Governed Create Payment execution, actor, request, interpretation, timeline, timing, outcome, result, and linked policy evidence |
| **OPA evidence** | Original evaluate request/response and complete linked payment security event |

The Audit records list shows the linked security-event id as a hyperlink. On the
execution detail page, **Load linked evidence** resolves the source as follows:

1. Prefer `governance.security_event_id` after payment-service completes the write.
2. Load the original event from `security_events.payment_service`.
3. Display `details.authorization.evaluate_request` and `evaluate_response`.
4. Before confirmation, or when execution stops before payment creation, display
   the provisional `governance.policy_exchange` instead.

The service does **not** create a second OPA audit record. The authoritative policy
decision remains on the security event. Scientific-notation amounts in older OPA
basis text are humanized when displayed (for example, `1e+06` → `$1 million`).

## Access control and demo users

Every data API requires a valid ZITADEL session and exact membership in
`TECH_AUDITORS`. `TECH_AUDITOR` is the users' descriptive role; the group is the
console access gate. It does not grant payment or instruction mutation rights.

| User id | Name | Role | Group | Password |
|---------|------|------|-------|----------|
| `audit-001` | Taylor Brooks | `TECH_AUDITOR` | `TECH_AUDITORS` | `Password1!` |
| `audit-002` | Riley Quinn | `TECH_AUDITOR` | `TECH_AUDITORS` | `Password1!` |
| `audit-003` | Casey Nguyen | `TECH_AUDITOR` | `TECH_AUDITORS` | `Password1!` |

These are local demo credentials from
[`zitadel-seed/users.yaml`](../zitadel-seed/users.yaml), not production defaults.
After changing the seed file, rerun the
[`zitadel-seed`](../zitadel-seed/README.md) process because the application reads
the live ZITADEL directory, not YAML.

## Data sources

The application connects directly to the shared MongoDB replica set:

| Evidence | MongoDB namespace |
|----------|-------------------|
| Instruction security events | `security_events.instruction_service` |
| Payment security events | `security_events.payment_service` |
| Governed activity executions | `ssi_cash_activities.audit_executions` |

Security-event generation, Mongo transactions, Kafka CDC, and Neo4j indexing remain
owned by the domain services and ssi-indexer.

## Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Security events and Audit records UI |
| GET | `/events/{source}/{event_id}` | Full instruction or payment event |
| GET | `/audit/{execution_id}` | Governed activity detail |
| POST | `/api/auth/login` | Create ZITADEL session |
| GET | `/api/me` | Resolve and authorize the current auditor |
| GET | `/api/security-events` | Unified event list (`source`, `severity`, `limit`) |
| GET | `/api/security-events/{source}/{event_id}` | Full source event |
| GET | `/api/audit-executions` | All audit executions (`limit`) |
| GET | `/api/audit-executions/{execution_id}` | Full audit execution |
| GET | `/api/audit-executions/{execution_id}/opa` | Linked or provisional OPA evidence |
| GET | `/health` | Liveness |

The HTML shell is public, but all evidence APIs are group-gated.

## Local use

From the repository root:

```bash
docker compose up -d --build audit-service
open http://localhost:8097
```

For a fresh ZITADEL volume, seed users first:

```bash
PAT=$(docker exec zitadel-login cat /zitadel/bootstrap/login-client.pat | tr -d '\n')
cd zitadel-seed
ZITADEL_PAT="$PAT" python3 seed.py
```

## Configuration

| Variable | Docker value / default | Purpose |
|----------|------------------------|---------|
| `MONGODB_URI` | `mongodb://mongodb:27017/?replicaSet=rs0` | Shared Mongo replica set |
| `SECURITY_EVENTS_DATABASE` | `security_events` | Security-event database |
| `INSTRUCTION_EVENTS_COLLECTION` | `instruction_service` | Instruction events |
| `PAYMENT_EVENTS_COLLECTION` | `payment_service` | Payment events |
| `AUDIT_DATABASE` | `ssi_cash_activities` | Governed activity database |
| `AUDIT_COLLECTION` | `audit_executions` | Audit execution collection |
| `REQUIRED_GROUP` | `TECH_AUDITORS` | Exact ZITADEL group gate |
| `ZITADEL_SERVICE_PAT_FILE` | `/zitadel/bootstrap/login-client.pat` | Session and metadata resolution |
| `INITIAL_LIMIT` | `200` | Default list size (maximum 1000) |

## Verification

```bash
ruff check src/ --select E,F,W,I --ignore E501
pytest --cov=audit_console --cov-report=term-missing --cov-fail-under=80
```
