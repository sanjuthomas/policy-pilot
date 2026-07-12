# Create-payment skill

Policy Pilot’s first **mutation skill**: a scripted multi-step flow that creates a draft payment from natural language, only after an OPA preflight and an explicit **Go / No Go** confirmation.

Skills are **not** free-form LLM tool loops. Steps are fixed; authorization always goes through **authorization-service → OPA**, the same path payment-service uses for `CREATE`.

| | |
|--|--|
| **Package** | [`ssi-chat/src/chat_application/skills/`](../ssi-chat/src/chat_application/skills/) |
| **Demo users** | `pay-101`, `pay-205` (middle-office `PAYMENT_CREATOR`) |
| **Chat mode** | **Payments** |
| **Tag** | **`skill`** (see [sample questions](sample-questions.md)) |

---

## Example

```text
Can you create a payment for instruction ID 20260705-FICC-I-31?
Value date tomorrow; amount: 12 million USD.
```

Sign in as `pay-205` / `Password1!`, select **Payments**, then send the question.

---

## Sequence (happy path)

```mermaid
sequenceDiagram
    actor U as User (browser)
    participant UI as Policy Pilot UI
    participant C as ssi-chat
    participant I as instruction-service
    participant A as authorization-service / OPA
    participant P as payment-service
    participant M as MongoDB

    U->>UI: Create payment (instruction, amount, value date)
    UI->>C: POST /api/chat (Bearer JWT)

    Note over C: Phase 1 — preflight (no mutate)
    C-->>UI: activity: Parsed request…
    C->>I: GET /api/v1/instructions/{id}
    I-->>C: parties, LOB, status, currency
    C-->>UI: activity: Loaded instruction…
    C-->>UI: activity: Checking CREATE for LOB…
    C->>A: POST …/payments/evaluate action=CREATE<br/>(svc-chat + X-On-Behalf-Of user)
    A-->>C: allowed + allow_basis / violations

    alt Denied
        C-->>UI: Stop — violations (no payment created)
    else Allowed
        C-->>UI: activity: Yes — may create…
        C-->>UI: Confirmation card + pending_id<br/>(debtor / creditor / intermediaries)
        Note over C: Pending skill stored (TTL)
        U->>UI: Go
        UI->>C: POST /api/chat/skills/create-payment/confirm<br/>{ pending_id, decision: "go" }

        Note over C: Phase 2 — mutate
        C->>A: Re-check CREATE (optional)
        C->>P: POST /api/v1/payments<br/>(user JWT)
        P->>A: CREATE evaluate (domain path)
        P->>M: Insert payment + security event<br/>(one transaction)
        P-->>C: PaymentResponse (DRAFT)
        C->>A: eligible-approvers (svc-chat)
        C-->>UI: Created report + who can approve
    end

    opt No Go
        U->>UI: No Go
        UI->>C: confirm { decision: "no_go" }
        C-->>UI: Cancelled — no payment created
    end
```

---

## Activity steps (what the user sees)

| Step | Activity / UI | Side effect |
|------|---------------|-------------|
| 1. Detect + parse | Parsed instruction, amount, value date | None |
| 2. Load instruction | Loading / loaded LOB, status, currency | None |
| 3. Preflight CREATE | Checking roles, groups, covering LOBs, amount club… | Authz evaluate only |
| 4. Explain | **Yes** + humanized allow basis, or **No** + stop | None |
| 5. Confirm | Card: instruction, amount, value date, LOB, debtor/creditor names & accounts, intermediaries · **Go** / **No Go** | Pending skill id |
| 6. Create (Go only) | Creating draft… | `POST /api/v1/payments` → Mongo |
| 7. Approvers | Looking up who can approve… | Authz eligible-approvers |
| 8. Report | Payment id, instruction, amount, LOB, eligible approvers | None |

---

## Design rules

| Rule | Meaning |
|------|---------|
| **Scripted pipeline** | Detector + fixed steps — not an agent inventing APIs |
| **OPA stays normative** | Preflight and create both use payment `CREATE` policy |
| **Explain before confirm** | Stream permission reasoning before any Go button |
| **Confirm before mutate** | No Mongo write until **Go** |
| **Fail closed** | Deny, No Go, expired pending, or wrong user → no create |
| **Act as logged-in user** | User JWT on instruction GET and payment CREATE; `svc-chat` OBO for evaluate |

Chat does **not** write Mongo directly. On **Go**, payment-service allocates the id, re-evaluates OPA, and inserts the payment version + security event in one transaction (`ssi_cash_activities.payments` + `security_events.payment_service`). Kafka CDC / indexer then update Neo4j as for any other create.

---

## APIs

| Call | When |
|------|------|
| `POST /api/chat` | Phase 1 — detect skill, return activities + `skill_confirmation` |
| `POST /api/chat/skills/create-payment/confirm` | Phase 2 — `{ "pending_id", "decision": "go" \| "no_go" }` |
| `GET /api/v1/instructions/{id}` | Load SSI parties for the card |
| `POST /api/v1/authorization/payments/evaluate` | Dry-run (and optional re-check) `CREATE` |
| `POST /api/v1/payments` | Create DRAFT (user JWT) |
| `POST /api/v1/authorization/payments/eligible-approvers` | Post-create approver list |

---

## Code map

| Module | Role |
|--------|------|
| `skills/detect.py` | Phrase + instruction id + amount + value date (`today` / `tomorrow` / ISO) |
| `skills/create_payment.py` | Phase 1 runner + confirm / Go path |
| `skills/pending_store.py` | In-process TTL pending skills |
| `skills/instruction_client.py` | Instruction GET (user / svc-chat OBO) |
| `skills/payment_client.py` | Payment CREATE |
| `skills/format.py` | Confirmation card + created report |
| `pipeline/orchestrator.py` | Skill short-circuit before me-intents / RAG |
| `static/app.js` | Activity list + Go / No Go card |

Tests: `ssi-chat/tests/test_create_payment_skill.py`.
