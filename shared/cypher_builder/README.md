# cypher_builder

Shared **Neo4j query planner** for PolicyPilot and the indexer Search Console. Maps natural-language questions to **read-only Cypher** without an LLM when the shape is known (counts, rankings, hierarchy, audit lookups).

## Consumers

| Service | Usage |
|---------|--------|
| **ssi-chat** | Planned graph queries in `chat_application/cypher.py` before LLM fallback |
| **ssi-indexer** | Search Console Cypher generation (`POST /api/intent/extract`) |

## Graph edge names

Queries use lifecycle edges `CREATED_IV`, `APPROVED_IV`, `CREATED_PV`, `APPROVED_PV`, … and audit links `FOR` → version. See [neo4j-graph-model/README.md](../../neo4j-graph-model/README.md).

Examples handled without LLM:

- ALERT / INFO event counts and rankings
- Mutual approval and subordinate-approves-supervisor patterns (`APPROVED_IV`, `CREATED_IV`, `REPORTS_TO`)
- Payment totals and LOB filters
- Instruction / payment approver lookups by id

## Install

Path dependency from `ssi-chat` and `ssi-indexer`:

```bash
pip install -e shared/cypher_builder
```

## Tests

```bash
cd shared/cypher_builder
pip install -e .
pytest
```
