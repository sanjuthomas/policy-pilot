# Sequence Service

Allocates **monotonic business identifiers** for instructions, payments, and security events. Domain services call this API before inserting versioned Mongo rows so IDs are unique and human-readable.

## URL (Docker)

http://localhost:8095/docs

## ID formats

| Entity | Example ID | Counter key |
|--------|------------|-------------|
| Instruction | `20260705-FICC-I-12` | `{yyyymmdd}-{LOB}-I` |
| Payment | `20260705-FICC-P-3` | `{yyyymmdd}-{LOB}-P` |
| Security event | `{resource_id}-SE-7` | `{resource_id}-SE` |

Security event IDs are scoped per parent instruction or payment sequence id. Mongo stores them as document `_id`; APIs expose `event_id` derived from `_id`.

## API

| Method | Path | Caller | Purpose |
|--------|------|--------|---------|
| POST | `/api/v1/sequences/next` | instruction-service, payment-service | Next instruction or payment id |
| POST | `/api/v1/sequences/security-events/next` | instruction-service, payment-service | Next security event id for a resource |

### Example: next instruction id

```bash
curl -s -X POST http://localhost:8095/api/v1/sequences/next \
  -H 'Content-Type: application/json' \
  -d '{
    "business_date": "2026-07-05",
    "owning_lob": "FICC",
    "entity_type": "INSTRUCTION"
  }'
```

### Example: next security event id

```bash
curl -s -X POST http://localhost:8095/api/v1/sequences/security-events/next \
  -H 'Content-Type: application/json' \
  -d '{"resource_id": "20260705-FICC-I-12"}'
```

## Storage

Counters live in MongoDB (`ssi_sequences.counters`). Allocation uses atomic find-and-increment — safe under concurrent writers from multiple domain service instances.

## Who calls sequence-service

| Caller | When |
|--------|------|
| **instruction-service** | Create instruction; emit instruction security event |
| **payment-service** | Create payment; emit payment security event |

**Not callers:** authorization-service, ssi-indexer (reads ids from Kafka payloads), ssi-chat, demo harness.

## Run locally

```bash
cd sequence-service
pip install -e .
sequence-service   # :8095
```

Requires MongoDB — see root `docker-compose.yml`.

| Variable | Default |
|----------|---------|
| `MONGODB_URI` | `mongodb://localhost:27017/?replicaSet=rs0` |

## Docker

```bash
docker compose up -d sequence-service
```

Shared client: `shared/sequence_client` (path dependency in domain services).
