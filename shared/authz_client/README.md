# authz_client

Shared HTTP client for domain services calling **authorization-service**.

Used by instruction-service and payment-service for:

- `evaluate_instruction` / `evaluate_payment` — lifecycle allow/deny (OBO when user token present)
- `eligible_instruction_approvers` / `eligible_payment_approvers` — batch eligibility (service token only)

Install as a path dependency from each service's `pyproject.toml`.
