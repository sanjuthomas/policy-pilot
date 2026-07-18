# Architecture decisions

Why Policy Pilot is built the way it is — identity, policy, persistence, streaming, retrieval, graph, and ML.

## Why ZITADEL?

**What ZITADEL is:** ZITADEL is an open-source cloud-native identity and access management (IAM) platform — think self-hosted Auth0 or Okta. It provides OIDC/OAuth2 authentication, JWT issuance, user management, and metadata storage. In this demo it runs entirely in Docker with no external dependencies.

**How ZITADEL is used:**

Every request to the instruction and payment services carries a ZITADEL-issued JWT Bearer token. Each service validates it against ZITADEL's OIDC discovery endpoint (`/.well-known/openid-configuration`) and extracts the caller's identity — user ID, roles, LOB, and reporting line — from ZITADEL user metadata:

| Metadata key | Meaning | Used for |
|---|---|---|
| `subject_user_id` | Business user ID (`mo-100`, `ficc-300`) | Security events, graph nodes |
| `given_name` / `family_name` | Full name | `display_name` in graph + chat answers |
| `title` | Seniority (Analyst / VP / MD) | OPA approval matrix |
| `roles` | JSON array (`INSTRUCTION_CREATOR`, `INSTRUCTION_APPROVER`) | OPA role check |
| `lob` | Owning profit center (FICC, FX, DESK_*) | OPA LOB ownership check |
| `supervisor_id` | Direct manager's user ID | Inversion-of-control detection in graph |

This metadata is stored in ZITADEL via the `zitadel-seed/seed.py` script, which reads `users.yaml` and calls the ZITADEL admin API to create users and attach metadata. Domain services decode and validate this metadata on every authenticated request. Authorization-service, chat, and the demo harness also **list** ZITADEL users at runtime for directory / eligibility / me-intent answers — `users.yaml` is seed-only after bootstrap.

**Service accounts** (`svc-instruction`, `svc-payment`) authenticate to authorization-service and (for payment) instruction-service using machine tokens. On user-initiated lifecycle calls, the domain service forwards the user's JWT in `X-On-Behalf-Of` so OPA evaluates policy for the real actor, not the service account.

**Audience validation:** Docker Compose sets a shared `OIDC_AUDIENCE=policy-pilot` on authz, instruction, payment, chat, indexer, and harness. When a Bearer token is a JWT, services verify `aud` and **fail closed** on audience mismatch (no userinfo fallback). Demo login still uses ZITADEL **session** tokens (opaque), which skip the JWT path and resolve via `X-Session-Id` — unaffected by audience. A future hardening step is to mint OIDC access tokens bound to a ZITADEL API project id and set `OIDC_AUDIENCE` to that project id.

**Why ZITADEL over a simpler alternative:** ZITADEL provides a **user metadata API** that allows arbitrary key-value pairs per user (roles, LOB, supervisor). Identity attributes that drive authorization policy (LOB ownership, seniority, org hierarchy) live in the identity layer — not hard-coded in the application or duplicated across services.

---

## Why OPA?

**What OPA is:** Open Policy Agent is a **policy-as-code** engine. It decouples authorization decisions from application code — the application sends a structured query (`input`) to OPA and receives a boolean decision (allow / deny). Policies are written in **Rego**, a declarative language designed for hierarchical data queries.

**How OPA is used:**

Only **authorization-service** calls OPA at runtime. Domain services build structured policy input and POST to authz; authz forwards to OPA's Data API:

```
instruction-service / payment-service
  → authorization-service  (svc-* token + X-On-Behalf-Of: user JWT)
  → OPA POST /v1/data/{instruction|payment}/lifecycle/allow
```

Example input (built by the domain service, evaluated by authz → OPA):

```json
{
  "input": {
    "action": "APPROVE",
    "subject": { "user_id": "mo-100", "title": "Analyst", "roles": ["INSTRUCTION_CREATOR"], "lob": null },
    "resource": { "instruction_id": "...", "owning_lob": "FICC", "created_by": "mo-100", "status": "SUBMITTED" }
  }
}
```

OPA evaluates the Rego policy bundle and returns `allow` / `deny`. Authorization-service also queries **`allow_basis`**, **`violations`**, and **`is_alert`**. Domain services store the result on every security event as `details.authorization` and copy `authorization.summary` to `event.reason` for authorized actions.

**OPA security in this demo:** OPA listens on `:8181` with no authentication (typical for a local policy sidecar). The trust boundary is **authorization-service**, which requires `svc-instruction` or `svc-payment` bearer tokens. Do not expose OPA to untrusted networks in production.

Example authorization block on an APPROVE security event:

```json
{
  "engine": "opa",
  "package": "instruction.lifecycle",
  "action": "APPROVE",
  "decision": "allow",
  "allow_basis": [
    "approval matrix: Vice President may approve work by Analyst",
    "approver LOB FICC matches instruction LOB",
    "approver does not report to creator",
    "role INSTRUCTION_APPROVER"
  ],
  "summary": "Vasquez, Elena (ficc-300) was allowed to APPROVE because approval matrix: Vice President may approve work by Analyst; ..."
}
```

**Key policies enforced:**

| Rule | Rego condition | What it catches |
|---|---|---|
| Role gate | `"INSTRUCTION_APPROVER" in subject.roles` | Non-approvers attempting to approve |
| Creator cannot approve | `subject.user_id != resource.created_by` | Self-approval (cross-approval collusion) |
| Subordinate cannot approve | `approver.supervisor_id != creator.user_id` | Manager approving subordinate's instruction (inversion of control) |
| LOB ownership | `subject.lob == resource.owning_lob` | Wrong-desk approval (e.g. FX desk approving FICC instruction) |
| Status gate | `resource.status == "SUBMITTED"` | Approving an instruction not yet submitted |
| Role segregation | `"INSTRUCTION_CREATOR" not in subject.roles` | Middle-office creator accounts cannot approve |

**Why policy-as-code matters:** Allows and denials both produce structured audit records in Kafka → Neo4j. Denials surface as `ALERT` events for fraud-pattern questions. Allows carry `details.authorization` so chat can answer approval audit questions with **Who / When / Why**. See [Authorization audit trail](authorization-audit-trail.md).

**Why OPA over embedding auth in domain services:** Policy logic changes independently of application logic. Adding a new rule requires editing a `.rego` file and reloading OPA — not rebuilding domain services. OPA mounts `opa-policy-seed/policies/` and loads Rego on every start.

---

## Why MongoDB for security events?

Security events are **write-heavy, append-only, and schema-flexible**. Different event actions (CREATE, APPROVE, REJECT, VIEW) carry different payloads — a rejection includes a reason, an approval includes the approver's LOB, a VIEW includes a resource path.

MongoDB fits naturally because:

- **Schemaless documents** — each event is stored as-is with no schema migration when new fields are added.
- **Long-term retention** — TTL indexes allow per-collection expiry policies for regulatory audit trails vs transient operational events.
- **Bi-temporal versioning** — instructions are stored as versioned documents (`version_number`, `in`/`out` timestamps) as self-contained snapshots.
- **Change Streams** — the instruction-service live security-event monitor and `SecurityEventWatcher` for real-time UI updates consume ordered, resumable change feeds.
- **Replica set transactions** — writing an instruction version and its security event in a single ACID multi-document transaction requires a MongoDB replica set (`rs0` in `docker-compose.yml`).

---

## Why Kafka?

Every instruction or payment mutation produces a **security event** in MongoDB. **Kafka Connect** CDC decouples domain services from downstream consumers.

Key reasons:

- **Fan-out with no coupling** — new consumers subscribe independently without changes to domain services.
- **Durable replay** — ETL can seek back and replay without touching domain APIs.
- **Ordered delivery per partition** — events for the same key arrive in order, which matters for `CURRENT` relationship management in Neo4j.
- **Backpressure isolation** — spikes in activity do not block domain services; Kafka absorbs the burst.

In this demo Kafka runs as a single broker with no replication. Production would use a multi-broker cluster with `replication.factor=3` and `min.insync.replicas=2`.

---

## Why Neo4j dense vector search?

No single retrieval strategy reliably handles the full range of policy, lifecycle, and audit questions investigators ask.

**Dense vector search** (via **Vertex AI `text-embedding-004`** on `MultimodalDocument` nodes) excels at **semantic similarity** — "who tried to approve each other's instructions?" or "show me policy denial events for FX desk".

**Exact identifiers** (UUIDs, payment ids, user ids) and **structured relationships** are handled by dedicated Neo4j lookups and graph/Cypher paths.

**Hybrid retrieval** in chat means **vector + graph** (RRF when both run), selected per question by the [intent router](intent-determination.md).

Using **one Neo4j store** for graph traversal and dense vectors keeps infrastructure simple — no separate vector database.

---

## Why Neo4j (knowledge graph)?

Dense vector retrieval operates over **flat document similarity**. Relationships between events — cross-approval, duplicate routes, org hierarchy — are **invisible** to document ranking alone.

A **knowledge graph** makes those relationships first-class:

```
(User ficc-300)-[:APPROVED]->(InstructionVersion v2)
(User mo-100)-[:CREATED]->(InstructionVersion v2)
```

| Question | Why flat retrieval fails | How Neo4j answers it |
|---|---|---|
| Users who approved each other's instructions? | Requires joining two query results | `MATCH (a)-[:APPROVED]->(va)<-[:CREATED]-(b), (b)-[:APPROVED]->(vb)<-[:CREATED]-(a)` |
| Full lifecycle timeline of instruction X? | Each event is a separate document | `MATCH (e)-[:TARGETS]->(i) ORDER BY e.timestamp` |
| Instructions sharing the same creditor account? | No link between documents | `MATCH (v1)-[:CONFLICTS_WITH]->(v2)` |
| All users in FICC profit center? | Keyword search on `lob=FICC` | `MATCH (u)-[:BELONGS_TO]->(p:ProfitCenter {lob: 'FICC'})` |

The chat pipeline uses **planned Cypher** from `shared/cypher_builder` for known question shapes, and **Vertex Gemini** graph plan extraction when no planner rule matches. Graph rows are injected into LLM context alongside vector hits when the router selects hybrid or graph strategy.

The root [README](../README.md#neo4j-graph-model) summarizes writer roles; see [neo4j-graph-model/README.md](../neo4j-graph-model/README.md) for diagrams, property catalog, and example Cypher.

---

## Why Vertex AI?

**What Vertex provides:** Google Cloud Vertex AI hosts the **embedding** and **generative** models. Both **ssi-indexer** and **Policy Pilot** call Vertex through `shared/vertex_client/`.

| Role | Model | Used by |
|------|-------|---------|
| Document + query embeddings | `text-embedding-004` (768-dim) | ssi-indexer (write), Policy Pilot (query) |
| Semantic routing | `gemini-2.5-flash` | Policy Pilot (`RouterDecision` JSON) |
| Answer synthesis + authorization WHY rewrite | `gemini-2.5-flash` | Policy Pilot |
| Graph query plan extraction (fallback) | `gemini-2.5-flash` | Policy Pilot → `cypher_builder` |

**Why Vertex for all ML:**

- **Consistent vectors** — indexer and chat use the same embedding model and dimension (`768`).
- **No local GPU** — embeddings and generation run in GCP; the demo stack is containerized aside from GCP credentials.
- **Production-shaped** — mirrors managed LLM + local retrieval patterns common in regulated environments.

**GCP setup:** see [GCP and Vertex AI setup](gcp-setup.md). Smoke test: `python scripts/vertex_smoke_test.py`.

> **Important:** changing the embedding model or dimension requires dropping Neo4j vector indexes, resetting Kafka consumer offsets, and replaying the ETL (see `ssi-indexer/README.md`).

---

## Graph queries — `shared/cypher_builder`

Neo4j graph retrieval uses a **two-tier** approach:

1. **Planned Cypher** — rule-based intent matching in `shared/cypher_builder` for counts, rankings, hierarchy traversals, approval lookups, and other high-confidence question shapes. No LLM call.
2. **Gemini graph plan extraction** — when no planner rule matches, Policy Pilot asks Gemini for a structured `GraphQueryPlan` (intent + parameters), which `cypher_builder` turns into validated read-only Cypher.

The indexer Search Console `POST /api/cypher/generate` endpoint uses the same planner (deterministic matches only).

---

## Models and retrieval

### Embedding — Vertex `text-embedding-004`

| Property | Value |
|----------|-------|
| Model | `text-embedding-004` |
| Output dimension | **768** float32 |
| Index task | `RETRIEVAL_DOCUMENT` (ETL) / `RETRIEVAL_QUERY` (chat) |

### Generative — Vertex `gemini-2.5-flash`

| Property | Value |
|----------|-------|
| Model | `gemini-2.5-flash` (configurable via `VERTEX_GEMINI_MODEL`) |
| Used for | Routing, answer synthesis, authorization WHY summarization |

Retrieved context is passed to Gemini; the model does **not** emit raw Cypher directly — graph fallback uses structured plan extraction via `cypher_builder`.

### Per-question LLM calls (Policy Pilot)

| Step | Provider | When |
|------|----------|------|
| Semantic routing | Vertex `gemini-2.5-flash` | Every question |
| Query embedding | Vertex `text-embedding-004` | Vector / hybrid strategy |
| Graph plan extraction | Vertex `gemini-2.5-flash` | Graph fallback when no planner rule matches |
| Answer synthesis | Vertex `gemini-2.5-flash` | Open-ended questions |
| Authorization WHY rewrite | Vertex `gemini-2.5-flash` | Approval audit questions only |
| Planned Cypher | `cypher_builder` (no LLM) | Counts, rankings, hierarchy, known audit shapes |

WHO and WHEN in approval audit answers remain deterministic from indexed data.
