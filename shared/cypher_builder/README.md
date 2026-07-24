# cypher_builder

Shared **Neo4j query planner** used by the **ssi-indexer Search Console**. Maps natural-language questions to **read-only Cypher** without an LLM when the shape is known (counts, rankings, hierarchy, audit lookups).

Policy Pilot chat (`ssi-chat-j`) plans Cypher **in-process** in Java (`com.sanjuthomas.policypilot.cypher`). It does **not** call this package or the retired `cypher-builder-svc` HTTP bridge.

## Consumers

| Service | Usage |
|---------|--------|
| **ssi-indexer** | Search Console Cypher generation (`POST /api/intent/extract`, `/api/cypher/generate`) |
| ~~ssi-chat~~ / ~~cypher-builder-svc~~ | Retired — do not reintroduce into Compose or CI |

## Graph edge names

Queries use lifecycle edges `CREATED_IV`, `APPROVED_IV`, `CREATED_PV`, `APPROVED_PV`, … and audit links `FOR` → version. See [neo4j-graph-model/README.md](../../neo4j-graph-model/README.md).

Examples handled without LLM:

- ALERT / INFO event counts and rankings
- Mutual approval and subordinate-approves-supervisor patterns (`APPROVED_IV`, `CREATED_IV`, `REPORTS_TO`)
- Payment totals and LOB filters
- Instruction / payment approver lookups by id

## Install

Path dependency from `ssi-indexer`:

```bash
pip install -e shared/cypher_builder
```

## Tests

```bash
cd shared/cypher_builder
pip install -e .
pytest
```
