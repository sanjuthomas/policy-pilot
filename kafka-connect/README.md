# Kafka Connect (MongoDB source)

Distributed **Kafka Connect** worker with the [MongoDB Kafka Connector](https://www.mongodb.com/docs/kafka-connector/) plugin (**1.16.0** on Confluent Hub). Watches MongoDB change streams and publishes **full documents** to the domain Kafka topics. This is the **only** producer for the four application topics — instruction-service and payment-service write Mongo only.

## Connectors

| Connector | MongoDB | Kafka topic |
|-----------|---------|-------------|
| `mongo-instructions-source` | `ssi_cash_instructions.instructions` | `instructions` |
| `mongo-instruction-security-events-source` | `security_events.instruction_service` | `instruction_security_events` |
| `mongo-payments-source` | `ssi_cash_activities.payments` | `payments` |
| `mongo-payment-security-events-source` | `security_events.payment_service` | `payment_security_events` |

All connectors set:

- `publish.full.document.only=true` — message value is the Mongo document only
- `pipeline=[{"$match": {"operationType": "insert"}}]` — **insert-only** change stream; skip `update` events (e.g. closing `out` on a superseded version row). Downstream only needs new rows.
- `copy.existing=true` — backfill existing collection data on first run
- `topic.namespace.map` — route each collection to its topic
- `value.converter=StringConverter` — Mongo connector already serializes JSON; avoids double-encoding at the broker

**No field mapping or SMTs** — Kafka messages are verbatim Mongo documents. For example,
instruction rows use composite `_id` (`{instruction_id}|{version_number}`) and do **not**
include a top-level `instruction_id` field. The **ssi-indexer** consumer maps that shape
to pipeline payloads in `ssi-indexer/src/etl/mongo_cdc.py` at consume time (see also
`etl/kafka_deserialize.py` for legacy double-encoded records). The indexer graph projection is documented in [neo4j-graph-model/README.md](../neo4j-graph-model/README.md) (lifecycle on fact topics; audit via `FOR` on security-event topics).

Downstream consumers: [ssi-indexer/README.md](../ssi-indexer/README.md).

Connector configs live in `connectors/`. `register-connectors.sh` registers them via the Connect REST API (`POST /connectors`) after the worker is healthy.

## Docker

```bash
docker compose up -d kafka-connect
docker compose run --rm kafka-connect-init   # re-register after config changes
```

REST API: http://localhost:8083/connectors

Internal Connect topics (`connect-configs`, `connect-offsets`, `connect-status`) are created by `kafka-init`.
