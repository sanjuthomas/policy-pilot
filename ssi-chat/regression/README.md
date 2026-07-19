# PolicyPilot regression suite (`ssi-chat`)

YAML-driven regression tests for **Security Events**, **Instructions**, and **Payments** chat modes.

Each case posts a question to `POST /api/chat` and checks the response with flexible assertions (keywords, numeric answers, minimum sources/graph rows). LLM answers are not compared verbatim — expectations use `answer_contains_any`, `answer_has_number`, etc.

Each case also declares a **`retrieval`** tag — the primary engine the answer is expected to use:

| `retrieval` | Meaning | Count in bank |
|-------------|---------|---------------|
| `deterministic` | Neo4j planned query + formatter; skips LLM synthesis | 28 |
| `graph` | Neo4j planned or LLM Cypher is authoritative (vector skipped) | 31 |
| `vector` | Dense vector hits drive open-ended security-event answers | 3 |
| `eligibility` | Live OPA via authorization-service (`mode: policies`) | 2 |
| `policy_directory` | ZITADEL / covering_lobs / amount-club directory (`mode: policies`) | 2 |
| `skill` | Mutation skill phase-1 + optional confirm/forbidden checks (`persona` login) | 8 |

Selective retrieval (`pipeline/retrieve.py`) runs vector only when strategy is `vector` or `hybrid`. Unit CI does **not** call Gemini; it injects fixture `RouterDecision` values (`tests/fixtures/router_decisions.py`).

## Prerequisites

- Full stack running (`docker compose up -d`), including **Kafka Connect** and **ssi-indexer**
- **GCP Vertex AI** credentials mounted into ssi-indexer and ssi-chat (embeddings + Gemini)
- Harness reachable at http://localhost:8091 (regression seed POSTs `/api/actions/...`)
- Optional larger demo seed: `./ssi-demo-harness/seed-demo-data.sh` (checked in)
- Graph uses `CREATED_IV`, `APPROVED_IV`, `FOR`, … — see [neo4j-graph-model/README.md](../../neo4j-graph-model/README.md)

## Quick run

From repo root with the stack up. Default integration order:

1. **Harness seed** (from `questions.yaml`)
2. **Golden eval** (`eval_golden.yaml`) — before smoke so denial counts stay seed-deterministic
3. **API smoke**
4. **Full chat bank** (`questions.yaml`)

```bash
cd ssi-chat
pip install -e ".[regression]"
PYTHONPATH=. python -m regression.runner --report regression-report.json
```

Skip seed only when the graph is already warm:

```bash
PYTHONPATH=. python -m regression.runner --no-seed
```

Skip golden (smoke + bank only) or smoke:

```bash
PYTHONPATH=. python -m regression.runner --skip-golden
PYTHONPATH=. python -m regression.runner --skip-api-smoke
```

After install:

```bash
ssi-chat-regression
ssi-chat-regression --no-seed   # skip seed
```

## Filters

```bash
# Security Events mode only
python -m regression.runner --mode events

# Tag filter (counts, compliance, who, why, when, …)
python -m regression.runner --tags counts,alerts

# Retrieval filter (deterministic, graph, vector, eligibility, skill)
python -m regression.runner --retrieval skill

# Mutation skills only
python -m regression.runner --tags skill --skip-api-smoke

# Single case
python -m regression.runner --ids events_who_approved_payment_why
```

## Pytest (CI / optional)

Integration tests are skipped unless explicitly enabled:

```bash
cd ssi-chat
pip install -e ".[regression]"
RUN_CHAT_REGRESSION=1 pytest tests/test_chat_regression.py -v
```

Harness seed runs by default. Opt out with `CHAT_REGRESSION_SEED=0` on a warm stack.

## API smoke (cross-service)

Before chat cases, the runner executes **API smoke checks** across services (health, auth gates, admin UI APIs, indexer search/graph/intent extract, payment/instruction eligible-approvers, FO/MO LOB view entitlement). Use:

```bash
# Smoke only (fast, skips Vertex-dependent indexer checks)
PYTHONPATH=. python -m regression.runner --api-smoke-only --no-seed

# Full run: seed + smoke + chat cases (seed is default)
PYTHONPATH=. python -m regression.runner

# Chat only (skip smoke; still seeds unless --no-seed)
PYTHONPATH=. python -m regression.runner --skip-api-smoke
```

Set `API_SMOKE_SKIP_VERTEX=1` to skip Vertex-dependent smoke checks (indexer vector search and intent extract) when GCP credentials are unavailable.

Pytest:

```bash
RUN_API_SMOKE=1 pytest tests/test_api_smoke.py -v
```

### Coverage matrix

| Service | What regression covers |
|---------|------------------------|
| **ssi-demo-harness** | Seed actions, `/api/status`, auth on lifecycle actions (incl. suspend/reactivate) |
| **instruction-service** | UI list (admin), REST auth gate; FO/MO GET LOB view (+/−); lifecycle via harness seed |
| **payment-service** | UI list (admin), REST auth gate; FO/MO GET LOB view (+/−); lifecycle via harness seed |
| **ssi-indexer** | Stats, vector search, graph events, intent extract, cypher run, auth gates |
| **PolicyPilot** (`ssi-chat`) | Compliance + operational persona login, `/api/chat` (65 YAML cases incl. skills), compliance-users |
| **authorization-service** | Health, service-auth gate on evaluate endpoints |
| **payment-service** / **instruction-service** | Eligible-approvers + FO/MO FICC view via **svc-chat + OBO** (bare human JWT rejected); admin UI probes use platform-admin JWT only |

Chat cases exercise RAG end-to-end; they do not call instruction-service/payment REST APIs directly. Indexer and authz are covered by API smoke, not chat YAML.

## RAG retrieval quality evaluation

Every regression run now computes **retrieval-quality metrics** alongside answer assertions:

| Metric | Meaning |
|--------|---------|
| `routing_accuracy` | Share of cases where `ChatResponse.routing.path` matches the declared `retrieval` strategy |
| `mean_entity_recall` | Entity IDs in the question found in answer, sources, or graph rows |
| `mean_source_precision@5` | Share of top-5 sources using expected channels (`vector`, `neo4j`, …) |
| `mean_groundedness` | Answer token overlap with primary graph row (deterministic/graph cases) |
| `mean_faithfulness` | Answer token overlap with retrieved context (lightweight ragas-style proxy) |

Metrics are printed after the case summary and written to `--report` JSON under `chat.quality_summary` and per-case `quality`.

### Golden labeled set

`eval_golden.yaml` is a smaller hand-labeled set with explicit routing and quality gates (`require_routing`, `require_entity_recall`, `min_faithfulness`, …). Case-by-case catalog: **[GOLDEN_EVAL.md](GOLDEN_EVAL.md)**.

The full integration suite runs golden **first**, then API smoke, then the chat bank. Golden-only (still runs smoke after golden; skips the full bank):

```bash
PYTHONPATH=. python -m regression.runner --eval-golden --report golden-eval.json
```

Cases fail when **both** answer expectations and explicit quality gates fail. The full `questions.yaml` bank still uses flexible keyword assertions; quality metrics are reported for all cases without changing pass/fail unless you add quality fields under `expect:`.

Example quality overrides on any case:

```yaml
expect:
  require_routing: true
  routing_path: neo4j_direct
  cypher_class: deterministic
  require_entity_recall: true
  min_faithfulness: 0.15
  source_channels_any: [vector]
```

### Offline unit tests

```bash
cd ssi-chat
pytest tests/test_eval_metrics.py -v
```

No live stack required — validates metric math and golden YAML schema.

## Files

| File | Purpose |
|------|---------|
| `questions.yaml` | Question bank + seed plan + per-case expectations |
| `runner.py` | CLI entry point (chat + API smoke) |
| `api_smoke.py` | Cross-service API smoke checks |
| `auth_helpers.py` | Shared admin/compliance login headers |
| `seed.py` | Harness actions, ETL wait, context placeholders (`approved_payment_id`, `draft_payment_id`, …) |
| `assertions.py` | Expectation evaluation (incl. skill confirmation / confirm step) |
| `eval_metrics.py` | Routing accuracy, recall, precision@k, faithfulness proxies |
| `eval_golden.yaml` | Labeled golden eval set with strict quality gates |
| `GOLDEN_EVAL.md` | Human-readable catalog of golden cases and gates |
| `models.py` | Pydantic schemas (`persona`, `confirm`, `retrieval: skill`) |

## Adding cases

```yaml
- id: my_new_case
  mode: events
  retrieval: graph   # deterministic | graph | vector | eligibility | skill
  tags: [who, approve]
  question: Who approved payment {approved_payment_id} and why?
  expect:
    requires_context: [approved_payment_id]
    min_answer_length: 30
    answer_contains_any: ["allowed", "because", "role"]
```

Skill cases (Payments mode) also take `persona` and optional `confirm`:

```yaml
- id: skill_cancel_payment_phase1_nogo
  mode: payments
  retrieval: skill
  persona: pay-101
  question: Please cancel payment {draft_payment_id}.
  confirm:
    decision: no_go
    intent_id: skill.cancel_payment.no_go
  expect:
    require_skill_confirmation: true
    skill_name: cancel_payment
    intent_id: skill.cancel_payment.awaiting_confirmation
```

Negative skill cases assert the denial path and that no confirmation card is issued:

```yaml
expect:
  forbid_skill_confirmation: true
  intent_id: skill.cancel_payment.forbidden
  answer_contains_all:
    - cannot run the cancel-payment skill
    - needs `PAYMENT_CREATOR` and `MIDDLE_OFFICE`
```

Context placeholders for non-skill cases are filled from instruction-service /
payment UI APIs after the suite seed. **Skill cases** are independent: the runner
calls harness `setup-skill-fixture` (create approved instruction → optional draft
or submitted payment) before the case and `teardown-skill-fixture` (cancel
payment + suspend instruction) afterward.

## Exit codes

- `0` — all non-skipped cases passed
- `1` — one or more failures

Skipped cases (missing context when data not seeded) do not fail the run.
