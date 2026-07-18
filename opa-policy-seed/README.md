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
│   ├── policy_catalog.rego      # Single source: role/group + summary + gate_predicates
│   ├── lifecycle.rego           # allow rules (reads catalog for identity gates)
│   └── policy_summary.rego      # Derived from action_catalog for chat
└── payment/
    ├── common.rego              # LOB coverage, creator≠approver, subordinate check
    ├── amount_limits.rego       # Amount-limit clubs from ZITADEL groups
    ├── violations.rego          # Violation catalog + is_alert helper
    ├── allow_basis.rego         # Allow reasons for success audit trail
    ├── policy_catalog.rego      # Single source: role/group + summary + gate_predicates
    ├── lifecycle.rego           # allow rules (reads catalog for identity gates)
    └── policy_summary.rego      # Derived from action_catalog for chat
```

`validate_policy_catalog.py` (also run by `opa-policy-seed` and authorization-service tests) fails if a lifecycle allow rule drops a `gate_predicates` entry or stops using `catalog_role_ok` / `catalog_group_ok`.
## Instruction authorization

| Actor | Roles | Scope |
|-------|-------|-------|
| Middle office | `INSTRUCTION_CREATOR`, `MIDDLE_OFFICE` | Create/update/submit/cancel; **VIEW** only for LOBs in `covering_lobs` (or own creations) |
| Profit center | `INSTRUCTION_APPROVER` + `lob` | Approve/reject/suspend; **VIEW** when `subject.lob` matches `owning_lob` |
| Payment staff | `PAYMENT_CREATOR` / `FUNDING_APPROVER` + `covering_lobs` | **VIEW**/USE when covering includes instruction LOB |
| Platform admin | `PLATFORM_ADMIN` / `ADMIN` | Cross-LOB **VIEW** for operators |

`VIEW` / `USE` / `RELEASE_USE` require both a viewer role **and** data-level BU entitlement (`can_view_instruction_data`). Role alone is not enough.

Valid LOB values: `FICC`, `FX`, or `DESK_<name>`.

### Actions governed

`CREATE`, `UPDATE`, `CANCEL`, `SUBMIT`, `APPROVE`, `REJECT`, `SUSPEND`, `REACTIVATE`, `USE`, `VIEW`

Key rules: creator cannot approve own instruction; approver must not report directly to creator (inversion of control); manager cannot approve direct report’s instruction; approver LOB must match instruction LOB; approver title must satisfy the approval matrix. Full control catalog: **[docs/opa-controls.md](../docs/opa-controls.md)**.

Policy denials surface as HTTP 403 and `ALERT` security events in Mongo (streamed to Kafka by Connect). Authorization-service queries:

| OPA endpoint | Purpose |
|--------------|---------|
| `/v1/data/instruction/lifecycle/allow` | Boolean decision |
| `/v1/data/instruction/lifecycle/allow_basis` | Human-readable allow reasons (stored on security events) |
| `/v1/data/instruction/lifecycle/violations` | Named denial codes |
| `/v1/data/instruction/lifecycle/is_alert` | Escalation severity |

The same pattern applies under `/v1/data/payment/lifecycle/…` for payments.

On allow, domain services build `details.authorization.summary` from `allow_basis` and persist it on Mongo security events; **Kafka Connect** relays those documents to Kafka and **ssi-indexer** indexes them into Neo4j (`SecurityEvent`, `ACTED_AS`, `FOR` → version, vector docs) for RAG **Who / When / Why** answers. Graph edge names: [neo4j-graph-model/README.md](../neo4j-graph-model/README.md).

## Payment authorization

| Actor | Roles | Scope |
|-------|-------|-------|
| Middle office | `PAYMENT_CREATOR` + `covering_lobs` | Create payments for covered LOBs |
| Front office | `PAYMENT_CREATOR` + `lob` | Submit payments for own desk LOB |
| Middle office | `FUNDING_APPROVER` + `covering_lobs` | Approve/reject submitted payments for covered LOBs |

### Actions governed

`CREATE`, `SUBMIT`, `APPROVE`, `REJECT`, `CANCEL`

Key rules: payment amount within user's club ceiling and absolute $100 B limit; instruction status must be `APPROVED` and not expired; creator cannot approve own payment; approver must not report directly to creator; approver must cover the instruction LOB. Full control catalog: **[docs/opa-controls.md](../docs/opa-controls.md)**.

Policy denials surface as HTTP 403 and `ALERT` security events in Mongo (streamed to Kafka by Connect).

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
      "action": "CREATE",
      "subject": {
        "user_id": "pay-101",
        "roles": ["PAYMENT_CREATOR"],
        "groups": ["MIDDLE_OFFICE", "UP_TO_100_MILLION_CLUB"],
        "covering_lobs": ["FICC", "FX"]
      },
      "payment": {
        "amount": 1000000,
        "instruction_owning_lob": "FICC",
        "instruction_status": "APPROVED",
        "instruction_end_date": "2027-06-24T00:00:00Z",
        "created_by": { "user_id": "pay-101" }
      }
    }
  }'
```

## Docker

OPA loads policies from the mounted `policies/` directory on every start (`opa run --server /policies` in Compose). Restarting the `opa` container therefore does **not** require a separate upload step.

The `opa-policy-seed` service waits until OPA has compiled those policies and passes a CREATE smoke evaluation before dependent services start. Use it as a startup gate only — not for reloading policies after an OPA restart.

For manual hot-reload during Rego development (optional):

```bash
docker compose run --rm --entrypoint python opa-policy-seed /app/upload_policies.py
```

OPA API (unauthenticated demo): http://localhost:8181
