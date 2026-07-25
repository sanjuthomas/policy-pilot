# Technology Auditor Console

Read-only evidence application for members of the ZITADEL `TECH_AUDITORS` group.

It reads MongoDB directly and presents:

- instruction-service security events;
- payment-service security events;
- governed Create Payment audit executions;
- linked OPA evaluate request/response from the payment security event.

The service does not create a second OPA audit record. Audit executions retain the
security-event ID and the UI loads the original security-event document on demand.

## Local use

```bash
docker compose up -d --build audit-service
open http://localhost:8097
```

Demo logins (`TECH_AUDITORS`): `audit-001`, `audit-002`, `audit-003` / `Password1!`.

## Verification

```bash
ruff check src/ --select E,F,W,I --ignore E501
pytest --cov=audit_console --cov-report=term-missing --cov-fail-under=80
```
