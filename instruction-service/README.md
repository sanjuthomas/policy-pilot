# Instruction Lifecycle Manager

REST API for **SSI settlement route template** lifecycle — domestic and international wires.

An instruction defines the **route** (funding account, debtor/creditor, bank chain, currency, validity, approval). It is **not** a payment message — no amount or value date on the template.

Middle office analysts create instructions **on behalf of** P&L profit centers (`owning_lob`). Treasury bank-liquidity instructions are **out of scope**.

## URLs (Docker)

| URL | Description |
|-----|-------------|
| http://localhost:8000/docs | OpenAPI |
| http://localhost:8000/ui/ | Instruction browser |
| http://localhost:8000/ui/security-events/ | Security event monitor (Mongo-backed) |
| http://localhost:8000/api/v1/instructions | REST API |

## Authentication

Production path uses **ZITADEL JWT** (`AUTH_MODE=jwt` in Docker). The test harness and secured admin UIs use ZITADEL session tokens.

For local header-based testing without JWT, set `AUTH_MODE=headers` and pass subject headers:

| Header | Middle office | Profit center |
|--------|---------------|---------------|
| `X-Subject-User-Id` | `mo-100` | `ficc-201` |
| `X-Subject-Title` | `Analyst` | `Associate` |
| `X-Subject-Roles` | `INSTRUCTION_CREATOR,MIDDLE_OFFICE` | `INSTRUCTION_APPROVER` |
| `X-Subject-Lob` | omit | `FICC` |

Demo users are defined in `zitadel-seed/users.yaml` (password `Password1!`).

## Policy authorization

Instruction-service does **not** call OPA directly. Lifecycle mutations delegate to **authorization-service** via `shared/authz_client`:

1. Service account `svc-instruction` authenticates at startup.
2. On each lifecycle call, if the request includes `Authorization: Bearer <user-token>`, authz receives OBO headers (`svc-*` token + `X-On-Behalf-Of`).
3. Authz evaluates OPA and returns allow/deny, `allow_basis`, and violations.

| Authz endpoint | When |
|----------------|------|
| `POST /api/v1/authorization/instructions/evaluate` | Create, update, submit, approve, reject, suspend, reactivate, use, view |
| `POST /api/v1/authorization/instructions/eligible-approvers` | Compliance “who can approve?” (service token only) |

### Compliance: eligible approvers

```bash
curl -s -X POST "http://localhost:8000/api/v1/instructions/{instruction_id}/eligible-approvers" \
  -H "Authorization: Bearer <compliance-or-admin-token>" \
  -H "X-Session-Id: <session-id>"
```

Requires `COMPLIANCE_ANALYST`, `COMPLIANCE_OFFICER`, or `PLATFORM_ADMIN`. The service loads the instruction, then calls authz for batch OPA evaluation.

## Owning profit center (`owning_lob`)

| Value | Meaning |
|-------|---------|
| `FICC` | Fixed income, currencies & commodities |
| `FX` | Foreign exchange desk |
| `DESK_<name>` | Other profit centers, e.g. `DESK_RATES` |

## Instruction schema (summary)

| Field | Notes |
|-------|-------|
| `instruction_type` | `STANDING` or `SINGLE_USE` |
| `wire_scope` | `DOMESTIC` or `INTERNATIONAL` |
| `currency` | ISO 4217 route currency (required) |
| `funding_account`, `debtor`, `creditor`, agents | Settlement route |
| `effective_date`, `end_date` | Template validity |
| `created_by`, `approved_by`, `rejected_by` | Lifecycle parties (copied on each version) |

No `instructed_amount`, `payment_identification`, or remittance fields.

## Instruction lifecycle

```
DRAFT / PENDING  →  STANDING | SINGLE_USE | REJECTED
STANDING         →  SUSPENDED  →  STANDING (reactivate)
SINGLE_USE       →  USED (after payment use)
DRAFT / PENDING  →  DELETED (soft delete)
```

| Step | Actor | Policy action (via authz) |
|------|-------|--------------------------|
| Create | Middle office with `covering_lobs` | `CREATE` |
| Update | Creator while `DRAFT` | `UPDATE` |
| Submit | Creator | `SUBMIT` |
| Approve | Approver covering instruction LOB | `APPROVE` |
| Reject | Approver covering instruction LOB | `REJECT` |
| Suspend / reactivate | Authorized roles | `SUSPEND` / `REACTIVATE` |
| Use | Payment flow | `USE` |
| Soft delete | Creator while `DRAFT` or `PENDING` | `DELETE` (service layer; no HTTP route yet) |

Terminal states (`REJECTED`, `USED`, `EXPIRED`, `DELETED`) block further mutations — each change appends a new version row; existing history is never overwritten.

## Storage (append-only versions)

Instructions are stored as **versioned rows** in MongoDB. Each mutation closes the current row and inserts the next version.

| Concept | Value |
|---------|-------|
| Document `_id` | `{instruction_id}\|{version_number}` |
| Current row marker | `out` = `9999-12-31T23:59:59Z` (`INSTRUCTION_CURRENT_OUT`) |
| Instruction IDs | Allocated by **sequence-service** (`next_instruction_id`) |
| Concurrency | Optimistic locking on append — concurrent writes return HTTP 409 |

| Store | Location |
|-------|----------|
| MongoDB | `ssi_cash_instructions.instructions` |

`GET /api/v1/instructions/{id}/versions` returns the full version history for an instruction.

## Security events (SIEM)

Every authorized create/read/mutation (and policy denial before write) emits an **append-only** document to MongoDB `security_events.instruction_service`.

**Instruction mutations** write the instruction version and the matching security event in a **single MongoDB transaction** (replica set required).

| Outcome | Severity | When |
|---------|----------|------|
| Authorized action | `INFO` | Policy allowed (via authorization-service → OPA) |
| Policy denial | `ALERT` | Policy denied before any write |

Security event documents:

- **`_id`** — sequence-allocated id from **sequence-service** (`next_security_event_id`); not stored as a separate `event_id` field
- **API/UI** — `serialize_security_event` exposes `event_id` from `_id` for clients
- **`instruction_snapshot`** — full instruction state at event time for downstream indexing

Key OPA rules include: creator cannot approve own instruction; approver must not report directly to creator (inversion of control); approver LOB must match instruction LOB.

Events use ECS-style fields (`event`, `actor`, `resource`, `source`).

### Authorization audit block

On every policy decision the service stores `details.authorization`:

| Field | Content |
|-------|---------|
| `summary` | Human-readable allow/deny sentence |
| `allow_basis` | Policy checks that passed (allows) |
| `violations` | Named violation codes (denials) |
| `subject_at_decision` | Actor snapshot at decision time |
| `resource_context` | Instruction fields used by OPA |

On successful actions, `event.reason` is set to `authorization.summary`.

**Excluded actors:**

| User / setting | Effect |
|----------------|--------|
| `etl-reader` | No security events at all (`SECURITY_EVENT_EXCLUDED_USER_IDS`) |
| `admin-001` | No **VIEW** security events on `GET /instructions` or `GET /instructions/{id}` (`SECURITY_EVENT_VIEW_EXCLUDED_USER_IDS`, default `admin-001`) |

The instruction browser UI (`GET /api/ui/instructions`) reads Mongo directly and does not record VIEW events. Downstream indexing is **Mongo → Kafka Connect → Kafka → ssi-indexer**; this service does not publish to Kafka.

## Example: create instruction

```bash
curl -s -X POST http://localhost:8000/api/v1/instructions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <zitadel-session-token>' \
  -H 'X-Session-Id: <session-id>' \
  -d '{
    "instruction_type": "SINGLE_USE",
    "owning_lob": "FICC",
    "wire_scope": "DOMESTIC",
    "currency": "USD",
    "funding_account": {
      "account_id": "DDA-FICC-01",
      "account_name": "FICC Client Payments",
      "owning_lob": "FICC"
    },
    "debtor": { "name": "Client Fund A", "postal_address": { "country": "US" } },
    "debtor_account": {
      "identification_scheme": "PROPRIETARY",
      "identification": "DDA-FICC-01",
      "currency": "USD"
    },
    "debtor_agent": {
      "financial_institution": {
        "scheme": "CLEARING_SYSTEM",
        "identification": "021000021",
        "clearing_system_id": "USABA"
      }
    },
    "creditor": { "name": "Counterparty LLC", "postal_address": { "country": "US" } },
    "creditor_account": {
      "identification_scheme": "PROPRIETARY",
      "identification": "9988776655",
      "currency": "USD"
    },
    "creditor_agent": {
      "financial_institution": {
        "scheme": "CLEARING_SYSTEM",
        "identification": "011401533",
        "clearing_system_id": "USABA"
      }
    },
    "charge_bearer": "SHAR",
    "effective_date": "2026-06-24T00:00:00Z",
    "end_date": "2027-06-24T00:00:00Z"
  }'
```

Subsequent lifecycle calls: `POST /instructions/{id}/submit`, `approve`, `reject`, `suspend`, `reactivate`, `use`.

## Run locally

```bash
cd instruction-service
pip install -e .
uvicorn inst.main:app --reload --port 8000
```

Requires MongoDB (replica set), **authorization-service**, **sequence-service**, and (for JWT mode) ZITADEL — see root `docker-compose.yml`.

| Variable | Default |
|----------|---------|
| `MONGODB_URI` | `mongodb://localhost:27017/?replicaSet=rs0` |
| `AUTHORIZATION_SERVICE_URL` | `http://authorization-service:8094` |
| `SEQUENCE_SERVICE_URL` | `http://localhost:8095` |
| `SECURITY_EVENT_EXCLUDED_USER_IDS` | `etl-reader` |
| `SECURITY_EVENT_VIEW_EXCLUDED_USER_IDS` | `admin-001` |
