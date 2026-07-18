# Policy Pilot — Critical Architecture Review

**Date:** 2026-07-18  
**Reviewer model:** Claude Opus (adversarial / critical architecture pass)  
**Scope:** Identity → OPA → domain writes → CDC/indexer → Neo4j → chat skills → observability / trust boundaries  
**Method:** Code- and policy-grounded review (`docker-compose`, `authorization-service`, Rego packs, domain services, Kafka Connect, `ssi-indexer` DLQ, `ssi-chat` skills/retrieve). No files modified during the review.

---

## Executive summary

Policy Pilot is an event-driven, policy-aware knowledge platform for the cash leg of Standard Settlement Instructions. Domain services enforce OPA policy and write versioned state **and** an immutable security event to MongoDB in a single transaction; CDC streams inserts through Kafka into `ssi-indexer`, which builds a shared Neo4j graph plus a dense vector index; `ssi-chat` answers questions via Route → Retrieve → Synthesize and runs scripted mutation skills.

**Strongest parts:** a single OPA gateway (`authorization-service`) on every mutation and live-policy path; a clean identity↔policy bridge where OPA evaluates only injected `input` and **never** contacts ZITADEL; fail-closed OBO (token-derived subject only); atomic co-persistence of state + audit; layered SoD / four-eyes / reporting-line / LOB / amount-club Rego; mature ETL resilience (DLQ-before-commit, pause-on-quarantine-failure, integrity banner).

**Weakest residual risk:** chat graph/vector retrieval is not LOB/row-scoped, so an operational single-LOB user can read cross-LOB data through natural-language questions (P2; likely intentional for the demo, a real production gap).

**No P0 or P1 issues found.**

---

## Overall score

### 8.5 / 10

The security-critical spine — one policy engine, fail-closed OBO, atomic state+audit, resilient indexing — is designed correctly and defensively, with defense-in-depth (chat preflight **and** independent service-side OPA). Points are deducted primarily for missing read-side row/LOB authorization in chat retrieval, plus two production-hardening items (OIDC audience validation off; over-broad Neo4j boosted-procedure grant). Unauthenticated OPA behind authz, local ZITADEL, and demo credentials are treated as **intentional demo posture**, not defects.

---

## Strengths (evidence-backed)

| Strength | Evidence |
|----------|----------|
| Single OPA gateway; OPA never calls ZITADEL | `authorization-service` → OPA Data API; Rego packs have no `http.send` |
| Fail-closed OBO with identity binding | `resolve_evaluate_subject` requires service caller + `X-On-Behalf-Of`; inline subject can only match, never substitute |
| Atomic state + audit in one store | Domain services write version + security event in one Mongo transaction; CDC is insert-only |
| Layered, realistic SoD controls | Four-eyes, reporting-line inversion, LOB coverage, amount clubs + ceiling, instruction seniority matrix |
| ETL resilience is real | DLQ-before-commit, pause when quarantine unavailable, replay, chat integrity banner |
| Least-privilege Neo4j accounts | `svc_chat` MATCH-only; `svc_indexer` write; admin separate |
| Defense-in-depth in skills | OPA preflight + Go/No Go + payment-service re-authorizes via OPA/OBO |

---

## Findings

| ID | Severity | Area | Finding | Suggested fix / question |
|----|----------|------|---------|--------------------------|
| F-1 | **P2** (+Question) | Chat data plane | Graph/vector retrieval is **not scoped** by caller identity or LOB. Operational users can read cross-LOB data via NL questions. | Intentional for compliance demo? If not, inject LOB/role into Cypher plans and vector filters. |
| F-2 | **P2** (+Question) | Identity / JWT | OIDC **audience not validated** (`verify_aud=False` when unset). | Set and enforce `oidc_audience` before non-demo deployment. **Fixed 2026-07-18:** compose sets `OIDC_AUDIENCE=policy-pilot`; JWT path fail-closes on `InvalidAudienceError` (issue #64). Session login unaffected. |
| F-3 | **P2** | Neo4j | `svc_chat` has `EXECUTE BOOSTED PROCEDURE *` — latent privilege beyond read-only graph grants. | Restrict to the specific procedures chat needs. **Fixed 2026-07-18:** `role_ssi_chat` now grants only `EXECUTE PROCEDURE db.index.vector.queryNodes` (see #65). |
| F-4 | Question | Audit labeling | `SELF_APPROVAL` is not `ALERT_`-prefixed, so `is_alert` may disagree with stored severity. | Confirm intent for four-eyes denials. |
| F-5 | Question | Instruction policy | Instruction `SUBMIT` checks role/group/transition but not same-LOB / creator identity. | Is cross-LOB submit intended? |
| F-6 | Question | Skills | Confirm-phase OPA re-check fails open on transport error; payment-service remains authoritative. | Formalize “client recheck advisory / service authoritative”; optional skipped-recheck audit signal. |

---

## Trust-boundary map

```
User JWT  →  ssi-chat / Classic UI
                │
                ├─(service token + X-On-Behalf-Of)─→  authorization-service
                │                                         │
                │                                         ├─→ ZITADEL (JWKS, userinfo, metadata)
                │                                         └─→ OPA (pure input eval; no IdP calls)
                │
                └─(skill mutations)─→ payment-service / instruction-service
                                          │
                                          └─→ Mongo (version + security event, one txn)
                                                │
                                                └─ CDC → Kafka → ssi-indexer → Neo4j + vectors
```

- **OPA does not talk to ZITADEL.** Authz is the sole identity↔policy bridge.
- **Unauthenticated by design (demo):** OPA (network-reachable only from authz in production), some health/integrity endpoints.
- **Service-account only:** OPA evaluate, eligible-approvers discovery, DLQ admin.
- **User JWT required:** chat questions and domain mutations (via OBO).

---

## Residual risks / demo vs production

| Item | Label |
|------|-------|
| Chat read-side not LOB-scoped (F-1) | Real gap for operational personas in production |
| Audience validation off (F-2) | Hardening before multi-client deploy |
| Unauthenticated OPA, local ZITADEL, demo passwords, PLAINTEXT Kafka | Intentional demo posture |
| Cross-service submit → mark_used is compensating saga, not 2PC | Correct for single-store design |
| Boosted-procedure grant (F-3) | Latent; mitigated by parameterized planned Cypher today |

---

## What would raise the score

1. Add read-side authorization to chat retrieval (or document unfiltered read as compliance-only and restrict operational personas).
2. Enable OIDC audience validation with per-service expected audiences.
3. Tighten `svc_chat` Neo4j grants to specific procedures/functions.
4. Resolve `is_alert` labeling for four-eyes denials.
5. Confirm SUBMIT LOB scoping and formalize the advisory-vs-authoritative skill recheck contract.

---

## Score history

| Date | Model | Score | Notes |
|------|-------|-------|-------|
| Prior | Claude Opus + GPT peer (owner-corrected) | ~8.0 / 10 | GPT over-flagged intentional design; owner-aligned to Opus |
| **2026-07-18** | **Claude Opus** | **8.5 / 10** | Fresh pass on current `main`; 0 P0 / 0 P1; residual P2s above |
