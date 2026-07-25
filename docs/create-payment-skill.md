# Create-payment skill

Policy Pilot’s first **mutation skill**: a scripted multi-step flow that creates a draft payment from natural language, only after an OPA preflight and an explicit **Go / No Go** confirmation.

Skills are **not** free-form LLM tool loops. Steps are fixed; authorization always goes through **authorization-service → OPA**, the same path payment-service uses for `CREATE`.

Related: **[Submit-payment skill](submit-payment-skill.md)** (desk submits the DRAFT for funding approval).

| | |
|--|--|
| **Package** | [`ssi-chat-j/.../skill/`](../ssi-chat-j/src/main/java/com/sanjuthomas/policypilot/skill/) (`CreatePaymentSkill`, `SkillSlots`) |
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

## How intent is identified

**Thumb rule** ([intent determination](intent-determination.md)): natural-language intent uses Gemini structured output (`RouterDecision.path`). Create-payment is selected when `path=skill` and `skill=create_payment`.

| Step | Mechanism |
|------|-----------|
| Intent | Spring AI `RouterDecision` → `path=skill`, `skill=create_payment` |
| Slots | LLM `skillInstructionId` / `skillAmount` / `skillValueDate` (`SkillSlots`; id has stable-token fallback) |
| Execution | Scripted preflight → Go / No Go → payment-service CREATE |
| Evidence | Chat writes `audit_executions`; payment-service links the OPA security event |

Capability questions like “Can I create a payment?” should route to `path=me`, not this mutation skill.

Auditors inspect the resulting evidence on the
[Technology Auditor Console](../audit-service/README.md) (`http://localhost:8097`),
not in chat or payment-service UI.


---

## Sequence (happy path)

```mermaid
sequenceDiagram
    actor U as User (browser)
    participant UI as Policy Pilot UI
    participant C as ssi-chat-j
    participant L as Gemini (router)
    participant I as instruction-service
    participant A as authorization-service / OPA
    participant P as payment-service
    participant M as MongoDB
    participant AC as audit-service :8097

    U->>UI: Create payment (instruction, amount, value date)
    UI->>C: POST /api/chat (Bearer JWT)

    C->>L: Spring AI → RouterDecision
    L-->>C: path=skill, skill=create_payment + slots
    Note over C: SkillSlots (LLM amount/date; id slot or token fallback)

    Note over C: Phase 1 — preflight (no mutate)
    C-->>UI: activity: Parsed request…
    C->>I: GET /api/v1/instructions/{id}
    I-->>C: parties, LOB, status, currency
    C-->>UI: activity: Loaded instruction…
    C-->>UI: activity: Checking CREATE for LOB…
    C->>A: POST …/payments/evaluate action=CREATE<br/>(svc-chat + X-On-Behalf-Of user)
    A-->>C: allowed + allow_basis / violations

    alt Denied
        C->>P: POST /api/v1/audit-executions<br/>status=DENIED + policy_exchange
        P->>M: Insert audit_executions
        C-->>UI: Stop — violations (no payment created)
    else Allowed
        C->>P: POST /api/v1/audit-executions<br/>status=AWAITING_CONFIRMATION + policy_exchange
        P->>M: Insert audit_executions
        C-->>UI: activity: Yes — may create…
        C-->>UI: Confirmation card + pending_id<br/>(debtor / creditor / intermediaries)
        Note over C: Pending skill stored (TTL)
        U->>UI: Go
        UI->>C: POST /api/chat/skills/create-payment/confirm<br/>{ pending_id, decision: "go" }

        Note over C: Phase 2 — mutate
        C->>A: Re-check CREATE (optional)
        C->>P: POST /api/v1/payments<br/>+ X-Audit-Execution-Id
        P->>A: CREATE evaluate (domain path)
        P->>M: Insert payment + security event<br/>(one transaction)
        P->>M: Link audit → security_event_id<br/>unset policy_exchange → COMPLETED
        P-->>C: PaymentResponse (DRAFT)
        C->>P: PATCH audit-executions (result)
        C->>A: eligible-submitters (svc-chat + user OBO)
        C-->>UI: Created report + who can submit
        Note over AC: TECH_AUDITORS view /audit/{id}<br/>and linked OPA via /opa
    end

    opt No Go
        U->>UI: No Go
        UI->>C: confirm { decision: "no_go" }
        C->>P: PATCH audit-executions (cancelled)
        C-->>UI: Cancelled — no payment created
    end
```

---

## Activity steps (what the user sees)

| Step | Activity / UI | Side effect |
|------|---------------|-------------|
| 0. Route | (none for skill) | Gemini `path=skill` |
| 1. Parse slots | Parsed instruction, amount, value date | Deterministic parsers |
| 2. Load instruction | Loading / loaded LOB, status, currency | None |
| 3. Preflight CREATE | Checking roles, groups, covering LOBs, amount club… | Authz evaluate only |
| 4. Explain | **Yes** + humanized allow basis, or **No** + stop | Create `audit_executions` with provisional `governance.policy_exchange` |
| 5. Confirm | Card: instruction, amount, value date, LOB, debtor/creditor names & accounts, intermediaries · **Go** / **No Go** | Pending skill id |
| 6. Create (Go only) | Creating draft… | `POST /api/v1/payments` + `X-Audit-Execution-Id` → Mongo |
| 7. Submitters | Looking up who can submit… | Authz eligible-submitters |
| 8. Report | Payment id, instruction, amount, LOB, eligible desk submitters | Audit linked to payment security event |

---

## Design rules

| Rule | Meaning |
|------|---------|
| **Scripted pipeline** | Regex detector + fixed steps — not an agent inventing APIs; Gemini router is not the skill classifier |
| **OPA stays normative** | Preflight and create both use payment `CREATE` policy |
| **Explain before confirm** | Stream permission reasoning before any Go button |
| **Confirm before mutate** | No Mongo write until **Go** |
| **Fail closed** | Deny, No Go, expired pending, wrong user, or authz re-check unavailable → no create |
| **Act as logged-in user** | User JWT on instruction GET and payment CREATE; `svc-chat` OBO for evaluate |

Chat does **not** write Mongo domain collections directly. On **Go**, payment-service allocates the id, re-evaluates OPA, and inserts the payment version + security event in one transaction (`ssi_cash_activities.payments` + `security_events.payment_service`). Kafka CDC / indexer then update Neo4j as for any other create.

### Governed activity evidence (not a second OPA copy)

Create Payment also persists a governed **audit execution** so technology auditors can reconstruct AI/capability context without duplicating OPA:

| Stage | Audit status / outcome | Where OPA lives |
|-------|------------------------|-----------------|
| Phase 1 deny | Terminal `DENIED` / `deny` | Provisional `governance.policy_exchange` on the audit doc |
| Phase 1 allow | `AWAITING_CONFIRMATION` / `allow` | Same provisional `policy_exchange` |
| Phase 2 No Go / cancel | Terminal cancelled statuses | Still policy_exchange (no security event) |
| Phase 2 Go create | Linked `COMPLETED` / `allow` | Authoritative OPA on the payment security event; `policy_exchange` unset |

Writers are **ssi-chat-j → payment-service** (`POST`/`PATCH /api/v1/audit-executions`, mutation header `X-Audit-Execution-Id`). The same pattern applies to submit / approve / cancel via `PaymentIdSkillFlow`. Readers are **audit-service** (`TECH_AUDITORS`) via `/audit/{execution_id}` and `/api/audit-executions/{id}/opa`. See [payment-service/README.md](../payment-service/README.md#governed-payment-skill-audit-executions) and [audit-service/README.md](../audit-service/README.md).

---

## APIs

| Call | When |
|------|------|
| `POST /api/chat` | Phase 1 — detect skill, return activities + `skill_confirmation` |
| `POST /api/chat/skills/create-payment/confirm` | Phase 2 — `{ "pending_id", "decision": "go" \| "no_go" }` |
| `GET /api/v1/instructions/{id}` | Load SSI parties for the card |
| `POST /api/v1/authorization/payments/evaluate` | Dry-run (and optional re-check) `CREATE` |
| `POST /api/v1/audit-executions` | Persist governed activity evidence (preflight allow/deny) |
| `PATCH /api/v1/audit-executions/{id}` | Confirm, cancel, fail, or attach result |
| `POST /api/v1/payments` | Create DRAFT (`X-Audit-Execution-Id` links evidence) |
| `POST /api/v1/authorization/payments/eligible-submitters` | Post-create desk submitter list |

---

## Code map

| Module | Role |
|--------|------|
| `pipeline/RouterDecision.java` | LLM slots (`skillInstructionId`, `skillAmount`, `skillValueDate`) |
| `skill/SkillSlots.java` | Resolve create params (amount/date from LLM only) |
| `skill/CreatePaymentSkill.java` | Phase 1 runner + confirm / Go path + audit create/patch |
| `skill/AuditExecutionClient.java` | payment-service audit write client |
| `skill/PaymentMutationClient.java` | CREATE with `X-Audit-Execution-Id` |
| `skill/PendingSkillStore.java` | In-process TTL pending skills |
| `skill/SkillFormat.java` | Confirmation card + created report |
| `static/app.js` | Activity list + Go / No Go card |

Tests: `ssi-chat-j/src/test/java/.../skill/CreatePaymentSkillTest.java` (and related skill tests).
