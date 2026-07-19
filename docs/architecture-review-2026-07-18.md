# Policy Pilot — Critical Architecture Review

**Date:** 2026-07-18 (evening re-pass)  
**Reviewer model:** Claude Opus (adversarial / critical architecture pass)  
**HEAD:** `main` @ `4f6fc91` (post PR #75 — chat vector LOB scope)  
**Scope:** Identity → OPA → domain writes → CDC/indexer → Neo4j → chat skills → observability / trust boundaries  
**Method:** Code- and policy-grounded review. Prior F-1…F-6 re-validated against current code. No files modified during the review.

---

## Executive summary

Policy Pilot is an event-driven, policy-aware knowledge platform for the cash leg of Standard Settlement Instructions. Domain services enforce OPA policy and write versioned state **and** an immutable security event to MongoDB in a single transaction; CDC streams inserts through Kafka into `ssi-indexer`, which builds a shared Neo4j graph plus a dense vector index; `ssi-chat` answers questions via Route → Retrieve → Synthesize and runs scripted mutation skills.

**Strongest parts:** a single OPA gateway (`authorization-service`) on every mutation and live-policy path; a clean identity↔policy bridge where OPA evaluates only injected `input` and **never** contacts ZITADEL; fail-closed OBO (token-derived subject only); atomic co-persistence of state + audit; layered SoD / four-eyes / reporting-line / LOB / amount-club Rego; mature ETL resilience (DLQ-before-commit, pause-on-quarantine-failure, integrity banner); **chat graph + vector + REST VIEW LOB scoping** for operational personas (issue #63 2a/2b/2c).

**Weakest residual risk (updated):** parked **by-id** chat lookups (approval / versions / timeline) that neither inject `owning_lob_and_clause` nor `RETURN … AS owning_lob`, so the graph post-filter cannot drop cross-LOB rows on id paste (F-1b). Detail-by-id and vector paths are already scoped. Tracked on `park/issue-63-2d-hardening`.

**No P0 or P1 issues found.**

---

## Overall score

### 9.0 / 10 *(proposed — pending owner confirmation)*

Up from 8.5 because F-1 graph/vector/REST read-side authorization, F-2 audience, F-3 Neo4j grants, and F-6 skill confirm fail-closed are verified closed; F-4 resolved as by-design. Held below ~9.5 by F-1b (parked 2d) and open F-5 SUBMIT LOB design question. Demo posture is not scored as defects.

---

## Strengths (evidence-backed)

| Strength | Evidence |
|----------|----------|
| Single OPA gateway; OPA never calls ZITADEL | `authorization-service` → OPA Data API; Rego packs have no `http.send` |
| Fail-closed OBO with identity binding | `resolve_evaluate_subject` requires service caller + `X-On-Behalf-Of`; inline subject can only match, never substitute |
| Atomic state + audit in one store | Domain services write version + security event in one Mongo transaction; CDC is insert-only |
| Layered, realistic SoD controls | Four-eyes, reporting-line inversion, LOB coverage, amount clubs + ceiling, instruction seniority matrix |
| Chat + REST LOB scope | `allowed_retrieval_lobs` + `owning_lob_and_clause` + vector `IN $allowed_lobs` + OPA `VIEW` |
| ETL resilience is real | DLQ-before-commit, pause when quarantine unavailable, replay, chat integrity banner |
| Least-privilege Neo4j accounts | `svc_chat` MATCH-only + `db.index.vector.queryNodes`; `svc_indexer` write; admin separate |
| Defense-in-depth in skills | OPA preflight + Go/No Go + confirm fail-closed; payment-service re-authorizes via OPA/OBO |

---

## Findings

| ID | Severity | Area | Finding | Suggested fix / question |
|----|----------|------|---------|--------------------------|
| F-1a | **Closed** | Chat / REST data plane | Graph, vector, and REST `VIEW` paths are LOB-scoped by caller identity (#63 2a/2b/2c, #75). | — |
| F-1b | **P2** (parked) | Chat by-id | Approval / versions / timeline / approver-via-payment templates lack LOB `WHERE` and `owning_lob` RETURN; post-filter keeps null-LOB rows → id-paste cross-LOB metadata. | Land `park/issue-63-2d-hardening`, and/or fail-closed post-filter when scoped subject + missing `owning_lob`. |
| F-2 | **Closed** | Identity / JWT | Compose sets `OIDC_AUDIENCE=policy-pilot`; JWT path fail-closes on audience mismatch. Opaque/userinfo fallback remains demo-shaped. | — |
| F-3 | **Closed** | Neo4j | `role_ssi_chat` grants only `EXECUTE PROCEDURE db.index.vector.queryNodes`. | — |
| F-4 | **Closed (by design)** | Audit labeling | Denials → `severity=ALERT`; `is_alert` only for `ALERT_`-prefixed codes. `SELF_APPROVAL` → ALERT severity, `is_alert=false`. | Document convention; do not re-raise as defect. |
| F-5 | Question | Instruction policy | Instruction `SUBMIT` checks role/group/transition but not same-LOB / covering. | Confirm intent; add gate if needed. |
| F-6 | **Closed** | Skills | Confirm-phase OPA recheck fails closed on transport error; payment-service remains authoritative. | — |

---

## Trust-boundary map

```
User JWT  →  ssi-chat / Classic UI
                │
                ├─(allowed_retrieval_lobs)─→ Neo4j graph/vector  [LOB scoped; F-1b by-id residual]
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
| By-id chat LOB gap (F-1b) | Real gap — parked on `park/issue-63-2d-hardening` |
| Graph post-filter fail-open on missing `owning_lob` | Real gap (enables F-1b); vector path is fail-closed |
| Instruction SUBMIT not LOB-scoped (F-5) | Design question |
| Opaque token userinfo skips audience | Demo / minor |
| Unauthenticated OPA, local ZITADEL, demo passwords, PLAINTEXT Kafka | Intentional demo posture |
| Cross-service submit → mark_used is compensating saga, not 2PC | Correct for single-store design |

---

## What would raise the score

1. Land parked 2d: inject `owning_lob_and_clause` + `RETURN … AS owning_lob` on F-1b by-id templates.
2. Make `filter_rows_by_retrieval_lobs` fail-closed for scoped subjects when a detail row lacks `owning_lob`.
3. Resolve F-5 SUBMIT LOB/covering policy.
4. Optionally enforce audience on opaque/userinfo fallback for non-demo deploys.
5. Add FO cross-LOB id-paste golden negatives (approval / versions / timeline).

---

## Score history

| Date | Model | Score | Notes |
|------|-------|-------|-------|
| Prior | Claude Opus + GPT peer (owner-corrected) | ~8.0 / 10 | GPT over-flagged intentional design; owner-aligned to Opus |
| 2026-07-18 (morning) | Claude Opus | **8.5 / 10** | F-1 open (chat read-side); F-2/F-3 open then later fixed |
| **2026-07-18 (evening)** | **Claude Opus** | **9.0 / 10 (proposed)** | Post #75; F-1a/F-2/F-3/F-6 closed; residual F-1b parked; F-5 question |
