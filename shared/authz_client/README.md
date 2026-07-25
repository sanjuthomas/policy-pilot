# authz_client

Shared HTTP client for domain services calling **[authorization-service](../../authorization-service/README.md)**.

Used by instruction-service and payment-service for:

- `evaluate_instruction` / `evaluate_payment` — lifecycle allow/deny (**requires** service token + user `X-On-Behalf-Of`)
- `evaluate_payment_exchange` — payment decision plus the exact evaluate request
  and raw response used for governed activity / security-event evidence
- `eligible_instruction_approvers` / `eligible_payment_approvers` — batch eligibility (**requires** service token + user OBO)

Authorization outcomes are persisted on Mongo security events and streamed to Neo4j by ssi-indexer (`SecurityEvent`, `ACTED_AS`, `FOR` → version). See [neo4j-graph-model/README.md](../../neo4j-graph-model/README.md).

Payment-service stores the exchange on the authoritative security event. The
[Technology Auditor Console](../../audit-service/README.md) follows the audit
execution's security-event id and displays that original request/response rather
than duplicating OPA audit data.

Install as a path dependency from each service's `pyproject.toml`.
