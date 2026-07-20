# ssi-chat-j — living todo

Status tracker for the Java / Spring AI chat **A/B experiment**.  
Plan details: [`ssi-chat-j-plan.md`](ssi-chat-j-plan.md).

**Success bar:** golden eval green against `http://localhost:8096` (Python `ssi-chat` remains on `8092`).

Update this file as work moves. Use only: `todo` · `in_progress` · `done` · `blocked` · `deferred`.

---

## Legend

| Status | Meaning |
|--------|---------|
| `todo` | Not started |
| `in_progress` | Actively being worked |
| `done` | Complete for the experiment’s success bar |
| `blocked` | Waiting on a decision or dependency |
| `deferred` | Out of scope until after golden green |

---

## Current focus

| Item | Status | Notes |
|------|--------|-------|
| Plan + todo docs | `done` | This file + `ssi-chat-j-plan.md` |
| **M1** — compose + health + login + eligibility golden | `done` | Three eligibility goldens via `prove-eligibility.sh` |
| Phase 2 cypher bridge | `todo` | Next for neo4j_direct goldens |

---

## Milestone M1 (shipped)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| M1.1 | `ssi-chat-j` in Compose on **8096** | `done` | Python chat stays **8092** |
| M1.2 | `GET /health` | `done` | |
| M1.3 | `POST /api/auth/login` (ZITADEL session) | `done` | Parity headers for golden |
| M1.4 | `POST /api/chat` + Spring AI `RouterDecision` | `done` | No heuristic failover — Spring AI only |
| M1.5 | Payment eligibility via OBO (`eligible-approvers`) | `done` | svc-chat + user session |
| M1.6 | Eligibility golden proof (3 cases) | `done` | `./ssi-chat-j/scripts/prove-eligibility.sh` |

---

## Phase 0 — Scaffold

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P0.1 | Create `ssi-chat-j/` Maven Spring Boot 3 / Java 21 module | `done` | |
| P0.2 | Dockerfile + compose service `ssi-chat-j` on **8096** | `done` | Do not take over `ssi-chat` / 8092 |
| P0.3 | `GET /health` | `done` | |
| P0.4 | Thymeleaf hello page | `done` | Minimal landing |
| P0.5 | Maven copy of static assets from `ssi-chat/.../static` | `done` | Build-time assembly |
| P0.6 | README for `ssi-chat-j` (how to run A/B) | `done` | |

---

## Phase 1 — Auth + chat stub + AI spike

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P1.1 | Spike: Spring AI ↔ Vertex Gemini (embed + generate) | `done` | Chat routing works live |
| P1.2 | Spike: structured `RouterDecision`-like JSON | `done` | `.entity(RouterDecision.class)` |
| P1.3 | ZITADEL JWT validation / login parity (enough for golden) | `done` | Session token + `X-Session-Id` |
| P1.4 | Subject + capabilities model | `done` | Roles from ZITADEL metadata |
| P1.5 | `POST /api/chat` stub (fixed or echo answer) | `done` | Superseded by eligibility |
| P1.6 | Service identity + OBO `WebClient` skeleton | `done` | RestTemplate OBO |

---

## Phase 2 — Cypher bridge

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P2.1 | Create `cypher-builder-svc` (FastAPI) wrapping `shared/cypher_builder` | `todo` | See plan: HTTP JSON protocol |
| P2.2 | `POST /v1/plan` + `POST /v1/validate` + `/health` | `todo` | |
| P2.3 | Compose wire-up (port **8097**) | `todo` | |
| P2.4 | Java `CypherBuilderClient` (WebClient) | `todo` | |
| P2.5 | Neo4j read execution as `svc_chat` | `todo` | |
| P2.6 | One end-to-end neo4j_direct golden case via bridge | `todo` | Proves protocol |

---

## Phase 3 — Golden path: tools + graph

Implement only what golden cases require; mark each golden id when green.

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P3.1 | Pipeline: route → handler lanes (path is law) | `in_progress` | Eligibility lane only |
| P3.2 | Eligibility / policy tools as needed by golden | `done` | Payment APPROVE/SUBMIT + instruction APPROVE |
| P3.3 | Me / who-am-i if in golden | `todo` | |
| P3.4 | neo4j_direct + formatters for golden graph cases | `todo` | Via cypher bridge |
| P3.5 | Vector / hybrid only if a golden case needs it | `todo` | |
| P3.6 | Skills only if a golden case needs them | `deferred` | Likely after golden |

### Golden case checklist

| Golden case id | Status | Notes |
|----------------|--------|-------|
| `golden_policies_eligible_approvers_payment` | `done` | `ssi-chat-j/eval/eligibility_golden.yaml` |
| `golden_policies_eligible_submitters_payment` | `done` | same |
| `golden_policies_eligible_approvers_instruction` | `done` | same |
| _(remaining from full `eval_golden.yaml`)_ | `todo` | |

---

## Phase 4 — Golden eval green

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P4.1 | Run seed + eligibility golden against `:8096` | `done` | `prove-eligibility.sh` / warm `--no-seed` |
| P4.2 | Triage failures into Phase 3 backlog | `todo` | |
| P4.3 | Document A/B how-to (switch `CHAT_BASE_URL`) | `done` | `ssi-chat-j/README.md` + `eval/README.md` |
| P4.4 | **Success bar met** | `todo` | Full golden suite still open |

---

## Deferred (after golden)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| D.1 | Full `questions.yaml` bank | `deferred` | |
| D.2 | Payment skills parity | `deferred` | |
| D.3 | Replace Python chat | `deferred` | Explicitly **out of scope** for this experiment |
| D.4 | Native Java `cypher_builder` port | `deferred` | Only if HTTP bridge fails scale/latency |

---

## Decisions log

| Date | Decision |
|------|----------|
| 2026-07-20 | Name `ssi-chat-j`; A/B only; Maven; reuse cypher_builder via HTTP sidecar; Thymeleaf + build-time static copy; success = golden green; track in this file |
| 2026-07-20 | **M1 done:** health + login + Spring AI `RouterDecision` + payment eligibility OBO; proven by `golden_policies_eligible_approvers_payment` |
| 2026-07-20 | Eligibility trio owned under `ssi-chat-j/eval/`; `prove-eligibility.sh` HTTP black-box vs `:8096` |
