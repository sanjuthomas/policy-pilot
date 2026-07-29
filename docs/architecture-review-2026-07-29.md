# Policy Pilot — Critical Architecture Review

**Date:** 2026-07-29 (evening re-pass, post PR #125)  
**Reviewer model:** Claude Opus 5 (adversarial / critical architecture pass)  
**HEAD:** `main` @ `fedbb45` (merge of #125 — N-3 / N-4 / N-5)  
**Scope:** Chat LOB retrieval (`ssi-chat-j` neo4j_direct), SoD Cypher, indexer ProfitCenter identity, residual P2 queue  
**Method:** Code-grounded re-validation of prior findings. No application code modified during the review. Score is **proposed** until owner confirmation.

Companion canvases (local IDE only): `architecture-review-opus-2026-07-29.canvas.tsx` (AM), `architecture-review-opus-2026-07-29-pm.canvas.tsx` (this pass), `architecture-p2-triage-2026-07-29.canvas.tsx`.

---

## Executive summary

PR #125 closes the three open LOB/graph findings from the mid-week reviews: alert aggregates no longer zero for FO/MO (**N-4**), `duplicate_routes` scopes both conflict sides (**N-5**), and `ProfitCenter` merges on the schema-unique `lob` key (**N-3**). Cross-LOB SoD / timeline confidentiality (**N-1 / F-1b**) remains closed.

**No P0 or P1 issues found.** Residual risk is a P2 maintainability / eval queue plus design questions introduced or clarified by #125.

---

## Overall score

### 9.0 / 10 *(proposed — pending owner confirmation)*

Up from 8.8 (2026-07-29 AM, N-4 working-tree only) because N-3 / N-4 / N-5 are merged and test-backed on `main`. Held below ~9.5 by open P2s (N-9, N-7, A4, A2, A3) and unanswered questions (N-10, Q-1, Q-2, F-5). Demo posture is not scored as defects.

| Date | Model | Score | Notes |
|------|-------|-------|-------|
| 2026-07-26 | Claude Opus 5 | 8.4 prop. | F-1b escalated to P1 after Java cutover |
| 2026-07-27 | Claude Opus 5 | 8.6 prop. | N-1 closed; N-4 open |
| 2026-07-29 AM | Claude Opus 5 | 8.8 prop. | N-4 closed in WT; N-3/N-5 still open |
| 2026-07-29 PM | Claude Opus 5 | **9.0 prop.** | N-3/N-4/N-5 merged (#125); N-7→P2; N-10/Q-2 new |

---

## Closed by #125

| ID | Was | Now | Evidence |
|----|-----|-----|----------|
| N-4 | P1 (alert aggregates zeroed for FO/MO) | **Closed** | `Neo4jDirectService.isCypherScopedAggregate` skips post-filter for `count` / `ranking` / `alert_count_today`; empty-entitlement deny still runs first. Alert list/detail RETURN `owning_lob`. |
| N-5 | P2 (`duplicate_routes` scoped `v1` only) | **Closed** | `LobScope` on `v1` and `v2`; RETURN `v2.owning_lob AS lob_b`; fail-closed `containsAll` still applies. |
| N-3 | P2 (ProfitCenter `{lob}` vs `{name}`) | **Closed** | All indexer MERGEs use `{lob: …}` + `SET name`; agrees with `schema.cypher` unique constraint. |
| N-1 / F-1b | Closed (#124) | **Still closed** | SoD/timeline inject `LobScope` and return recognized LOB columns; none are aggregate-exempt. |

---

## Remaining findings

| ID | Severity | Status | Finding |
|----|----------|--------|---------|
| N-9 | **P2** | Open | Aggregate filter exemption keyed on free-form label string; `alert_count_today` has no Java producer (dead entry). |
| N-7 | **P2** | Elevated from Concern | FX instruction-denial golden flipped empty→positive; seed density is ordering-dependent. |
| A4 | **P2** | Open | Service identity session cached until blank; no downstream 401 invalidation/retry. |
| A2 | **P2** | Open | Unformatted planned labels fall through to `"Graph query returned N row(s)."`. |
| A3 | **P2** | Open | `selectQuery` is a hardcoded 15-branch label ladder. |
| N-10 | Question | **New** | Named-LOB `duplicate_routes` now requires **both** sides in scope — may hide cross-LOB conflicts from compliance. |
| Q-1 | Question | Open | Aggregates scope `e.owning_lob` only (under-count vs coalesce on detail shapes). |
| Q-2 | Question | **New** | Cypher scopes `e.owning_lob`; post-filter reads `pv`-first coalesce — mismatch is fail-closed but can silently under-disclose. |
| F-5 | Question | Open | Instruction `SUBMIT` is not LOB-gated (role/group/transition only). |

---

## Owner questions

1. **N-10:** For compliance asking “duplicate settlement routes for FICC,” should **both** sides be FICC, or **at least one**?
2. **Q-2:** If event vs payment-version LOB disagree, which key is authoritative?
3. **N-7:** Seed explicit FX instruction denials, or drop the FX positive golden and rely on FICC?

---

## What would raise the score further

1. Close **N-9** — `PlannedQuery.cypherScoped` (or equivalent) set by `LobScope` producers; delete dead `alert_count_today` exemption.
2. Answer **N-10** and encode with a golden that can fail on cross-LOB pairs.
3. Stabilize **N-7** (seed or drop FX positive).
4. Fold **A3** into the same `PlannedQuery` cleanup as N-9; **A2** explicit not-formatted signal.
5. Resolve **F-5 / Q-1 / Q-2** as a short design note or code.

---

## Caveats

- Review was read-only against `fedbb45`. Local `Neo4jDirectServiceTest` may hit Mockito `MockMaker` sandbox limits; Cypher planner tests and indexer coverage were green in the fix PR.
- Existing Neo4j volumes may still hold name-keyed orphan `ProfitCenter` nodes until rebuild / CDC replay; new writes are correct.
- Confirm this proposed **9.0** before treating it as the formal score in other docs.
