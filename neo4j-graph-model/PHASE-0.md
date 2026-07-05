# Phase 0 — Neo4j graph rebuild specification

Frozen design for the **read-optimized** Neo4j model. Implementation follows this document; alpha ETL is replaced, not patched incrementally.

**Demo constraint:** Data is disposable. Wipe Neo4j and reload from Mongo (via Kafka fact/security-event topics or a batch loader) whenever the model changes.

---

## Principles

| Principle | Rule |
|-----------|------|
| Read-optimized | Redundant edges and denormalized root properties are intentional |
| Append-only versions | Never delete `*Version` nodes; history via `HAS_VERSION`, `SUPERSEDES`, `valid_in`/`valid_out` |
| Two writers, symmetric | **Fact pipelines** = state; **security-event pipelines** = audit only |
| Named lifecycle only | No `MUTATED`, no `APPROVED_FOR` |
| Domain approval | `(User)-[:APPROVED_*]->(Version)` = regulatory sign-off on the **route**, not approval of a person |
| Property naming | `snake_case` everywhere in Neo4j (matches Mongo payloads) |

---

## Writers

| Pipeline | Topic | Owns |
|----------|-------|------|
| `InstructionPipeline` | `instructions` | Instruction/Payment **state**: versions, `CURRENT`, lifecycle `_*IV`, structural edges, `CONFLICTS_WITH`, root denorm, `SUPERSEDES`, multimodal `instruction_state` |
| `PaymentFactPipeline` | `payments` | Payment **state**: versions, `CURRENT`, lifecycle `_*PV`, `FOR_INSTRUCTION`, `HAS_PAYMENT`, `CONSUMED`/`CONSUMED_BY`, root denorm, `SUPERSEDES`, multimodal `payment_fact` |
| `InstructionSecurityEventPipeline` | `instruction_security_events` | `SecurityEvent`, `ACTED_AS`, `FOR` → `InstructionVersion`, `INVOLVES_LOB`, sparse version merge for search |
| `PaymentSecurityEventPipeline` | `payment_security_events` | `SecurityEvent`, `ACTED_AS`, `FOR` → `PaymentVersion`, `INVOLVES_LOB`, sparse version merge for search |

**Security-event pipelines must not write:** lifecycle edges, `CURRENT`, `CONSUMED`, `HAS_PAYMENT`, `FOR_INSTRUCTION`, `SUPERSEDES`.

**Removed from alpha (do not write):** `TARGETS`, `TARGETS_*`, `MUTATED`, `APPROVED_FOR`.

---

## Nodes

### `Instruction` (root)

| Property | Source | Notes |
|----------|--------|-------|
| `instruction_id` | stable | Business key |
| `instruction_type` | stable | `STANDING` \| `SINGLE_USE` |
| `owning_lob`, `wire_scope`, `currency` | stable | Classification |
| `current_status` | denorm | From `CURRENT` version |
| `current_version_number` | denorm | From `CURRENT` version |
| `current_used_by` | denorm | Payment id when `current_status = USED`; else null |

### `InstructionVersion`

| Property | Notes |
|----------|-------|
| `version_key` | `{instruction_id}:{version_number}` |
| `version_number`, `status`, `action` | From Mongo fact row |
| `valid_in`, `valid_out` | From Mongo `in` / `out` (`out = 9999-12-31…` ⇒ open) |
| `used_by` | Set when `status = USED` (SINGLE_USE) |
| Route / auth fields | creditor, debtor, dates, `authorization_*`, actor ids, etc. |

### `Payment` (root)

| Property | Notes |
|----------|-------|
| `payment_id` | Business key |
| `instruction_id` | Stable link |
| `current_status` | Denorm from `CURRENT` |
| `current_version_number` | Denorm |
| `current_amount`, `current_currency` | Denorm from `CURRENT` version |

### `PaymentVersion`

Same pattern as instruction versions: `version_key`, `valid_in`/`valid_out`, status, amount, `cancellation_reason`, `instruction_version`, etc.

### `SecurityEvent`

Append-only audit row; `FOR` points at the **version** that was current at event time (when `version_number` present).

---

## Structural edges (fact pipelines only)

| Edge | From → To | When | Delete |
|------|-----------|------|--------|
| `HAS_VERSION` | Root → Version | Every fact row | Never |
| `CURRENT` | Root → Version | Fact row with open `out` | Re-point only; version-aware (never regress) |
| `SUPERSEDES` | Version → Version | `version_number > 1` | Never |
| `OWNED_BY` | Instruction → ProfitCenter | Instruction fact | Never |
| `BELONGS_TO` | InstructionVersion → ProfitCenter | Instruction fact | Never |
| `FOR_INSTRUCTION` | Payment → Instruction | Payment create fact | Never |
| `HAS_PAYMENT` | Instruction → Payment | Payment create fact | Never |
| `CONSUMED` | Payment → Instruction | Payment **submit** on `SINGLE_USE` | **DELETE** on instruction `RELEASE_USE` fact only |
| `CONSUMED_BY` | Instruction → Payment | Same as `CONSUMED` | Same delete rule |
| `CONFLICTS_WITH` | Instruction ↔ Instruction | Instruction approve fact | Never |

Temporary inconsistency is acceptable if payment is terminal before `RELEASE_USE` is indexed (orphan `USED` + consumption until release row arrives).

---

## Instruction lifecycle edges (fact pipeline only)

All: `(User)-[:<EDGE> {at: <iso>}]->(InstructionVersion)`

| Edge | Mongo action | When |
|------|--------------|------|
| `CREATED_IV` | `CREATE` | Initial version |
| `SUBMITTED_IV` | `SUBMIT` | |
| `APPROVED_IV` | `APPROVE` | Regulatory sign-off on route |
| `REJECTED_IV` | `REJECT` | |
| `CANCELLED_IV` | `CANCEL` | Instruction cancelled (not payment-driven) |
| `SUSPENDED_IV` | `SUSPEND` | |
| `REACTIVATED_IV` | `REACTIVATE` | `SUSPENDED` → `APPROVED` |
| `USED_IV` | `USE` | `SINGLE_USE` submit saga |
| `RELEASED_IV` | `RELEASE_USE` | Payment reject/cancel/system-cancel revert |

### `USED_IV` actor (chosen default)

- **From:** OBO **human** (payment submitter — accountability for consumption).
- **Edge properties:** `{at, payment_id, delegated_by}` where `delegated_by` is the service id (e.g. `svc-payment`).
- **Version property:** `used_by = payment_id`.

### `RELEASED_IV` vs `CANCELLED_IV`

| Scenario | Instruction edge |
|----------|------------------|
| User cancels **instruction** | `CANCELLED_IV` |
| Payment reject / cancel / system cancel on approve | `RELEASED_IV` only |

---

## Payment lifecycle edges (fact pipeline only)

All: `(User)-[:<EDGE> {at: <iso>}]->(PaymentVersion)`

| Edge | Mongo action |
|------|--------------|
| `CREATED_PV` | `CREATE_PAYMENT` |
| `SUBMITTED_PV` | `SUBMIT_PAYMENT` |
| `APPROVED_PV` | `APPROVE_PAYMENT` |
| `REJECTED_PV` | `REJECT_PAYMENT` |
| `CANCELLED_PV` | `CANCEL_PAYMENT` (user or system cancel on approve) |

System cancel: same `CANCELLED_PV`; distinguish via `PaymentVersion.cancellation_reason` and optional `cancelled_by_system: true`.

---

## Security-event edges (audit pipelines only)

| Edge | From → To |
|------|-----------|
| `ACTED_AS` | User → SecurityEvent |
| `FOR` | SecurityEvent → InstructionVersion **or** PaymentVersion |
| `INVOLVES_LOB` | SecurityEvent → ProfitCenter |

No `FOR` → Instruction/Payment roots. No lifecycle edges from security-event writers.

---

## SINGLE_USE domain (Mongo ↔ graph)

| Step | Payment | Instruction |
|------|---------|-------------|
| Create payment | `DRAFT`, `FOR_INSTRUCTION`, `HAS_PAYMENT` | unchanged |
| Submit (saga) | `SUBMITTED_PV`, `USED_IV`, `CONSUMED`/`CONSUMED_BY` | `USED`, `used_by` |
| Approve | `APPROVED_PV` | stays `USED` |
| Reject/cancel/system cancel | `REJECTED_PV` or `CANCELLED_PV` first | `RELEASE_USE` → `RELEASED_IV`, **DELETE** consumption edges |
| Draft conflict | Block submit if >1 payment `DRAFT`/`SUBMITTED` on same instruction | Graph: count via `HAS_PAYMENT` + `CURRENT.status` |

---

## Alpha → Phase 0 removals

| Removed | Reason |
|---------|--------|
| `APPROVED_FOR` | Wrong domain semantics; unused in queries |
| `MUTATED` | Named lifecycle edges only |
| `TARGETS`, `TARGETS_*` | Replaced by `FOR` → version |
| Lifecycle edges from instruction SE pipeline | Fact pipeline owns state |
| Instruction SE writing `SUPERSEDES` | Fact pipeline only |

---

## Downstream (same release)

- **`shared/cypher_builder`**: Rename to `_*IV` / `_*PV`; mutual approval uses `APPROVED_IV` + `CREATED_IV`.
- **`ssi-chat` intents**: Update `neo4j_direct.yaml` formatters; add SINGLE_USE queries (`used_by`, consumption, draft conflict) as needed.
- **`relationships.cypher` / READMEs`**: Phase 0 is documented in repo READMEs and `neo4j-graph-model/README.md`; `relationships.cypher` retained as legacy alpha reference only.

---

## Example queries (target names)

**Mutual approval**

```cypher
MATCH (a:User)-[:APPROVED_IV]->(va:InstructionVersion)<-[:CREATED_IV]-(b:User)
MATCH (b)-[:APPROVED_IV]->(vb:InstructionVersion)<-[:CREATED_IV]-(a)
WHERE a.user_id < b.user_id
RETURN a.display_name, b.display_name, va.instruction_id, vb.instruction_id
LIMIT 50
```

**Who holds SINGLE_USE instruction**

```cypher
MATCH (i:Instruction {instruction_id: $id})
RETURN i.current_status, i.current_used_by
```

**Version chain / diff**

```cypher
MATCH (i:Instruction {instruction_id: $id})-[:CURRENT]->(head:InstructionVersion)
MATCH (head)-[:SUPERSEDES*0..]->(v:InstructionVersion)
RETURN v ORDER BY v.version_number DESC
```

**Payment consumption**

```cypher
MATCH (p:Payment {payment_id: $id})-[:CONSUMED]->(i:Instruction)
RETURN i.instruction_id
```

---

## Implementation checklist

- [x] Refactor `InstructionPipeline` / `PaymentFactPipeline` per edge matrix
- [x] Strip state writes from both security-event pipelines; add `FOR`
- [x] Implement `CONSUMED` delete on `RELEASE_USE` only
- [x] Root denormalization on every `CURRENT` advance
- [x] Update `schema.cypher` indexes for `current_*`, `used_by`, `valid_in`/`valid_out`
- [x] Update `cypher_builder` + chat intents
- [x] Align README diagrams and example queries with Phase 0
- [ ] Wipe Neo4j + reload demo dataset
