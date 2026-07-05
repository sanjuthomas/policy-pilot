# Neo4j Graph Model

Version-controlled **graph schema and documentation** for security events, instruction lifecycle snapshots, and payment lifecycle.

Symmetric **fact** vs **security-event** writers, named lifecycle edges (`_*IV` / `_*PV`), audit links via `FOR` → version, and root denormalization. See **[PHASE-0.md](./PHASE-0.md)** for the full specification.

## Layout

```
schema.cypher              — constraints and indexes (applied by ETL on startup)
PHASE-0.md                 — graph spec (writers, edges, domain rules)
relationships.cypher       — node/relationship property reference (documentation)
ssi-indexer/.../graph_model.py — action → edge maps consumed by ETL
```

## Four ETL pipelines, two writer types

| Pipeline | Kafka topic | Consumer group | Writer role |
|---|---|---|---|
| `InstructionPipeline` | `instructions` | `ssi-instruction-etl` | **Fact** — instruction state |
| `PaymentFactPipeline` | `payments` | `payment-fact-etl` | **Fact** — payment state |
| `InstructionSecurityEventPipeline` | `instruction_security_events` | `instruction-security-event-etl` | **Audit** — instruction security events |
| `PaymentSecurityEventPipeline` | `payment_security_events` | `payment-security-event-etl` | **Audit** — payment security events |

All topics carry **full Mongo documents** via Kafka Connect — the ETL makes no API calls to instruction-service or payment-service.

### Fact pipelines own state

- Version nodes, `HAS_VERSION`, `CURRENT`, `SUPERSEDES`
- Lifecycle edges: `CREATED_IV`, `SUBMITTED_IV`, `APPROVED_IV`, … and `CREATED_PV`, `SUBMITTED_PV`, …
- Structural edges: `OWNED_BY`, `BELONGS_TO`, `CONFLICTS_WITH`, `FOR_INSTRUCTION`, `HAS_PAYMENT`, `CONSUMED` / `CONSUMED_BY`
- Root denormalization: `current_status`, `current_version_number`, `current_used_by`, etc.
- Multimodal docs: `instruction_state`, `payment_fact`

### Security-event pipelines own audit only

- `SecurityEvent`, `ACTED_AS`, `FOR` → `InstructionVersion` or `PaymentVersion`, `INVOLVES_LOB`
- Sparse version merge for search (no lifecycle or `CURRENT` writes)
- Multimodal docs: `instruction_security_event`, `payment_security_event`

## Graph model

```mermaid
flowchart TB
    subgraph Audit["Security-event pipelines (audit only)"]
        UA[User actor] -->|ACTED_AS| SE[SecurityEvent]
        SE -->|FOR| IV[InstructionVersion]
        SE -->|FOR| PV[PaymentVersion]
        SE -->|INVOLVES_LOB| PC[ProfitCenter]
    end

    subgraph InstructionFact["InstructionPipeline (fact)"]
        I[Instruction] -->|HAS_VERSION| IV
        I -->|CURRENT| IV
        I -->|OWNED_BY| PC
        IV -->|BELONGS_TO| PC
        I1[Instruction A] -->|CONFLICTS_WITH| I2[Instruction B]
        IV -->|SUPERSEDES| IVprev[Prior InstructionVersion]
        UC[User] -->|CREATED_IV| IV
        US[User] -->|SUBMITTED_IV| IV
        UAP[User] -->|APPROVED_IV| IV
        UR[User] -->|REJECTED_IV| IV
    end

    subgraph PaymentFact["PaymentFactPipeline (fact)"]
        P[Payment] -->|FOR_INSTRUCTION| I
        P -->|CONSUMED| I
        I -->|CONSUMED_BY| P
        P -->|HAS_VERSION| PV
        P -->|CURRENT| PV
        PV -->|SUPERSEDES| PVprev[Prior PaymentVersion]
        UPC[User] -->|CREATED_PV| PV
        UPS[User] -->|SUBMITTED_PV| PV
        UPA[User] -->|APPROVED_PV| PV
        UPR[User] -->|REJECTED_PV| PV
        I -->|HAS_PAYMENT| P
    end

    U[User] -->|REPORTS_TO| S[User supervisor]
```

## Node properties

| Node | Key properties |
|---|---|
| `Instruction` | `instruction_id`, `instruction_type`, `owning_lob`, `wire_scope`, `currency`, `current_status`, `current_version_number`, `current_used_by` (denorm from `CURRENT`) |
| `InstructionVersion` | `version_key`, `version_number`, `status`, `action`, `valid_in`, `valid_out`, `used_by`, route/auth fields, `creator_user_id`, `approver_user_id`, … |
| `Payment` | `payment_id`, `instruction_id`, `current_status`, `current_version_number`, `current_amount`, `current_currency` (denorm) |
| `PaymentVersion` | `version_key`, `version_number`, `status`, `valid_in`, `valid_out`, `amount`, `currency`, `value_date`, `cancellation_reason`, actor ids, … |
| `SecurityEvent` | `event_id`, `timestamp`, `severity`, `action`, `outcome`, `message`, `authorization_summary`, … |
| `User` | `user_id`, `given_name`, `family_name`, `display_name` (\*), `title`, `lob`, `roles`, `supervisor_id` |
| `ProfitCenter` | `lob` (unique), `name` |

(\*) `display_name` is computed as `"FamilyName, GivenName (user_id)"` on every upsert.

## Relationship types

| Relationship | Direction | Written by | Meaning |
|---|---|---|---|
| `HAS_VERSION` | Root → Version | fact pipelines | All point-in-time versions |
| `CURRENT` | Root → Version | fact pipelines | Latest open version (never regresses) |
| `SUPERSEDES` | Version → Version | fact pipelines | vN → v(N−1) chain |
| `OWNED_BY` | Instruction → ProfitCenter | InstructionPipeline | Instruction LOB |
| `BELONGS_TO` | InstructionVersion → ProfitCenter | InstructionPipeline | Version LOB |
| `CONFLICTS_WITH` | Instruction ↔ Instruction | InstructionPipeline | Same creditor account + currency |
| `FOR_INSTRUCTION` | Payment → Instruction | PaymentFactPipeline | Payment linked to instruction |
| `HAS_PAYMENT` | Instruction → Payment | PaymentFactPipeline | Instruction has payment(s) |
| `CONSUMED` | Payment → Instruction | PaymentFactPipeline | SINGLE_USE submit saga |
| `CONSUMED_BY` | Instruction → Payment | PaymentFactPipeline | Same; **deleted** on instruction `RELEASE_USE` |
| `CREATED_IV` | User → InstructionVersion | InstructionPipeline | Create |
| `SUBMITTED_IV` | User → InstructionVersion | InstructionPipeline | Submit |
| `APPROVED_IV` | User → InstructionVersion | InstructionPipeline | Regulatory sign-off on route |
| `REJECTED_IV` | User → InstructionVersion | InstructionPipeline | Reject |
| `CANCELLED_IV` | User → InstructionVersion | InstructionPipeline | Instruction cancel |
| `SUSPENDED_IV` / `REACTIVATED_IV` | User → InstructionVersion | InstructionPipeline | Suspend / reactivate |
| `USED_IV` / `RELEASED_IV` | User → InstructionVersion | InstructionPipeline | SINGLE_USE use / release |
| `CREATED_PV` … `CANCELLED_PV` | User → PaymentVersion | PaymentFactPipeline | Payment lifecycle |
| `ACTED_AS` | User → SecurityEvent | security-event pipelines | Event actor |
| `FOR` | SecurityEvent → Version | security-event pipelines | Audit link to version at event time |
| `INVOLVES_LOB` | SecurityEvent → ProfitCenter | security-event pipelines | Event LOB |
| `REPORTS_TO` | User → User | all pipelines (user upsert) | Org hierarchy from `supervisor_id` |

## Multimodal documents (four source tags)

The ETL writes searchable `MultimodalDocument` nodes in Neo4j (vector + fulltext). Each document has a `source` tag:

| `source` tag | Document ID | One per | Written by |
|---|---|---|---|
| `instruction_security_event` | `uuid5(event_id)` | Security event | InstructionSecurityEventPipeline |
| `instruction_state` | `uuid5("instruction:" + instruction_id)` | Instruction (upserted on every mutation) | InstructionPipeline |
| `payment_security_event` | `uuid5(event_id)` | Payment security event | PaymentSecurityEventPipeline |
| `payment_fact` | `uuid5("payment:" + payment_id)` | Payment (upserted on every mutation) | PaymentFactPipeline |

The chat API filters by source based on the selected mode:

| Chat mode | Multimodal filter | Neo4j focus |
|---|---|---|
| `events` | `instruction_security_event` + `payment_security_event` | Security events + `FOR` audit links |
| `instructions` | `instruction_state` | Instruction master graph |
| `payments` | `payment_fact` | Payment master graph |
| `all` | no filter | All entity types |

## Neo4j Browser

http://localhost:7474/browser/ — login `neo4j` / `devpassword`

## Apply schema manually

```bash
cat schema.cypher | docker exec -i neo4j cypher-shell -u neo4j -p devpassword
```

## Example queries

```cypher
// Who approved an instruction (from current version properties)
MATCH (i:Instruction {instruction_id: $uuid})-[:CURRENT]->(v:InstructionVersion)
OPTIONAL MATCH (au:User {user_id: v.approver_user_id})
RETURN v.instruction_id, v.approved_at,
       coalesce(au.display_name, v.approver_user_id) AS approver,
       v.authorization_summary, v.authorization_basis
LIMIT 1;

// Mutual approval (collusion signal)
MATCH (a:User)-[:APPROVED_IV]->(va:InstructionVersion)<-[:CREATED_IV]-(b:User)
MATCH (b)-[:APPROVED_IV]->(vb:InstructionVersion)<-[:CREATED_IV]-(a)
WHERE a.user_id < b.user_id
RETURN a.display_name AS user_a, b.display_name AS user_b,
       va.instruction_id AS approved_by_a,
       vb.instruction_id AS approved_by_b;

// Subordinate approved supervisor's instruction (inversion of control)
MATCH (creator:User)-[:CREATED_IV]->(v:InstructionVersion)
MATCH (approver:User)-[:APPROVED_IV]->(v)
MATCH (approver)-[:REPORTS_TO]->(creator)
RETURN creator.display_name AS supervisor, approver.display_name AS subordinate,
       v.instruction_id, v.owning_lob;

// ALERT events with actor and linked version
MATCH (e:SecurityEvent {severity: 'ALERT'})
WHERE date(datetime(e.timestamp)) = date()
OPTIONAL MATCH (actor:User)-[:ACTED_AS]->(e)
OPTIONAL MATCH (e)-[:FOR]->(v:InstructionVersion)
OPTIONAL MATCH (e)-[:FOR]->(pv:PaymentVersion)
RETURN e.event_id, e.message, e.timestamp,
       coalesce(actor.display_name, actor.user_id) AS actor,
       v.instruction_id, pv.payment_id, pv.amount
ORDER BY e.timestamp DESC;

// SINGLE_USE consumption
MATCH (p:Payment {payment_id: $id})-[:CONSUMED]->(i:Instruction)
RETURN i.instruction_id, i.current_status, i.current_used_by;

// Full version chain (newest → oldest)
MATCH (i:Instruction {instruction_id: $uuid})-[:CURRENT]->(head:InstructionVersion)
MATCH (head)-[:SUPERSEDES*0..]->(v:InstructionVersion)
RETURN v.version_number, v.status, v.action
ORDER BY v.version_number DESC;
```

Full specification: [PHASE-0.md](./PHASE-0.md). ETL edge constants: `ssi-indexer/src/etl/graph_model.py`.

## Wipe and reload demo graph

When the graph model changes, wipe Neo4j and replay Kafka (Mongo data stays):

```bash
docker compose -p security-event-rag-demo stop ssi-indexer ssi-chat

docker exec neo4j cypher-shell -u neo4j -p devpassword \
  "MATCH (n) DETACH DELETE n"

docker exec -i neo4j cypher-shell -u neo4j -p devpassword < neo4j-graph-model/schema.cypher

# Reset all four indexer consumer groups to earliest (see ssi-indexer/README.md)

docker compose -p security-event-rag-demo up -d --force-recreate ssi-indexer ssi-chat
```

Re-run `./ssi-demo-harness/seed-demo-data.sh --seed-only` if you need fresh ALERT demo events (replay alone does not recreate harness policy-denial seeds).
