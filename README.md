# Policy Pilot

An event-driven, policy-aware knowledge platform for regulated financial systems — OPA authorization, Neo4j knowledge graphs, graph and vector retrieval, and LLM-powered investigation in one conversational surface.

Policy Pilot gives supervisors, compliance officers, and **payment operations** users a single place to ask questions over the cash leg of Standard Settlement Instructions (SSI). It unifies **live policy rules** (OPA), **operational state** (instructions and payments), and the **immutable audit trail** of what was allowed or denied — so teams investigate in natural language instead of stitching answers from LDAP, databases, and ticket queues.

## Why this exists

In a large bank, answering even simple supervision questions is painfully slow:

- *Are there users approving each other's instructions?*
- *Did a subordinate approve their manager's instruction?*
- *Who can approve this payment when two approvers are out sick?*
- *Why was someone allowed to approve across line-of-business boundaries?*

The answers rarely live in one place. Rules sit in **LDAP**, **OPA**, **application code**, and **database config** that only one team understands. Worse, **what policy says** and **what actually happened** can diverge — investigators need both the **policy decision** (allow/deny and why) and the **operational fact**, captured together at decision time.

Policy Pilot models that end to end. Every mutation is recorded, streamed through Kafka, indexed into Neo4j (graph + dense vector store), and made queryable in conversation — a **holistic, evidence-backed view** grounded in what the system actually did.

## What you can ask

Policy Pilot surfaces **fraud patterns, compliance violations, and collusion signals** — not just application status screens.

**Demo tags** (see [intent determination](docs/intent-determination.md)): **`graph`** · **`tools`** · **`vector`** · **`skill`**

**Graph**

- _Are there any instances of approving each other's instructions?_ **`graph`**
- _Are there cases where one user created an instruction that another user approved, and that approver later created a payment on the same instruction that the original creator then approved?_ **`graph`**
- _Who approved instruction X, and why was it allowed?_ **`graph`** **`vector`**
- _Can you show me the payment 20260712-FICC-P-2?_ **`graph`**

**Tools** (live policy — use **Policies** mode; log in as `comp-001`)

- _What is the funding approval policy?_ **`tools`**
- _Who has permission to approve payments worth more than $25 billion, and for which lines of business?_ **`tools`** **`policy_directory`**
- _Who has permission to approve payments belong to LOB FICC?_ **`tools`** **`policy_directory`**
- _Can you list the permissions of Kowalski, Anna?_ **`tools`**
- _Who can approve payment Y?_ **`tools`** **`eligibility`**

**Skills** (mutation — use **Payments** mode; log in as a payment creator, e.g. `pay-101` / `pay-205`)

- _Can you create a payment for instruction ID 20260705-FICC-I-31? Value date tomorrow; amount: 12 million USD._ **`skill`**

  Scripted **create-payment** skill: parse request → load instruction → dry-run OPA `CREATE` → confirmation card (debtor / creditor / intermediaries) with **Go / No Go** → create draft only on **Go**. Fail closed on deny or No Go. Full write-up: **[Create-payment skill](docs/create-payment-skill.md)**.

**Vector** (use **Events** mode)

- _Show payment policy denial ALERT events today with actor and reason._ **`vector`**
- _Show ALERT events for LOB coverage violations on payments._ **`vector`**

**Full list:** **[Sample questions](docs/sample-questions.md)**. Demo personas: **[Domain models and demo users](docs/domain-models.md)**. Regression bank: **[ssi-chat/regression/questions.yaml](ssi-chat/regression/questions.yaml)**.

---

## How it works

![End-to-end architecture](docs/architecture-2.png)

Policy Pilot sits at the end of an event-driven pipeline: domain services enforce OPA policy and write versioned state + security events to MongoDB; Kafka Connect streams changes; **ssi-indexer** builds a shared Neo4j graph and dense vector index; **ssi-chat** routes each question through a **Route → Retrieve → Synthesize** pipeline. Live policy and eligibility answers go through the same **authorization-service → OPA** path as mutations, using the logged-in user's JWT / ZITADEL session — not a parallel unchecked tool layer.

| Topic | Summary |
|-------|---------|
| **[Create-payment skill](docs/create-payment-skill.md)** | First mutation skill: OPA preflight, Go / No Go confirmation, payment-service CREATE → Mongo. |
| **[OPA policy controls](docs/opa-controls.md)** | Segregation of duties, reporting-line inversion of control, LOB boundaries, amount clubs — the checks and balances enforced on every action. |
| **[Sample questions](docs/sample-questions.md)** | Curated demo questions by retrieval path (`graph`, `tools`, `skill`, `vector`), including Policies-mode and create-payment skill examples. |
| **[Intent determination](docs/intent-determination.md)** | Gemini returns a strict `RouterDecision` (eligibility, graph, vector, or hybrid). Selective retrieval — no blind merge of graph and vector on every question. |
| **[Data flow](docs/data-flow.md)** | Mongo transactions → Kafka CDC → four ETL pipelines → Neo4j graph + vector store → chat. |
| **[Architecture decisions](docs/architecture-decisions.md)** | Why ZITADEL, OPA, MongoDB, Kafka, Neo4j graph and vector search, Vertex AI, and `cypher_builder`. |
| **[Authorization audit trail](docs/authorization-audit-trail.md)** | Who / When / Why on past approvals; live *who can approve?* via eligible-approvers APIs. |
| **[Local development](docs/local-development.md)** | Run services locally, observability, regression evaluation, component map. |

---

## Intent Determination

Policy Pilot's chat layer (**ssi-chat**) decides what to do with a natural-language question before retrieval and answer synthesis. The design replaces brittle regex phrase lists with **LLM semantic routing**, then executes a **deterministic pipeline** (route → retrieve → synthesize).

### Summary

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| **Route** | Gemini Flash + structured `RouterDecision` JSON | Pick retrieval strategy from question intent |
| **Skills** | Scripted multi-step actions (e.g. create-payment) | Mutate only after OPA preflight + explicit Go / No Go |
| **Fast paths** | Neo4j direct YAML intents, live OPA eligibility API, me-intents | Skip full RAG when a specialized handler applies |
| **Retrieve** | Selective backends (graph, vector, or both) | Avoid merging unrelated search results |
| **Synthesize** | Deterministic formatters or Gemini | Produce the final answer from retrieved context |

We do **not** use fuzzy ML text classification for routing. Intent is expressed as a strict Pydantic schema returned by Gemini structured output. **Skills** are not free-form agent tool loops — they are fixed pipelines that reuse the same authorization-service → OPA path as domain mutations.

### End-to-end flow

The logged-in user's **JWT / ZITADEL session** is resolved to a subject. Live policy and eligibility answers still go through **authorization-service → OPA** — the same engine that guards domain mutations. What the chat pipeline offers next depends on the persona.

#### Compliance and audit (read-only)

Compliance analysts (`comp-001` / `comp-002`) investigate policy, eligibility, graph patterns, and event history. They do **not** run mutation skills.

```mermaid
flowchart TD
    Q["Compliance / audit question + Bearer JWT + search mode"] --> ID[Identity — ZITADEL subject]
    ID --> R[1. Route — LLM RouterDecision]
    R --> E{live policy / eligibility / tools?}
    E -->|yes| AZ[2. Authorization-service]
    AZ --> OPA[OPA policy evaluation]
    OPA --> A[Answer]
    E -->|no| D[3. Neo4j direct fast path]
    D -->|match| A
    D -->|no match| RET[4. Selective retrieval]
    RET --> G{strategy}
    G -->|graph| N[Neo4j + exact ID lookup]
    G -->|vector| V[Dense embeddings]
    G -->|hybrid| H[Neo4j + vector]
    N --> S[5. Synthesize]
    V --> S
    H --> S
    S --> A
```

#### Front and middle office (payment operations)

Payment creators and funding approvers (`pay-*`, `mo-*`) use the same route → retrieve → synthesize path for questions, and can also run **mutation skills** (create-payment today) after OPA preflight and an explicit **Go / No Go**.

```mermaid
flowchart TD
    Q["Front / middle office question + Bearer JWT + search mode"] --> ID[Identity — ZITADEL subject]
    ID --> SK{create-payment skill?}
    SK -->|yes| PRE[OPA CREATE preflight]
    PRE -->|allow| CONF[Confirm card — Go / No Go]
    CONF -->|Go| PAY[POST payment-service]
    PAY --> A[Answer]
    CONF -->|No Go / deny| A
    SK -->|no| R[1. Route — LLM RouterDecision]
    R --> E{live policy / eligibility / tools?}
    E -->|yes| AZ[2. Authorization-service]
    AZ --> OPA[OPA policy evaluation]
    OPA --> A
    E -->|no| D[3. Neo4j direct fast path]
    D -->|match| A
    D -->|no match| RET[4. Selective retrieval]
    RET --> G{strategy}
    G -->|graph| N[Neo4j + exact ID lookup]
    G -->|vector| V[Dense embeddings]
    G -->|hybrid| H[Neo4j + vector]
    N --> S[5. Synthesize]
    V --> S
    H --> S
    S --> A
```

Implementation entry point: `RagService.ask()` delegates to `RagPipelineOrchestrator` in `ssi-chat/src/chat_application/pipeline/orchestrator.py`. Create-payment skill: **[docs/create-payment-skill.md](docs/create-payment-skill.md)** (`ssi-chat/src/chat_application/skills/`). Full routing specification: **[docs/intent-determination.md](docs/intent-determination.md)**.

---

## Neo4j graph model

Four ETL pipelines write to the **same Neo4j database**, sharing nodes (`Instruction`, `InstructionVersion`, `User`, `ProfitCenter`, `Payment`, `PaymentVersion`, `SecurityEvent`). Writers split into two symmetric roles:

| Writer type | Pipelines | Owns |
|-------------|-----------|------|
| **Fact** (state) | `InstructionPipeline`, `PaymentFactPipeline` | Versions, `CURRENT`, `SUPERSEDES`, lifecycle edges (`_*IV` / `_*PV`), structural edges, root denorm, vector state docs |
| **Audit** (events) | `InstructionSecurityEventPipeline`, `PaymentSecurityEventPipeline` | `SecurityEvent`, `ACTED_AS`, `FOR` → version, `INVOLVES_LOB`, vector event docs |

Security-event pipelines write audit edges only — they do not write lifecycle edges, `CURRENT`, or `CONSUMED`. Each audit row links to the version that was current at event time via **`FOR`**.

Full specification, diagrams, example queries, and reload procedure: **[neo4j-graph-model/README.md](neo4j-graph-model/README.md)**.

---

## Quick start

**Prerequisites:** Docker + Docker Compose; GCP project with Vertex AI enabled and a service account key — **[GCP setup](docs/gcp-setup.md)**.

```bash
cp .env.example .env
# Set GCP_SA_KEY_PATH and GOOGLE_APPLICATION_CREDENTIALS

python scripts/vertex_smoke_test.py   # optional but recommended

docker compose up -d

# Seed demo users (~30 s after ZITADEL starts)
PAT=$(docker exec zitadel-login cat /zitadel/bootstrap/login-client.pat | tr -d '\n')
cd zitadel-seed && ZITADEL_PAT="$PAT" python3 seed.py

open http://localhost:8091   # harness — run policy scenarios
open http://localhost:8092   # Policy Pilot — start asking questions
```

**Full demo seed** (instructions, payments, dozens of policy-denial ALERTs):

```bash
./ssi-demo-harness/seed-demo-data.sh          # reset volumes + seed
./ssi-demo-harness/seed-demo-data.sh --seed-only   # stack already up
```

Allow **ssi-indexer** to catch up after seeding before ALERT counts in chat look correct. See [ssi-demo-harness/README.md](ssi-demo-harness/README.md).

| URL | What |
|-----|------|
| http://localhost:8092 | Policy Pilot |
| http://localhost:8091 | Demo harness |
| http://localhost:8090 | Indexer search console |
| http://localhost:8000 | Instruction service |
| http://localhost:8093 | Payment service |
| http://localhost:8094 | Authorization service |
| http://localhost:8095 | Sequence service |
| http://localhost:7474/browser/ | Neo4j (`neo4j` / `devpassword`) |

**Reset:** `docker compose down -v --remove-orphans && docker compose up -d` — then re-seed ZITADEL users and run the harness seed script.

**Neo4j graph only** (keep Mongo/Kafka data, replay ETL): see [ssi-indexer/README.md](ssi-indexer/README.md#reset-consumer-offsets) and [neo4j-graph-model/README.md](neo4j-graph-model/README.md#wipe-and-reload-demo-graph).

Demo logins (password `Password1!`): see **[Domain models and demo users](docs/domain-models.md)**.

---

## Documentation

| Document | Contents |
|----------|----------|
| [docs/opa-controls.md](docs/opa-controls.md) | OPA checks and balances — four-eyes, reporting lines, LOB scope, amount clubs |
| [docs/intent-determination.md](docs/intent-determination.md) | Route → Retrieve → Synthesize pipeline, `RouterDecision`, observability |
| [docs/data-flow.md](docs/data-flow.md) | End-to-end pipeline, transactions, storage and Kafka topics |
| [docs/architecture-decisions.md](docs/architecture-decisions.md) | ZITADEL, OPA, MongoDB, Kafka, Neo4j, Vertex, models |
| [docs/authorization-audit-trail.md](docs/authorization-audit-trail.md) | Who / When / Why, live eligibility |
| [docs/domain-models.md](docs/domain-models.md) | Instruction and payment models, demo users |
| [docs/gcp-setup.md](docs/gcp-setup.md) | Vertex AI credentials and smoke test |
| [docs/local-development.md](docs/local-development.md) | Local services, logs, regression suite, URLs |

Each application directory also has its own README — see table below.

---

## Repository layout

```
.
├── docker-compose.yml
├── docs/                            # Architecture and operations guides
├── instruction-service/             # Instruction lifecycle API + UIs
├── payment-service/                 # Payment lifecycle API + UIs
├── authorization-service/           # OPA gateway + user directory UI
├── sequence-service/                # Monotonic id allocation
├── shared/
│   ├── authz_client/                # Domain → authorization-service HTTP client
│   ├── cypher_builder/              # Neo4j planned query engine
│   ├── sequence_client/             # Domain → sequence-service HTTP client
│   ├── vertex_client/               # Vertex AI embeddings + Gemini
│   └── telemetry/                   # OpenTelemetry helpers
├── kafka-connect/                   # Mongo CDC → Kafka
├── ssi-indexer/                     # Kafka → Neo4j graph + vector index
├── ssi-chat/                        # Policy Pilot
├── ssi-demo-harness/                # Scenario harness + seed-demo-data.sh
├── neo4j-graph-model/               # Graph schema (README.md)
├── opa-policy-seed/                 # Rego policies
└── zitadel-seed/                    # Demo user definitions
```

| Directory | README | Port |
|-----------|--------|------|
| `instruction-service` | [README](instruction-service/README.md) | 8000 |
| `payment-service` | [README](payment-service/README.md) | 8093 |
| `authorization-service` | [README](authorization-service/README.md) | 8094 |
| `sequence-service` | [README](sequence-service/README.md) | 8095 |
| `ssi-indexer` | [README](ssi-indexer/README.md) | 8090 |
| `ssi-chat` | [README](ssi-chat/README.md) | 8092 |
| `ssi-demo-harness` | [README](ssi-demo-harness/README.md) | 8091 |
| `neo4j-graph-model` | [README](neo4j-graph-model/README.md) | — |
| `kafka-connect` | [README](kafka-connect/README.md) | 8083 |
| `opa-policy-seed` | [README](opa-policy-seed/README.md) | — |
| `zitadel-seed` | [README](zitadel-seed/README.md) | — |
| `shared/cypher_builder` | [README](shared/cypher_builder/README.md) | — |
| `shared/authz_client` | [README](shared/authz_client/README.md) | — |
