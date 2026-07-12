# Intent Determination in Policy Pilot

This document describes how **ssi-chat** decides what to do with a natural-language question before retrieval and answer synthesis. The design replaces brittle regex phrase lists with **LLM semantic routing**, then executes a **deterministic pipeline** (route → retrieve → synthesize).

## Summary

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| **Route** | Gemini Flash + structured `RouterDecision` JSON | Pick retrieval strategy from question intent |
| **Fast paths** | Neo4j direct YAML intents, live OPA eligibility API | Skip full RAG when a specialized handler applies |
| **Retrieve** | Selective backends (graph, vector, or both) | Avoid merging unrelated search results |
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

`RouterDecision.path` is the primary dispatch key (`skill`, `me`, `policy_summary`, `policy_directory`, `person_permissions`, `eligibility`, `graph`, `vector`, `hybrid`). See `.cursor/rules/intent-semantic-routing.mdc`.

## End-to-end flow

Live policy questions carry the logged-in user's **JWT / ZITADEL session** into **authorization-service**, which evaluates against **OPA** — the same policy path domain services use for mutations.

```mermaid
flowchart TD
    Q["User question + Bearer JWT + search mode"] --> ID[Identity — ZITADEL subject]
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
    G -->|vector| V[Embeddings + BM25]
    G -->|hybrid| H[Neo4j + vector/BM25]
    N --> S[5. Synthesize]
    V --> S
    H --> S
    S --> A
```

Implementation entry point: `RagService.ask()` delegates to `RagPipelineOrchestrator` in `ssi-chat/src/chat_application/pipeline/orchestrator.py`.

## Step 1 — Semantic routing (LLM)

Every question is sent to **Gemini Flash** with a fixed system prompt and **structured JSON output** validated against `RouterDecision`:

```python
class RouterDecision(BaseModel):
    path: Literal[
        "skill", "me", "policy_summary", "policy_directory",
        "person_permissions", "eligibility", "graph", "vector", "hybrid"
    ] | None
    strategy: Literal["eligibility", "graph", "vector", "hybrid"] | None
    eligibility_target: Literal["payment", "instruction"] | None
    skill: Literal["create_payment"] | None
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
| **MeIntent** | `me` | Who am I? Can I create a payment? |
| **PolicySummary** | `policy_summary` | What is the funding approval policy? |
| **PolicyDirectory** | `policy_directory` | Who can approve payments over $25B? |
| **PersonPermissions** | `person_permissions` | Permissions of Kowalski, Anna |
| **CheckEligibilityAPI** | `eligibility` | Who can approve payment `20260705-FX-P-534`? |
| **SearchGraph** | `graph` | How many alerts today? Who approved instruction X? |
| **SearchPolicyDocuments** | `vector` | Why was this payment denied? |
| **Hybrid** | `hybrid` | Needs structured facts **and** semantic policy text |

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

Previously, the fallback path always ran **vector + BM25 + graph in parallel** and merged everything with RRF. That polluted structured answers with fuzzy semantic hits.

Now `execute_selective_retrieval()` runs only what the router chose:

| Strategy | Neo4j / exact lookup | Vector + BM25 |
|----------|----------------------|---------------|
| `graph` | Yes | No |
| `vector` | No | Yes |
| `hybrid` | Yes | Yes |
| `eligibility` | N/A (handled in step 1) | N/A |

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
| `path` | `eligibility`, `neo4j_direct`, `full_rag` |
| `retrieval_strategy` | `eligibility`, `deterministic`, `graph`, `vector` (derived post-hoc) |
| `cypher_provenance` | `predefined_yaml`, `predefined_planned`, `llm_graph_plan`, `none` |
| `answer_synthesis` | `eligibility_api`, `formatter`, `gemini_why_only`, `gemini_full` |

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
| `ssi-chat/src/chat_application/ml_client.py` | `route_query()` — Gemini structured output |
| `shared/vertex_client/src/vertex_client/generation.py` | `response_schema` support for Gemini |
| `ssi-chat/src/chat_application/neo4j_intents.py` | Direct Neo4j intent matching |
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
