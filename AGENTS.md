# Agent instructions

Guidance for AI agents working in this repository.

## Before commit and push

**Always run lint locally** and fix all reported issues before committing or pushing. CI runs the same checks on every push to `main` and will fail on lint errors.

### One command (required before every commit/push)

From the repository root — run **check and auto-fix**, then verify clean:

```bash
pip install ruff

for svc in \
  instruction-service \
  authorization-service \
  sequence-service \
  ssi-chat \
  ssi-indexer \
  ssi-demo-harness \
  payment-service
do
  ruff check "$svc/src/" --select E,F,W,I --ignore E501 --fix
done

# Must exit 0 on all services — re-run without --fix to confirm:
for svc in \
  instruction-service \
  authorization-service \
  sequence-service \
  ssi-chat \
  ssi-indexer \
  ssi-demo-harness \
  payment-service
do
  echo "=== $svc ==="
  ruff check "$svc/src/" --select E,F,W,I --ignore E501
done
```

Do **not** commit or push if any service still reports errors.

### Test coverage (minimum 80%)

Every Python service **except** `ssi-demo-harness` must maintain **≥ 80% line coverage** on its application package. The harness is integration/demo tooling and is exempt. Package `[tool.coverage.report] fail_under` must be **80** (not lower) so local `pytest --cov` matches CI.

| Target | Coverage package (`--cov`) |
|--------|----------------------------|
| `instruction-service` | `inst` |
| `payment-service` | `ps` |
| `authorization-service` | `authz` |
| `sequence-service` | `seq` |
| `ssi-indexer` | `etl` |
| `ssi-chat` | `chat_application` |
| `shared/telemetry` | `telemetry` |
| `shared/platform_auth` | `platform_auth` |
| `shared/sequence_client` | `sequence_client` |
| `shared/authz_client` | `authz_client` |
| `shared/cypher_builder` | `cypher_builder` |
| `shared/vertex_client` | `vertex_client` |
| `shared/zitadel_directory` | `zitadel_directory` |

When you add or change code in a service or shared package, **add or update tests** so coverage stays at or above 80%. Do not commit or push if coverage on a touched target falls below the threshold.

#### One command (required before every commit/push)

From the repository root — run tests with coverage for each gated package:

```bash
pip install pytest pytest-cov

for spec in \
  "instruction-service:inst" \
  "payment-service:ps" \
  "authorization-service:authz" \
  "sequence-service:seq" \
  "ssi-indexer:etl" \
  "ssi-chat:chat_application" \
  "shared/telemetry:telemetry" \
  "shared/platform_auth:platform_auth" \
  "shared/sequence_client:sequence_client" \
  "shared/authz_client:authz_client" \
  "shared/cypher_builder:cypher_builder" \
  "shared/vertex_client:vertex_client" \
  "shared/zitadel_directory:zitadel_directory"
do
  svc="${spec%%:*}"
  pkg="${spec##*:}"
  echo "=== $svc (≥80% on $pkg) ==="
  (
    cd "$svc"
    pip install -q -e .
    pip install -q pytest pytest-cov
    pytest --cov="$pkg" --cov-report=term-missing --cov-fail-under=80
  )
done
```

If a package has no `tests/` directory yet, create one and add tests for the code you touched — do not skip the coverage check.

Optional chat regression suite (does not replace the 80% unit-coverage requirement). Harness seed from `questions.yaml` runs by default (`CHAT_REGRESSION_SEED=0` to skip):

```bash
cd ssi-chat
pip install -e ".[regression]"
RUN_CHAT_REGRESSION=1 pytest tests/test_chat_regression.py -v
```

### Lint all Python services (check only)

```bash
pip install ruff

for svc in \
  instruction-service \
  authorization-service \
  sequence-service \
  ssi-chat \
  ssi-indexer \
  ssi-demo-harness \
  payment-service
do
  echo "=== $svc ==="
  ruff check "$svc/src/" --select E,F,W,I --ignore E501
done
```

Auto-fix import sorting and other safe fixes:

```bash
ruff check <service>/src/ --select E,F,W,I --ignore E501 --fix
```

### What CI checks

The [Build workflow](.github/workflows/build.yml) runs:

```bash
ruff check src/ --select E,F,W,I --ignore E501
```

inside each service directory listed in the lint matrix:

- `instruction-service`
- `authorization-service`
- `sequence-service`
- `ssi-chat`
- `ssi-indexer`
- `ssi-demo-harness`

It also builds Docker images for the application services. Keep `payment-service` lint-clean even though it is not in the Docker build matrix yet.

The same workflow runs **unit test coverage** (≥ 80% line coverage) for:

- `instruction-service` (`inst`)
- `payment-service` (`ps`)
- `authorization-service` (`authz`)
- `sequence-service` (`seq`)
- `ssi-indexer` (`etl`)
- `ssi-chat` (`chat_application`)
- `shared/telemetry` (`telemetry`)
- `shared/platform_auth` (`platform_auth`)
- `shared/sequence_client` (`sequence_client`)
- `shared/authz_client` (`authz_client`)
- `shared/cypher_builder` (`cypher_builder`)
- `shared/vertex_client` (`vertex_client`)
- `shared/zitadel_directory` (`zitadel_directory`)

`ssi-demo-harness` is exempt from the coverage gate.

### Common lint failures

| Rule | Meaning | Fix |
|------|---------|-----|
| `I001` | Import block unsorted | Run `ruff check … --fix` — see import rules below |
| `F401` | Unused import | Remove the import (often left after a refactor) |
| `E741` | Ambiguous variable name (`l`, `O`, `I`) | Rename to a descriptive name |
| `E501` | Line too long | Ignored in CI; prefer wrapping anyway |

### Import order rules (prevents recurring `I001`)

Ruff/isort expects this order in every Python file:

1. `from __future__ import annotations` (if present)
2. Standard library (`datetime`, `logging`, `typing`, …)
3. Third party (`fastapi`, `pydantic`, `neo4j`, …)
4. First-party package imports — **alphabetically by full module path**

Within each service, first-party imports must be sorted by module name. Examples:

| Wrong | Correct |
|-------|---------|
| `from inst.config` then `from inst.authorization` | `inst.authorization` **before** `inst.config` |
| `from inst.models.enums` then `from inst.models.api` | `inst.models.api` **before** `inst.models.enums` |
| `from inst.models.instruction_fact` then `from inst.models.instruction` | `inst.models.instruction` **before** `inst.models.instruction_fact` |
| `from ps.models.api` then `from ps.authorization` | `ps.authorization` **before** `ps.models.*` |
| Long single-line `from inst.authorization import a, b, c` breaking sort | Multi-line import block (ruff `--fix` formats this) |

When adding new modules under `inst/`, `etl/`, or `ps/`, **always run `ruff check … --fix`** on that service — do not hand-order imports unless you mirror the rules above.

When removing a symbol from code, **remove its import** in the same edit (`F401`).

### Workflow checklist

1. Make code changes.
2. Run the **required** lint loop (`--fix` then verify) on every touched Python service.
3. Run the **required** coverage loop (≥ 80%) on every touched non-harness service; add tests when needed.
4. Fix any remaining errors manually — do not push with lint failures or sub-threshold coverage.
5. Commit only when the user asks; if committing, ensure all touched Python services pass lint and all non-harness application services meet coverage.
6. After push, confirm the GitHub Actions **Build** workflow succeeds (lint, coverage, and Docker build jobs).

## Project layout

| Directory | Python package | Port |
|-----------|----------------|------|
| `instruction-service` | `inst` | 8000 |
| `payment-service` | `ps` | 8093 |
| `authorization-service` | `authz` | 8094 |
| `sequence-service` | `seq` | 8095 |
| `ssi-indexer` | `etl` | 8090 |
| `ssi-chat` | `chat_application` | 8092 |
| `ssi-demo-harness` | `harness` | 8091 |

See the root [README.md](README.md) for architecture, storage names, and demo URLs.

## Conventions

- Match existing code style in each service (imports, naming, FastAPI patterns).
- Keep changes focused; avoid unrelated refactors.
- Maintain **≥ 80% test coverage** on application packages (`inst`, `ps`, `authz`, `seq`, `etl`, `chat_application`) and all `shared/*` packages listed above; `ssi-demo-harness` is exempt.
- **ssi-chat intent thumb rule:** determine natural-language intent with Gemini structured output / LLM semantic routing (`RouterDecision.path`) — not regex or fuzzy classification. Regex is OK for slot parsing (ids, amounts) and LLM-failure fallback only. Details: [docs/intent-determination.md](docs/intent-determination.md) and `.cursor/rules/intent-semantic-routing.mdc`.
- Do not commit secrets (`.env`, PAT files, credentials).
- Only create git commits when the user explicitly asks.
