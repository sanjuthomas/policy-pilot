# SSI Demo Harness

Web UI and CLI helpers for driving **instruction** and **payment** lifecycles with **ZITADEL OIDC** authentication.

Use it to generate realistic traffic that flows **MongoDB → Kafka Connect → Kafka → ssi-indexer → Neo4j**, including OPA policy demo scenarios that produce `ALERT` and `INFO` security events (indexed in Neo4j via `FOR` audit links).

After seeding, allow the indexer to catch up before querying ALERT counts in PolicyPilot. A full seed targets dozens of instruction and payment ALERTs; partial seeds or instruction-service list timeouts may yield fewer events — re-run `./ssi-demo-harness/seed-demo-data.sh --seed-only` when the stack is idle if counts look low.

### Verify ALERT counts

```bash
# Mongo (source of truth for security events)
docker exec mongodb mongosh security_events --quiet --eval '
printjson({
  instruction_ALERT: db.instruction_service.countDocuments({severity:"ALERT"}),
  payment_ALERT: db.payment_service.countDocuments({severity:"ALERT"}),
});
'

# Neo4j (after indexer catch-up)
docker exec neo4j cypher-shell -u neo4j -p devpassword \
  "MATCH (e:SecurityEvent {severity:'ALERT'}) RETURN count(e) AS total"
```

### Known issue: instruction list timeout

Harness actions and `seed_extra_alerts` call `GET /api/v1/instructions?limit=500`. Instruction-service runs a **VIEW** authorization check per row (~1 s each), so large lists can exceed the harness 30 s httpx timeout. Use `--seed-only` when the stack is idle, or run harness actions in smaller batches from the UI.

## URL

http://localhost:8091

## Actions (UI)

Each action has a count field and a run button:

### Instructions

| Action | Description |
|--------|-------------|
| Create instructions | Seed N instructions via instruction-service API (varied LOB / type / currency) |
| Submit | Submit draft instructions |
| Approve | Approve pending instructions (matching OPA approval matrix) |
| Reject | Reject pending instructions |
| Run scenario | Fixed 8-step OPA scenario (success + expected denials) |

The instruction scenario verifies MongoDB security event count increases and includes steps such as creator self-approval denial and wrong-LOB read denial.

### Payments

| Action | Description |
|--------|-------------|
| Create payments | Seed N payments against approved instructions |
| Submit payments | Front-office users submit DRAFT payments |
| Approve payments | Funding approvers approve SUBMITTED payments |
| Run payment scenario | Fixed 7-step OPA scenario (DRAFT → SUBMIT → APPROVE with denials) |

The payment scenario verifies MongoDB counts: **+4 ALERT** and **+3 INFO** events in `security_events.payment_service`:

1. `pay-101` creates FICC payment (DRAFT, INFO)
2. `pay-201` (approver only) tries to create → DENY (ALERT)
3. `pay-101` (middle office) tries to submit → DENY (ALERT)
4. `fo-ficc-101` submits payment → SUBMITTED (INFO)
5. `pay-101` tries to approve own payment → DENY (payment ALERT)
6. `pay-203` (FX-only) tries to approve → DENY on FICC instruction VIEW (instruction ALERT; no payment ALERT)
7. `pay-201` approves → APPROVED (INFO)

Requires at least one approved FICC instruction (run instruction create + approve first, or the full instruction scenario).

## Authentication

Uses ZITADEL **Session API** with the login-client PAT from bootstrap volume. Demo users are seeded into ZITADEL from `zitadel-seed/users.yaml` (password `Password1!`). Runtime directory queries hit ZITADEL, not the YAML file.

Seed users after a fresh stack:

```bash
PAT=$(docker exec zitadel-login cat /zitadel/bootstrap/login-client.pat | tr -d '\n')
cd zitadel-seed && ZITADEL_PAT="$PAT" python3 seed.py
```

### One-command demo seed (reset + data + ALERTs)

From the repo root (or anywhere), run the harness seed script. By default it clears all volumes, starts the stack, seeds Zitadel, then creates instructions/payments with many policy-denial **ALERT** events:

```bash
./ssi-demo-harness/seed-demo-data.sh
```

Seed only (stack already running):

```bash
./ssi-demo-harness/seed-demo-data.sh --seed-only
```

Optional env overrides: `CREATE_INSTRUCTIONS`, `INSTRUCTION_POLICY_RUNS`, `PAYMENT_POLICY_RUNS`, `HARNESS_URL`, etc. Run `./ssi-demo-harness/seed-demo-data.sh --help` for details.

Includes service accounts **`svc-instruction`** and **`svc-payment`** (not used by the harness UI).

## Instruction payloads

Fixtures build the **SSI route template** schema (`currency` field, no payment amounts). See `src/harness/fixtures.py`.

## Configuration (Docker)

| Variable | Default |
|----------|---------|
| `INSTRUCTION_SERVICE_URL` | `http://instruction-service:8000` |
| `PAYMENT_SERVICE_URL` | `http://payment-service:8093` |
| `ZITADEL_URL` | `http://zitadel-proxy` |
| `ZITADEL_HOST_HEADER` | `localhost` |
| `EMAIL_DOMAIN` | `ssi.local` |
| `DEFAULT_PASSWORD` | `Password1!` |
| `MONGODB_URI` | `mongodb://mongodb:27017/?replicaSet=rs0` |
| `SECURITY_EVENTS_COLLECTION` | `instruction_service` |
| `PAYMENT_SECURITY_EVENTS_COLLECTION` | `payment_service` |

## Run locally

```bash
cd ssi-demo-harness
pip install -e .
ssi-demo-harness-ui   # :8091
```

CLI entry point: `ssi-demo-harness`

## Docker

```bash
docker compose up -d ssi-demo-harness
```

Requires instruction-service, payment-service, authorization-service, Kafka Connect, and ZITADEL running.
