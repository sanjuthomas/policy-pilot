# ssi-chat-j eval fixtures

YAML golden cases owned by **ssi-chat-j**. They are HTTP black-box checks against
`http://localhost:8096` — not loaded by the Java process at runtime.

| File | Cases |
|------|------:|
| [`eligibility_golden.yaml`](eligibility_golden.yaml) | **98** |

## Bank by family

| Family | Approx. count | Examples |
|--------|--------------:|----------|
| Policy / eligibility / directory | 11 | `golden_policies_eligible_*`, amount-club directory, policy summaries |
| Me-centric | 18 | `golden_me_who_am_i_*`, can-act, waiting-for-me, who-covers-lob |
| Document extraction / show-by-id | 8 | instruction/payment show (ok / not-found / forbidden) |
| Neo4j events / denials / alerts | 12 | counts, lists, rankings, FO LOB scope |
| Entity / inventory / audit | ~25 | status, creator, list-by-status, who-approved, versions, timelines |
| SoD / vector / person | 7 | mutual/subordinate/duplicate, vector summary, person permissions |
| Payment skills | 17 | phase-1 No Go, forbidden, incomplete, wrong-status, amount/LOB gates |

Exact ids: see `eligibility_golden.yaml` (`- id:`).

## Prove (warm Compose stack)

From repo root (after `./scripts/clean-slate.sh --with-demo-seed` or an equivalent warm stack):

```bash
./ssi-chat-j/scripts/prove-eligibility.sh
```

The prove script uses a temporary HTTP client against `:8096`. The Python `ssi-chat` application is **retired** (local-only / gitignored archive) and is not part of Compose or CI.

## Later

Port asserts to JUnit + Java `HttpClient` under `ssi-chat-j` when convenient; keep these YAML files as the case source of truth.
