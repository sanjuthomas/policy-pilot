# Kafka Connect (MongoDB source)

Distributed **Kafka Connect** worker with the [MongoDB Kafka Connector](https://www.mongodb.com/docs/kafka-connector/) plugin. Watches MongoDB change streams and publishes **full documents** to the domain Kafka topics.

## Connectors

| Connector | MongoDB | Kafka topic |
|-----------|---------|-------------|
| `mongo-instructions-source` | `ssi_cash_instructions.instructions` | `instructions` |
| `mongo-instruction-security-events-source` | `security_events.instruction_service` | `instruction_security_events` |
| `mongo-payments-source` | `ssi_cash_activities.payments` | `payments` |
| `mongo-payment-security-events-source` | `security_events.payment_service` | `payment_security_events` |

All connectors set:

- `publish.full.document.only=true` — message value is the Mongo document only
- `copy.existing=true` — backfill existing collection data on first run
- `topic.namespace.map` — route each collection to its topic

**No field mapping or SMTs** — Kafka messages are verbatim Mongo documents. For example,
instruction rows use composite `_id` (`{instruction_id}|{version_number}`) and do **not**
include a top-level `instruction_id` field. The **ssi-indexer** consumer maps that shape
to pipeline payloads in `ssi-indexer/src/etl/mongo_cdc.py` at consume time.

Connector configs live in `connectors/`. `register-connectors.sh` registers them via the Connect REST API (`POST /connectors`) after the worker is healthy.

## Docker

```bash
docker compose up -d kafka-connect
docker compose run --rm kafka-connect-init   # re-register after config changes
```

REST API: http://localhost:8083/connectors

Internal Connect topics (`connect-configs`, `connect-offsets`, `connect-status`) are created by `kafka-init`.
