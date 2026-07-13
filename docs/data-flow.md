# Data flow

How an instruction or payment mutation becomes queryable in Policy Pilot — from domain API to Kafka, Neo4j, and chat.

## End-to-end pipeline

1. **Instruction service** — operator creates or mutates an instruction; ZITADEL JWT is validated; the service calls **authorization-service** with On-Behalf-Of (service account `svc-instruction` + user token); authz evaluates OPA and returns `allow` + `allow_basis`; instruction version and security event (with `details.authorization`) are written to MongoDB **in a single transaction** (`ssi_cash_instructions.instructions` and `security_events.instruction_service`). Domain services do **not** publish to Kafka directly.

2. **Payment service** — middle-office users create payments against approved SSI instructions; the same OBO → authz → OPA path applies; each action writes the payment version and matching security event to MongoDB (`ssi_cash_activities.payments` and `security_events.payment_service`) in one transaction.

3. **Kafka Connect** — four MongoDB source connectors watch those collections and publish **verbatim full documents** to `instruction_security_events`, `instructions`, `payment_security_events`, and `payments`. **ssi-indexer** normalizes versioned `_id` values and security-event ids in `mongo_cdc.py` at consume time.

4. **Authorization service** — sole runtime caller of OPA. Exposes evaluate and eligible-approvers APIs to domain services only (no MongoDB). Reads candidate approvers from `users.yaml` for batch eligibility checks.

5. **SSI indexer** — runs four independent Kafka consumers, all **self-contained** (full snapshots embedded — no API callbacks). Denormalizes `authorization_summary`, `approved_at`, and related fields onto Neo4j `MultimodalDocument` nodes and the graph for chat retrieval.
   - **InstructionSecurityEventPipeline** (`instruction_security_events`) → Neo4j graph + vector doc `source=instruction_security_event`
   - **InstructionPipeline** (`instructions`) → instruction master graph + vector doc `source=instruction_state`
   - **PaymentSecurityEventPipeline** (`payment_security_events`) → payment security graph + vector doc `source=payment_security_event`
   - **PaymentFactPipeline** (`payments`) → payment master graph + vector doc `source=payment_fact`

6. **Policy Pilot** (`ssi-chat`) — selects a search mode (`events` / `instructions` / `payments` / `all`), **routes** the question via Gemini structured output (`RouterDecision`), then runs **selective retrieval** (Neo4j only, vector only, or hybrid). Fast paths skip full RAG: live OPA eligibility for *who can approve?*, Neo4j direct YAML intents for known shapes, deterministic formatters for counts and audit trails. Other questions use **Vertex Gemini** synthesis over retrieved context. See [Intent Determination in Policy Pilot](intent-determination.md).

## Transactional consistency

Every instruction mutation (create, update, submit, approve, reject, suspend, reactivate, use, delete) writes:

- the instruction version to `ssi_cash_instructions.instructions`
- the matching security event to `security_events.instruction_service`

Every payment mutation (create, submit, approve, reject) writes:

- the payment record to `ssi_cash_activities.payments`
- the matching security event to `security_events.payment_service`

in a **single MongoDB multi-document transaction** per service. **Kafka Connect** picks up inserts from those collections and publishes to Kafka; **ssi-indexer** consumes asynchronously. MongoDB must run as a replica set — `docker-compose.yml` initialises `rs0` automatically.

## Storage and topic names

| Layer | Name | Purpose |
|-------|------|---------|
| Vector index | `multimodal_embedding` | Dense search on `MultimodalDocument.embedding` |
| Vector document `source` | `instruction_security_event`, `instruction_state`, `payment_security_event`, `payment_fact` | Document type filter for chat modes |
| MongoDB | `ssi_cash_instructions.instructions` | Instruction versions |
| MongoDB | `ssi_cash_activities.payments` | Payment records |
| MongoDB | `security_events.instruction_service` | instruction-service security events |
| MongoDB | `security_events.payment_service` | Payment security events |
| Kafka | `instruction_security_events` | Instruction security events (Mongo CDC) |
| Kafka | `instructions` | Instruction version rows (Mongo CDC) |
| Kafka | `payment_security_events` | Payment security events (Mongo CDC) |
| Kafka | `payments` | Payment version rows (Mongo CDC) |
