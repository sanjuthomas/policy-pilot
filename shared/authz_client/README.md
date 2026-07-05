# authz_client

Shared HTTP client for domain services calling **[authorization-service](../../authorization-service/README.md)**.

Used by instruction-service and payment-service for:

- `evaluate_instruction` / `evaluate_payment` — lifecycle allow/deny (OBO when user token present)
- `eligible_instruction_approvers` / `eligible_payment_approvers` — batch eligibility (service token only)

Authorization outcomes are persisted on Mongo security events and streamed to Neo4j by ssi-indexer (`SecurityEvent`, `ACTED_AS`, `FOR` → version). See [neo4j-graph-model/PHASE-0.md](../../neo4j-graph-model/PHASE-0.md).

Install as a path dependency from each service's `pyproject.toml`.
