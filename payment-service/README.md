# Payment Service

REST API for **cash payment lifecycle** against approved SSI instructions.

Middle-office users create payments on behalf of trading desks. Front-office desk users submit them for approval. Funding approvers approve or reject. **Authorization-service** (via OPA) enforces amount limits, LOB coverage, segregation of duties, and reporting-line rules before every mutation.

## URLs (Docker)

| URL | Description |
|-----|-------------|
| http://localhost:8093/docs | OpenAPI |
| http://localhost:8093/ui/ | Payment browser |
| http://localhost:8093/ui/security-events/ | Security event monitor (Mongo change stream) |
| http://localhost:8093/api/v1/payments | REST API |

## Authentication

Production path uses **ZITADEL JWT** (`AUTH_MODE=jwt` in Docker). Demo users are in `zitadel-seed/users.yaml` (password `Password1!`).

Key roles:

| Role | Who | Actions |
|------|-----|---------|
| `PAYMENT_CREATOR` | Middle office (`pay-101` …) or front office (`fo-ficc-101` …) | Create payments; front office submits |
| `FUNDING_APPROVER` | Middle office approvers (`pay-201` …) | Approve / reject submitted payments |

Amount limits are enforced via ZITADEL groups (`UP_TO_100_MILLION_CLUB`, `UP_TO_1_BILLION_CLUB`, `UP_TO_100_BILLION_CLUB`).

## Policy authorization

Payment-service does **not** call OPA directly. Lifecycle mutations use **authorization-service** with On-Behalf-Of (`svc-payment` + user JWT), same pattern as instruction-service.

Instruction reads for create/approve use **instruction-service** with OBO when a user token is present, or a service-only GET for eligibility batch paths.

| Authz endpoint | When |
|----------------|------|
| `POST /api/v1/authorization/payments/evaluate` | Create, submit, approve, reject |
| `POST /api/v1/authorization/payments/eligible-approvers` | Compliance “who can approve?” |

### Compliance: eligible approvers

```bash
curl -s -X POST "http://localhost:8093/api/v1/payments/{payment_id}/eligible-approvers" \
  -H "Authorization: Bearer <compliance-or-admin-token>" \
  -H "X-Session-Id: <session-id>"
```

## Payment lifecycle

```
DRAFT  →  SUBMITTED  →  APPROVED | REJECTED
                      ↘ CANCELLED (if instruction invalid at approval time)
```

| Step | Actor | Policy action (via authz) |
|------|-------|--------------|
| Create | Middle office with `covering_lobs` | `CREATE_PAYMENT` |
| Submit | Front-office user whose `lob` matches instruction LOB | `SUBMIT_PAYMENT` |
| Approve | Funding approver covering the instruction LOB | `APPROVE_PAYMENT` |
| Reject | Funding approver covering the instruction LOB | `REJECT_PAYMENT` |

At create time the service validates the linked instruction is `STANDING` or `SINGLE_USE` and not expired. At approval time it re-checks instruction version drift, status, and dates — invalid instructions auto-cancel the payment.

## Security events (SIEM)

Every authorized action or policy denial emits a document to MongoDB `security_events.payment-service` and publishes to Kafka topic `payment-security-events`. A payment state fact is also published to `ssi-payments`.

| Outcome | Severity | When |
|---------|----------|------|
| Authorized action | `INFO` | Policy allowed (via authorization-service → OPA) |
| Policy denial | `ALERT` | Policy denied before any write |

Authorized actions store `details.authorization` (`allow_basis`, `summary`, subject snapshot) and set `event.reason` to the summary. Same pattern as instruction-service.

Payment mutations write the payment record and matching security event in a **single MongoDB transaction** (replica set required).

## Storage

| Store | Location |
|-------|----------|
| MongoDB | `ssi_cash_activities.payments` |
| MongoDB | `security_events.payment-service` |
| Kafka | `payment-security-events`, `ssi-payments` |

## Example: create payment

Requires an approved instruction ID from instruction-service and a ZITADEL session token for a `PAYMENT_CREATOR` user.

```bash
curl -s -X POST http://localhost:8093/api/v1/payments \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <zitadel-session-token>' \
  -H 'X-Session-Id: <session-id>' \
  -d '{
    "instruction_id": "<approved-instruction-uuid>",
    "amount": 1000000.0,
    "currency": "USD",
    "value_date": "2026-06-26T00:00:00Z"
  }'
```

Subsequent lifecycle calls: `POST /payments/{id}/submit`, `POST /payments/{id}/approve`, `POST /payments/{id}/reject`.

## Run locally

```bash
cd payment-service
pip install -e .
payment-service   # :8093
```

Requires MongoDB, **authorization-service**, instruction-service (instruction reads), Kafka, and ZITADEL — see root `docker-compose.yml`.

| Variable | Default |
|----------|---------|
| `AUTHORIZATION_SERVICE_URL` | `http://authorization-service:8094` |
| `ILM_URL` | `http://instruction-service:8000` |

## Docker

```bash
docker compose up -d payment-service
```
