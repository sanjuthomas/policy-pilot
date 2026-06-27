# Chat regression suite

YAML-driven regression tests for **Security Events**, **Instructions**, and **Payments** chat modes.

Each case posts a question to `POST /api/chat` and checks the response with flexible assertions (keywords, numeric answers, minimum sources/graph rows). LLM answers are not compared verbatim — expectations use `answer_contains_any`, `answer_has_number`, etc.

## Prerequisites

- Full stack running (`docker compose up -d`)
- Host **Ollama** with `bge-m3:latest` and `qwen3:30b` (or models configured in chat env)
- Harness reachable at http://localhost:8091 (for `--seed`)

## Quick run

From repo root (stack already has data):

```bash
cd security-event-chat
pip install -e ".[regression]"
PYTHONPATH=. python -m regression.runner
```

Seed data, wait for ETL, then run all cases:

```bash
PYTHONPATH=. python -m regression.runner --seed --report regression-report.json
```

If testing **Who/When/Why approval audit** on data from an older stack, run authorization backfill first:

```bash
curl -X POST http://localhost:8091/api/actions/repair-authorization
```

After install:

```bash
security-event-chat-regression --seed
```

## Filters

```bash
# Security Events mode only
python -m regression.runner --mode events

# Tag filter (counts, compliance, who, why, when, …)
python -m regression.runner --tags counts,alerts

# Single case
python -m regression.runner --ids events_who_approved_payment_why
```

## Pytest (CI / optional)

Integration tests are skipped unless explicitly enabled:

```bash
cd security-event-chat
pip install -e ".[regression]"
RUN_CHAT_REGRESSION=1 pytest tests/test_chat_regression.py -v
```

Use `CHAT_REGRESSION_SEED=1` to run harness seed steps before the suite.

## Files

| File | Purpose |
|------|---------|
| `questions.yaml` | Question bank + seed plan + per-case expectations |
| `runner.py` | CLI entry point |
| `seed.py` | Harness actions, ETL wait, context `{approved_payment_id}` resolution |
| `assertions.py` | Expectation evaluation |
| `models.py` | Pydantic schemas |

## Adding cases

```yaml
- id: my_new_case
  mode: events
  tags: [who, approve]
  question: Who approved payment {approved_payment_id} and why?
  expect:
    requires_context: [approved_payment_id]
    min_answer_length: 30
    answer_contains_any: ["allowed", "because", "role"]
```

Context placeholders are filled from ILM/payment UI APIs after seeding.

## Exit codes

- `0` — all non-skipped cases passed
- `1` — one or more failures

Skipped cases (missing context when data not seeded) do not fail the run.
