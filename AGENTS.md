# Agent instructions

Guidance for AI agents working in this repository.

## Before commit and push

**Always run lint locally** and fix all reported issues before committing or pushing. CI runs the same checks on every push to `main` and will fail on lint errors.

### Lint all Python services

From the repository root:

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

It also builds Docker images for those four services.

### Common lint failures

| Rule | Meaning | Fix |
|------|---------|-----|
| `I001` | Import block unsorted | Run `ruff check … --fix` |
| `F401` | Unused import | Remove the import |
| `E741` | Ambiguous variable name (`l`, `O`, `I`) | Rename to a descriptive name |
| `E501` | Line too long | Ignored in CI; prefer wrapping anyway |

### Workflow checklist

1. Make code changes.
2. Run `ruff check` on every touched Python service (see command above).
3. Fix or auto-fix all errors — do not push with lint failures.
4. Commit only when the working tree passes lint for affected services.
5. Push; confirm the GitHub Actions **Build** workflow succeeds.

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
