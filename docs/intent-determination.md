# Intent Determination in Policy Pilot

This document describes how **ssi-chat** decides what to do with a natural-language question before retrieval and answer synthesis. The design replaces brittle regex phrase lists with **LLM semantic routing**, then executes a **deterministic pipeline** (route → retrieve → synthesize).

## Summary

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| **Route** | Gemini Flash + structured `RouterDecision` JSON (**10** paths; **4** retrieval strategies) | Pick intent / backends from question meaning |
| **Path-owned handlers** | skill / me / policy tools / `neo4j_direct` / investigate — no steal | One handler per path |
| **Retrieve** | Selective backends (graph, vector, or both) on investigate only | Avoid merging unrelated search results |
| **Synthesize** | Deterministic formatters or Gemini | Produce the final answer from retrieved context |

We do **not** use fuzzy ML text classification for routing. Intent is expressed as a strict Pydantic schema returned by Gemini structured output.

## Thumb rule

**Natural-language intent → Gemini structured output / LLM semantic routing. Not regex phrase lists. Not fuzzy classification.**

People can express the same intent with many wordings. Regex and keyword heuristics do not scale for open-ended NLU. After the route decision, execution stays deterministic (OPA, skill steps, Neo4j, formatters).

| Allowed | Not for primary intent |
|---------|------------------------|
| Extending `RouterDecision` (path, skill, me_*, policy_*) + router prompt | Growing `re.compile(...)` lists to guess what the user meant |
| Regex / extractors for **slots** once intent is known (ids, amounts, dates, person name) | Fuzzy keyword scoring as the classifier |
| Heuristic router **only** when the LLM call fails (resilience) | New regex-first skill or me-intent detectors |

`RouterDecision.path` is the primary dispatch key (`skill`, `me`, `policy_summary`, `policy_directory`, `person_permissions`, `eligibility`, `neo4j_direct`, `graph`, `vector`, `hybrid`). **Path is law:** handlers do not silently override another path's execution (issue #8). After the LLM routes, **documented post-route clamps** may rewrite `path` before handlers — this is the approved exception to “path is LLM-only,” not ad-hoc handler force-lanes:

| Stack | Clamp helpers | Typical rewrites |
|-------|---------------|------------------|
| Python `ssi-chat` | `prefer_neo4j_direct_when_matched`, `prefer_vector_for_open_narrative` | YAML-matched shapes → `neo4j_direct`; open narrative → `vector` (never upgrades pure `vector` away) |
| Java `ssi-chat-j` | `routing.RouteClamps` | Past who-approved + id → `neo4j_direct`; open narrative → `vector` (also clamps `neo4j_direct` / `eligibility`, slightly broader than Python) |

See `.cursor/rules/intent-semantic-routing.mdc`, `.cursor/rules/ssi-chat-j-intent-routing.mdc`, and `ssi-chat-j/AGENTS.md`.

## End-to-end flow

The logged-in user's **JWT / ZITADEL session** is resolved to a subject. Live policy and eligibility answers go through **authorization-service → OPA**. The diagrams below split the chat surface by persona.

### Compliance and audit (read-only)

Compliance analysts investigate policy, eligibility, graph patterns, and event history. They do **not** run mutation skills.

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

### Front and middle office (payment operations)

Payment creators, desk submitters, and funding approvers use the same investigation path, and can also run **mutation skills** (create-payment, submit-payment, approve-payment) after OPA preflight and an explicit **Go / No Go**.

```mermaid
flowchart TD
    Q["Front / middle office question + Bearer JWT + search mode"] --> ID[Identity — ZITADEL subject]
    ID --> SK{mutation skill?}
    SK -->|create| PRE1[OPA CREATE preflight]
    SK -->|submit| PRE2[OPA SUBMIT preflight]
    SK -->|approve| PRE3[OPA APPROVE preflight]
    PRE1 -->|allow| CONF[Confirm card — Go / No Go]
    PRE2 -->|allow| CONF
    PRE3 -->|allow| CONF
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

Implementation entry point: `RagService.ask()` delegates to `RagPipelineOrchestrator` in `ssi-chat/src/chat_application/pipeline/orchestrator.py`. Skills: [create-payment](create-payment-skill.md), [submit-payment](submit-payment-skill.md), [approve-payment](approve-payment-skill.md), [cancel-payment](cancel-payment-skill.md).

## Step 1 — Semantic routing (LLM)

Every question is sent to **Gemini Flash** (`PolicyPilotMlClient.route_query`) with:

1. A fixed system prompt (`pipeline/prompts.py` → `ROUTER_SYSTEM_PROMPT`)
2. The user question (plus UI search mode) as the user turn
3. **Structured JSON output** constrained by `RouterDecision.model_json_schema()` (Vertex `response_schema`)

Pydantic validates the model reply before the orchestrator dispatches. There is **no free-form agent loop** — one route call, then deterministic handlers.

### How many paths and strategies?

| Layer | Count | Values |
|-------|------:|--------|
| **Intent paths** (`RouterDecision.path`) | **9** | `skill`, `me`, `policy_summary`, `policy_directory`, `person_permissions`, `eligibility`, `graph`, `vector`, `hybrid` |
| **Retrieval strategies** (`RouterDecision.strategy` / selective retrieve) | **4** | `eligibility`, `graph`, `vector`, `hybrid` |
| **Post-hoc observability** (`AnswerRoutingInfo.retrieval_strategy`) | **6** | `eligibility`, `policy_directory`, `deterministic`, `graph`, `vector`, `skill` |

The four retrieval strategies drive backends in step 3. Tool-style paths (`skill`, `me`, `policy_*`, …) do not use `strategy` for backend selection. Observability may later label an answer `deterministic` (Neo4j direct YAML) or `policy_directory` / `skill` after execution.

```python
class RouterDecision(BaseModel):
    path: Literal[
        "skill", "me", "policy_summary", "policy_directory",
        "person_permissions", "eligibility", "graph", "vector", "hybrid"
    ] | None
    strategy: Literal["eligibility", "graph", "vector", "hybrid"] | None
    eligibility_target: Literal["payment", "instruction"] | None
    skill: Literal["create_payment", "submit_payment", "approve_payment"] | None
    me_kind / me_action / me_entity_type: ...
    policy_domain / policy_action: ...
    person_query: str | None
    reasoning: str
```

| Field | Meaning |
|-------|---------|
| `path` | Primary intent dispatch (skill / me / policy tools / retrieval) |
| `strategy` | Retrieval backends when path is eligibility/graph/vector/hybrid |
| `eligibility_target` | For eligibility: payment vs instruction |
| `skill` / `me_*` / `policy_*` / `person_query` | Fields for dedicated handlers |
| `reasoning` | Short audit trail for logs and debugging |

**Conceptual tools** the router maps to (not a free-form agent loop — one decision, then deterministic execution):

| Tool | Path | Example questions |
|------|------|-------------------|
| **CreatePaymentSkill** | `skill` | Can you create a payment for instruction X…? |
| **SubmitPaymentSkill** | `skill` | Please submit payment Y for approval. |
| **ApprovePaymentSkill** | `skill` | Please approve payment Y. |
| **MeIntent** | `me` | Who am I? Can I create a payment? |
| **PolicySummary** | `policy_summary` | What is the funding approval policy? |
| **PolicyDirectory** | `policy_directory` | Who can approve payments over $25B? |
| **PersonPermissions** | `person_permissions` | Permissions of Kowalski, Anna |
| **CheckEligibilityAPI** | `eligibility` | Who can approve payment `20260705-FX-P-534`? |
| **SearchGraph** | `graph` | How many alerts today? Who approved instruction X? |
| **SearchPolicyDocuments** | `vector` | Why was this payment denied? |
| **Hybrid** | `hybrid` | Needs structured facts **and** semantic policy text |

### Example Gemini Flash → `RouterDecision` JSON

Illustrative structured replies (field set matches `RouterDecision`; `null` omitted fields are allowed and normalized in the model validator):

**Eligibility (live OPA — who can approve this payment):**

```json
{
  "path": "eligibility",
  "strategy": "eligibility",
  "eligibility_target": "payment",
  "reasoning": "Forward-looking who-can for a specific payment id"
}
```

**Graph (structured Neo4j audit — who already approved):**

```json
{
  "path": "graph",
  "strategy": "graph",
  "reasoning": "Past-tense approval lookup; answer from the knowledge graph"
}
```

**Vector (semantic why / policy prose):**

```json
{
  "path": "vector",
  "strategy": "vector",
  "reasoning": "Open-ended why-denied; needs semantic retrieval over audit text"
}
```

**Hybrid (structured facts + semantic context):**

```json
{
  "path": "hybrid",
  "strategy": "hybrid",
  "reasoning": "Needs both graph facts and policy narrative"
}
```

**Policy directory (amount club / LOB funding-approver list — no payment id):**

```json
{
  "path": "policy_directory",
  "reasoning": "Who may approve by amount threshold; directory lookup, not live payment eligibility"
}
```

**Policy summary (normative OPA catalog):**

```json
{
  "path": "policy_summary",
  "policy_domain": "payment",
  "policy_action": "APPROVE",
  "reasoning": "User asked what the funding approval policy is"
}
```

**Me intent (logged-in user capabilities):**

```json
{
  "path": "me",
  "me_kind": "can_act_on_entity",
  "me_action": "CREATE",
  "me_entity_type": "payment",
  "reasoning": "Can I create a payment — self capability, not mutation skill"
}
```

**Create-payment skill (mutation):**
```json
{
  "path": "skill",
  "skill": "create_payment",
  "reasoning": "User wants to create a draft payment from an instruction"
}
```

**Submit-payment skill (mutation):**
```json
{
  "path": "skill",
  "skill": "submit_payment",
  "reasoning": "User wants to submit an existing draft payment for funding approval"
}
```

**Approve-payment skill (mutation):**
```json
{
  "path": "skill",
  "skill": "approve_payment",
  "reasoning": "User wants to funding-approve an existing submitted payment"
}
```

**Person permissions:**

```json
{
  "path": "person_permissions",
  "person_query": "Kowalski, Anna",
  "reasoning": "Permissions of a named person, not the logged-in user"
}
```

### Eligibility vs audit (critical distinction)

The router must separate **forward-looking** from **past-tense** approval language:

| Intent | Wording | Strategy |
|--------|---------|----------|
| **Eligibility** (who *can*) | approve, authorize, green-light, sign off, release, eligible, allowed | `eligibility` → OPA API |
| **Audit** (who *did*) | who approved, when was it approved, who signed off yesterday | `graph` → Neo4j |

Synonyms like *green-light*, *sign off*, and *authorize* are handled by the LLM router semantically — they are **not** maintained as a growing regex phrase list.

### Heuristic fallback

If the LLM router fails (network, schema error, etc.), `route_question()` falls back to `heuristic_router_decision()` in `pipeline/heuristic_strategy.py`. This uses structural detectors from `cypher_builder` (counts, aggregates, rankings) plus a minimal eligibility pattern. Fallback is for **resilience**, not primary routing.

### Resolving payment vs instruction

For eligibility, target resolution order:

1. LLM `eligibility_target` when present
2. Sequence ID heuristics: `-P-` → payment, `-I-` → instruction
3. Keywords (`payment`, `instruction`, `ssi`) and UI search mode

## Step 2 — Neo4j direct fast path (unchanged)

Before full RAG, **YAML-defined direct intents** in `neo4j_direct.yaml` still match high-confidence patterns and return formatted answers with zero vector search. This path is preserved for latency, cost, and regression stability.

Observability path: `neo4j_direct` → `retrieval_strategy: deterministic`.

## Step 3 — Selective retrieval (no blind merge)

`execute_selective_retrieval()` runs only the backends the router chose — one of the **four** retrieval strategies:

| Strategy | Neo4j / exact lookup | Dense vector |
|----------|----------------------|--------------|
| `graph` | Yes | No |
| `vector` | No | Yes |
| `hybrid` | Yes | Yes (RRF with graph) |
| `eligibility` | N/A (handled via live OPA fast path, not this merge) | N/A |

Graph retrieval still uses the existing stack: planned Cypher from `cypher_builder`, LLM `GraphQueryPlan` extraction when needed, and exact UUID/sequence ID lookups.

## Step 4 — Synthesize

After retrieval, the orchestrator applies the same synthesis rules as before:

- **Deterministic formatters** for counts, rankings, payment lists, alert tables, etc.
- **Gemini WHY-only** rewrite for approval audit questions
- **Full Gemini synthesis** when no formatter applies

## What we deliberately did *not* do

| Anti-pattern | Our approach |
|--------------|--------------|
| Regex / fuzzy phrase list as primary NLU | LLM structured output (`RouterDecision` / skill schemas) |
| Unconstrained multi-step agent on every turn | Single route call → deterministic execution |
| Always parallel RRF merge | Strategy-driven selective retrieval |
| Replace Neo4j direct YAML intents | Keep them as a fast path for high-confidence id/pattern lookups |

**Thumb rule:** open-ended intent is semantic (Gemini). Regex remains appropriate for **slot parsers** (IDs, amounts, dates) and **LLM-failure fallback**, not for guessing which skill or me-intent the user meant.

## Observability

Each answer records routing metadata (`AnswerRoutingInfo`):

| Field | Values |
|-------|--------|
| `path` | `eligibility`, `policy_directory`, `neo4j_direct`, `full_rag`, `skill` |
| `retrieval_strategy` | `eligibility`, `policy_directory`, `deterministic`, `graph`, `vector`, `skill` (derived post-hoc) |
| `cypher_provenance` | `predefined_yaml`, `predefined_planned`, `llm_graph_plan`, `none` |
| `answer_synthesis` | `eligibility_api`, `policy_directory_api`, `formatter`, `gemini_why_only`, `gemini_full` |

Structured log line: `chat.answer.completed strategy=… path=… cypher=… synthesis=…`

## Code map

| File | Role |
|------|------|
| `ssi-chat/src/chat_application/pipeline/orchestrator.py` | Route → retrieve → synthesize orchestration |
| `ssi-chat/src/chat_application/pipeline/route.py` | LLM route + heuristic fallback |
| `ssi-chat/src/chat_application/pipeline/models.py` | `RouterDecision` schema |
| `ssi-chat/src/chat_application/pipeline/prompts.py` | Router system prompt |
| `ssi-chat/src/chat_application/pipeline/heuristic_strategy.py` | Fallback routing heuristics |
| `ssi-chat/src/chat_application/pipeline/retrieve.py` | Selective retrieval execution |
| `ssi-chat/src/chat_application/gemini/client.py` | `route_query()` — Gemini structured output |
| `shared/vertex_client/src/vertex_client/generation.py` | `response_schema` support for Gemini |
| `ssi-chat/src/chat_application/graph/direct.py` | Direct Neo4j intent matching |
| `shared/cypher_builder/` | Graph plan extraction and planned Cypher |

## Reviewer talking points

1. **Deterministic intent routing** uses Gemini with a strict Pydantic `RouterDecision` schema — not fuzzy text classification.
2. **Structured financial queries** (counts, totals, lists) go to Neo4j only; vector search does not run unless the router chooses `vector` or `hybrid`.
3. **Eligibility questions** call live OPA through the authorization service; synonyms like *green-light* are understood by the LLM router.
4. **Audit questions** (*who approved*) route to graph retrieval, not eligibility.
5. The pipeline is **testable**: unit tests mock `route_query`; regression cases assert `retrieval_strategy` and answer quality.

## Related documentation

- `ssi-chat/README.md` — chat API, routing observability, feedback metrics
- Regression bank: `ssi-chat/regression/questions.yaml` — cases tagged with expected `retrieval` strategy
