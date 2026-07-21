# cypher-builder-svc

Thin FastAPI HTTP bridge over [`shared/cypher_builder`](../shared/cypher_builder) for the Java chat A/B experiment (`ssi-chat-j`).

| Item | Value |
|------|--------|
| Port | **8097** |
| Role | Plan + validate read-only Cypher (deterministic `neo4j_direct`) |
| Auth | Network-local (no public ingress) |

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness |
| `POST` | `/v1/plan` | `question` + `mode` → planned Cypher |
| `POST` | `/v1/validate` | Normalize + enforce read-only |

## Run (local)

With Neo4j / stack optional — this service is CPU-only:

```bash
pip install -e ./shared/telemetry -e ./shared/cypher_builder -e ./cypher-builder-svc
cd cypher-builder-svc
uvicorn cbs.main:app --host 0.0.0.0 --port 8097
```

Or via Compose:

```bash
docker compose up -d --build cypher-builder-svc
curl -s http://localhost:8097/health
```

## Example plan

```bash
curl -s http://localhost:8097/v1/plan \
  -H 'Content-Type: application/json' \
  -d '{"question":"How many ALERT events happened today?","mode":"events"}'
```
