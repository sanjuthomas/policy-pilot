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
| **M1** — health + login + eligibility golden | `done` | Three eligibility goldens via `prove-eligibility.sh`; Maven on `:8096` (no root Compose) |
| Observability (Micrometer → OTLP) | `done` | Same chat SLI names as Python; no Prometheus scrape |
| Document extraction (API) | `done` | `path=document_extraction` → instruction/payment GET |
| Phase 2 cypher bridge | `done` | `cypher-builder-svc` :8097 + Java client + `golden_events_count_today` |

---

## Milestone M1 (shipped)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| M1.1 | `ssi-chat-j` listening on **8096** | `done` | Maven local; **not** in root Compose yet |
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
| P0.2 | Dockerfile (CI image) for `ssi-chat-j` | `done` | Root Compose wiring deferred — run via Maven |
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
| P2.1 | Create `cypher-builder-svc` (FastAPI) wrapping `shared/cypher_builder` | `done` | Port **8097** |
| P2.2 | `POST /v1/plan` + `POST /v1/validate` + `/health` | `done` | |
| P2.3 | Compose wire-up (port **8097**) | `done` | Root compose service |
| P2.4 | Java `CypherBuilderClient` (RestTemplate) | `done` | |
| P2.5 | Neo4j read execution as `svc_chat` | `done` | neo4j-java-driver |
| P2.6 | One end-to-end neo4j_direct golden case via bridge | `done` | `golden_events_count_today` |

---

## Phase 3 — Golden path: tools + graph

Implement only what golden cases require; mark each golden id when green.

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P3.1 | Pipeline: route → handler lanes (path is law) | `in_progress` | Eligibility + directory + summary + me + document_extraction + neo4j_direct |
| P3.2 | Eligibility / policy tools as needed by golden | `done` | Eligibility + directory + `policy_summary` |
| P3.3 | Me / who-am-i if in golden | `done` | All Python meKinds live (incl. waiting_for_me / who_else_can_act) |
| P3.4 | neo4j_direct + formatters for golden graph cases | `in_progress` | Bridge live; expand formatters beyond alert counts |
| P3.5 | Vector / hybrid only if a golden case needs it | `todo` | |
| P3.6 | Skills only if a golden case needs them | `deferred` | Likely after golden |

### Golden case checklist

| Golden case id | Status | Notes |
|----------------|--------|-------|
| `golden_policies_eligible_approvers_payment` | `done` | `ssi-chat-j/eval/eligibility_golden.yaml` |
| `golden_policies_eligible_submitters_payment` | `done` | same |
| `golden_policies_eligible_approvers_instruction` | `done` | same |
| `golden_policies_amount_club_directory` | `done` | amount-club policy directory |
| `golden_policies_covering_lob_directory` | `done` | covering-LOB policy directory |
| `golden_policies_instruction_approval_summary` | `done` | `policy_summary` via authz OBO |
| `golden_policies_payment_approval_summary` | `done` | funding / payment APPROVE summary |
| `golden_me_who_am_i_identity_tokens_pay205` | `done` | who-am-I identity token backticks |
| `golden_me_my_permissions_pay205` | `done` | my_permissions for pay-205 |
| `golden_me_can_create_payment_yes_pay205` | `done` | can_act CREATE yes |
| `golden_me_can_create_payment_fo_submitter` | `done` | FO create → fo_submitter |
| `golden_me_who_covers_lob_ficc` | `done` | who_covers_lob FICC |
| `golden_me_who_can_create_payment_ficc` | `done` | who_can_create payment for FICC |
| `golden_me_users_like_me_pay205` | `done` | users_like_me |
| `golden_me_can_approve_payment_capability` | `done` | can_approve directory-level |
| `golden_me_can_submit_payment_fo_fx` | `done` | can_submit FO yes |
| `golden_me_who_can_create_instruction` | `done` | who_can_create instruction |
| `golden_policies_payment_create_summary` | `done` | payment CREATE summary |
| `golden_policies_payment_cancel_summary` | `done` | payment CANCEL summary |
| `golden_policies_amount_club_inclusive_1b` | `done` | inclusive $1B directory |
| `golden_policies_amount_and_covering_combo` | `done` | amount + FICC covering |
| `golden_me_waiting_for_me_not_approver_fo` | `done` | FO not_approver |
| `golden_me_waiting_for_me_worklist_pay205` | `done` | live SUBMITTED + OPA worklist |
| `golden_me_who_else_can_act_need_id` | `done` | who_else need_id |
| `golden_me_who_else_can_act_submitted` | `done` | who_else on submitted payment |
| `golden_me_can_approve_instruction_no_pay205` | `done` | instruction APPROVE ≠ payment APPROVE |
| `golden_me_can_approve_instruction_yes_ficc300` | `done` | instruction APPROVE yes (desk FO) |
| `golden_me_can_create_instruction_no_pay205` | `done` | CREATE instruction ≠ payment CREATE |
| `golden_me_can_create_instruction_yes_mo` | `done` | CREATE instruction yes (mo-100) |
| `golden_me_can_approve_payment_no_fo` | `done` | FO cannot funding-approve |
| `golden_instruction_show_by_id_with_noun` | `done` | `document_extraction` |
| `golden_instruction_show_by_id_bare` | `done` | same |
| `golden_payment_show_by_id_with_noun` | `done` | same |
| `golden_payment_show_by_id_bare` | `done` | same |
| `golden_instruction_show_by_id_not_found` | `done` | negative |
| `golden_payment_show_by_id_not_found` | `done` | negative |
| `golden_instruction_show_by_id_forbidden_fo` | `done` | FO 403 UX |
| `golden_payment_show_by_id_forbidden_fo` | `done` | FO 403 UX |
| `golden_events_count_today` | `done` | neo4j_direct via cypher bridge |
| _(remaining from full `eval_golden.yaml`)_ | `todo` | ~19 Python-only (graph / denials / vector) |

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
| 2026-07-20 | Removed `ssi-chat-j` from root `docker-compose.yml` (Maven-only until Compose is wanted) |
| 2026-07-20 | Java chat observability: Micrometer → OTLP (same chat SLI names as Python); no Prometheus scrape endpoint yet |
| 2026-07-20 | Phase 2 cypher bridge: `cypher-builder-svc` wraps `plan_graph_queries` + validate; Java neo4j_direct proven by `golden_events_count_today` |
