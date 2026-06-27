# Agent instructions

Guidance for AI agents working in this repository.

## Before commit and push

**Always run lint locally** and fix all reported issues before committing or pushing. CI runs the same checks on every push to `main` and will fail on lint errors.

### One command (required before every commit/push)

From the repository root — run **check and auto-fix**, then verify clean:

```bash
pip install ruff

for svc in \
  instruction-lifecycle-manager \
  security-event-chat \
  security-event-qdrant-etl \
  security-event-test-harness \
  payment-service
do
  ruff check "$svc/src/" --select E,F,W,I --ignore E501 --fix
done

# Must exit 0 on all services — re-run without --fix to confirm:
for svc in \
  instruction-lifecycle-manager \
  security-event-chat \
  security-event-qdrant-etl \
  security-event-test-harness \
  payment-service
do
  echo "=== $svc ==="
  ruff check "$svc/src/" --select E,F,W,I --ignore E501
done
```

Do **not** commit or push if any service still reports errors.

### Lint all Python services (check only)

```bash
pip install ruff

for svc in \
  instruction-lifecycle-manager \
  security-event-chat \
  security-event-qdrant-etl \
  security-event-test-harness \
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

- `instruction-lifecycle-manager`
- `security-event-chat`
- `security-event-qdrant-etl`
- `security-event-test-harness`

It also builds Docker images for those four services. (`payment-service` is not in the CI lint matrix yet, but keep it clean anyway.)

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
| `from ilm.config` then `from ilm.authorization` | `ilm.authorization` **before** `ilm.config` |
| `from ilm.models.enums` then `from ilm.models.api` | `ilm.models.api` **before** `ilm.models.enums` |
| `from ilm.models.instruction_fact` then `from ilm.models.instruction` | `ilm.models.instruction` **before** `ilm.models.instruction_fact` |
| `from ps.models.api` then `from ps.authorization` | `ps.authorization` **before** `ps.models.*` |
| Long single-line `from ilm.authorization import a, b, c` breaking sort | Multi-line import block (ruff `--fix` formats this) |

When adding new modules under `ilm/`, `etl/`, or `ps/`, **always run `ruff check … --fix`** on that service — do not hand-order imports unless you mirror the rules above.

When removing a symbol from code, **remove its import** in the same edit (`F401`).

### Workflow checklist

1. Make code changes.
2. Run the **required** lint loop (`--fix` then verify) on every touched Python service.
3. Fix any remaining errors manually — do not push with lint failures.
4. Commit only when the user asks; if committing, ensure all five services pass lint.
5. After push, confirm the GitHub Actions **Build** workflow succeeds.

## Project layout

| Directory | Python package | Port |
|-----------|----------------|------|
| `instruction-lifecycle-manager` | `ilm` | 8000 |
| `payment-service` | `ps` | 8093 |
| `security-event-qdrant-etl` | `etl` | 8090 |
| `security-event-chat` | `chat_application` | 8092 |
| `security-event-test-harness` | `harness` | 8091 |

See the root [README.md](README.md) for architecture, storage names, and demo URLs.

## Conventions

- Match existing code style in each service (imports, naming, FastAPI patterns).
- Keep changes focused; avoid unrelated refactors.
- Do not commit secrets (`.env`, PAT files, credentials).
- Only create git commits when the user explicitly asks.
