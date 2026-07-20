# ssi-chat-j eval fixtures

YAML golden cases owned by **ssi-chat-j**. They are HTTP black-box checks against
`http://localhost:8096` — not loaded by the Java process at runtime.

| File | Cases |
|------|--------|
| [`eligibility_golden.yaml`](eligibility_golden.yaml) | Payment APPROVE, payment SUBMIT, instruction APPROVE |

## Prove (warm Compose stack)

From repo root:

```bash
./ssi-chat-j/scripts/prove-eligibility.sh
```

Uses the temporary Python regression CLI as an HTTP client only (`--golden` points
at this directory). Java chat does not import `ssi-chat` application code.

## Later

Port asserts to JUnit + Java HttpClient under `ssi-chat-j` when retiring the Python
chat service; keep these YAML files as the case source of truth.
