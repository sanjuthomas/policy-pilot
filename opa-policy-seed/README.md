# OPA Policy Seed

Version-controlled **Rego policies** uploaded to OPA on Docker Compose startup.

At runtime, only **authorization-service** calls OPA. Domain services never hit OPA directly — they POST to authz, which evaluates:

- `POST /v1/data/instruction/lifecycle/allow` — instruction lifecycle
- `POST /v1/data/payment/lifecycle/allow` — payment lifecycle

The curl examples below are for **local debugging** of Rego rules. In production, restrict OPA to an internal network reachable only from authz.

## Layout

```
policies/
├── instruction/
│   ├── common.rego              # Shared helpers (roles, LOB, dates, subordinate check)
│   ├── approval_matrix.rego     # Who may approve whom by title + LOB
│   ├── lifecycle_rules.rego     # Valid state transitions
│   ├── violations.rego          # Violation catalog + is_alert helper
│   ├── allow_basis.rego         # Allow reasons for success audit trail
│   └── lifecycle.rego           # allow rules per action
└── payment/
    ├── common.rego              # LOB coverage, creator≠approver, subordinate check
    ├── amount_limits.rego       # Amount-limit clubs from ZITADEL groups
    ├── violations.rego          # Violation catalog + is_alert helper
    ├── allow_basis.rego         # Allow reasons for success audit trail
    └── lifecycle.rego           # CREATE / SUBMIT / APPROVE / REJECT rules
```

## Instruction authorization

| Actor | Roles | Scope |
|-------|-------|-------|
| Middle office | `INSTRUCTION_CREATOR`, `MIDDLE_OFFICE` | Create, update, submit, delete (draft/pending), view all LOBs |
| Profit center | `INSTRUCTION_APPROVER` + `lob` | Approve, reject, suspend, use, view matching `owning_lob` |

Valid LOB values: `FICC`, `FX`, or `DESK_<name>`.

### Actions governed

`CREATE`, `UPDATE`, `DELETE`, `SUBMIT`, `APPROVE`, `REJECT`, `SUSPEND`, `REACTIVATE`, `USE`, `VIEW`

Key rules: creator cannot approve own instruction; approver must not report directly to creator (inversion of control); approver LOB must match instruction LOB; approver title must satisfy the approval matrix.

Policy denials surface as HTTP 403 and `ALERT` security events on Kafka. Authorization-service queries:

| OPA endpoint | Purpose |
|--------------|---------|
| `/v1/data/instruction/lifecycle/allow` | Boolean decision |
| `/v1/data/instruction/lifecycle/allow_basis` | Human-readable allow reasons (stored on security events) |
| `/v1/data/instruction/lifecycle/violations` | Named denial codes |
| `/v1/data/instruction/lifecycle/is_alert` | Escalation severity |

The same pattern applies under `/v1/data/payment/lifecycle/…` for payments.

On allow, domain services build `details.authorization.summary` from `allow_basis` and persist it on Mongo security events, Kafka facts, and (via ETL) Neo4j multimodal documents for RAG **Who / When / Why** answers.

## Payment authorization

| Actor | Roles | Scope |
|-------|-------|-------|
| Middle office | `PAYMENT_CREATOR` + `covering_lobs` | Create payments for covered LOBs |
| Front office | `PAYMENT_CREATOR` + `lob` | Submit payments for own desk LOB |
| Middle office | `FUNDING_APPROVER` + `covering_lobs` | Approve/reject submitted payments for covered LOBs |

### Actions governed

`CREATE_PAYMENT`, `SUBMIT_PAYMENT`, `APPROVE_PAYMENT`, `REJECT_PAYMENT`

Key rules: payment amount within user's club ceiling and absolute $100 B limit; instruction must be `STANDING` or `SINGLE_USE` and not expired; creator cannot approve own payment; approver must not report directly to creator; approver must cover the instruction LOB.

Policy denials surface as HTTP 403 and `ALERT` security events on Kafka.

## Evaluate locally (instruction)

Debug Rego directly against OPA (demo only — no auth on OPA):

```bash
curl -s http://localhost:8181/v1/data/instruction/lifecycle/allow \
  -H 'Content-Type: application/json' \
  -d '{
    "input": {
      "action": "CREATE",
      "subject": {
        "roles": ["INSTRUCTION_CREATOR", "MIDDLE_OFFICE"],
        "title": "Analyst",
        "user_id": "mo-100"
      },
      "instruction": {
        "owning_lob": "FICC",
        "status": "DRAFT",
        "type": "STANDING",
        "effective_date": "2026-06-24T00:00:00Z",
        "end_date": "2027-06-24T00:00:00Z",
        "created_by": { "user_id": "mo-100", "title": "Analyst" }
      },
      "account": { "owning_lob": "FICC" }
    }
  }'
```

## Evaluate locally (payment)

```bash
curl -s http://localhost:8181/v1/data/payment/lifecycle/allow \
  -H 'Content-Type: application/json' \
  -d '{
    "input": {
      "action": "CREATE_PAYMENT",
      "subject": {
        "user_id": "pay-101",
        "roles": ["PAYMENT_CREATOR"],
        "groups": ["MIDDLE_OFFICE", "UP_TO_100_MILLION_CLUB"],
        "covering_lobs": ["FICC", "FX"]
      },
      "payment": {
        "amount": 1000000,
        "instruction_owning_lob": "FICC",
        "instruction_status": "STANDING",
        "instruction_end_date": "2027-06-24T00:00:00Z",
        "created_by": { "user_id": "pay-101" }
      }
    }
  }'
```

## Docker

The `opa-policy-seed` service runs once after `opa` starts and uploads policies from the mounted `policies/` directory.

OPA API (unauthenticated demo): http://localhost:8181
