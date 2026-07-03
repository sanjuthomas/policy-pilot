# Search text profiles

Each YAML file declares which fields are flattened into **`search_text`** — the string
embedded as the dense vector and indexed for BM25 in Neo4j multimodal documents.

| File | Multimodal `source` | Wired to builder |
|------|-----------------|------------------|
| `instruction_security_event.yaml` | `instruction_security_event` | **Yes** |
| `instruction_state.yaml` | `instruction_state` | **Yes** |
| `payment_security_event.yaml` | `payment_security_event` | **Yes** |
| `payment_fact.yaml` | `payment_fact` | **Yes** |

## What is *not* in these files

Full JSON documents remain in the multimodal **payload** (`security_event`,
`instruction_snapshot`, `payment_snapshot`, etc.) and in the admin UI. Only fields
listed under `includes` (and shared `profiles`) feed the embedding string.

Paths use dot notation from the profile's `context_root` document (usually `merged`
for instruction security events, or the normalized Kafka fact/event dict for others).

## Versioned Mongo `_id` conventions

Kafka Connect publishes full Mongo documents. The ETL normalizes them in
`etl.mongo_cdc` before building `search_text`:

| Topic | Mongo `_id` | Normalized id field | Search profile |
|-------|-------------|---------------------|----------------|
| `instructions` | `{instruction_id}\|{version}` | `instruction_id` (entity id only) | `instruction_state.yaml` |
| `payments` | `{payment_id}\|{version}` | `payment_id` | `payment_fact.yaml` |
| `instruction_security_events` | sequence id | `event_id` | `instruction_security_event.yaml` |
| `payment_security_events` | sequence id | `event_id` | `payment_security_event.yaml` |

Composite version keys and raw `_id` values are listed under `excludes` — they stay
in the multimodal payload for lookup but are not embedded in `search_text`.

## Editing

After changing a profile, run:

```bash
cd ssi-indexer && python3 -m pytest tests/test_search_profiles.py -q
```

View wired field lists in the **Search text profiles** panel on the ETL admin UI
(`GET /api/search-profiles`).
