# authz_client

Shared HTTP client for domain services calling **[authorization-service](../../authorization-service/README.md)**.

Used by instruction-service and payment-service for:

- `evaluate_instruction` / `evaluate_payment` — lifecycle allow/deny (**requires** service token + user `X-On-Behalf-Of`)
- `eligible_instruction_approvers` / `eligible_payment_approvers` — batch eligibility (**requires** service token + user OBO)

Authorization outcomes are persisted on Mongo security events and streamed to Neo4j by ssi-indexer (`SecurityEvent`, `ACTED_AS`, `FOR` → version). See [neo4j-graph-model/README.md](../../neo4j-graph-model/README.md).

Install as a path dependency from each service's `pyproject.toml`.
