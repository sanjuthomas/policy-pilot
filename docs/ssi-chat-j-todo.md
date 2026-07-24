# ssi-chat-j — living todo

Status tracker for **Policy Pilot chat** (`ssi-chat-j`). Historical A/B plan: [`ssi-chat-j-plan.md`](ssi-chat-j-plan.md).

**Success bar:** golden eval green against `http://localhost:8096` (**98** cases in `ssi-chat-j/eval/`). Python `ssi-chat` and `cypher-builder-svc` are **retired**.

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
| **M1** — health + login + eligibility golden | `done` | `prove-eligibility.sh` on `:8096` |
| Observability (Micrometer → OTLP) | `done` | Same chat SLI names as Python; no Prometheus scrape |
| Document extraction (API) | `done` | `path=document_extraction` → instruction/payment GET |
| Phase 2 cypher bridge | `done` | Historical [#99](https://github.com/sanjuthomas/policy-pilot/pull/99); **superseded** by in-process Java planner |
| In-process Java Cypher planner | `done` | `com.sanjuthomas.policypilot.cypher` — no HTTP bridge for `ssi-chat-j` |
| **P3.4** — neo4j_direct security-event / denial formatters | `done` | Thymeleaf templates + LOB scope; 8 denial/alert goldens |
| Entity status / creator goldens | `done` | status + payment creator via bridge YAML-parity |
| Who-approved payment golden | `done` | approval-lookup Thymeleaf; heuristic + entity_plan fallback |
| FO/MO instruction VIEW goldens | `done` | `golden_instruction_view_fo_ficc` / `_mo_covering_ficc` |
| **P3.5** — vector security summary | `done` | `golden_vector_security_summary` green on `:8096` |
| **person_permissions** | `done` | Authz directory summary; `golden_person_permissions_kowalski` in prove bank |
| **neo4j_direct remaining port** | `done` | SoD goldens in prove bank; facet families still backlog |
| **Payment mutation skills** | `done` | `path=skill` + LLM `SkillSlots` (amount/date from router; id stable-token fallback); **17** `golden_skill_*` |
| **Python chat + cypher HTTP bridge retired** | `done` | Compose/CI use `ssi-chat-j` only; UI vendored under `ssi-chat-j/.../static/` |
| **Next** | `todo` | Facet-family goldens / prove flakes (seed context, LOB-scope denials) |

**Bank snapshot:** prove bank **98** (policies 11 · me 18 · skills 17 · graph/entity/SoD/vector remainder).

### neo4j_direct / entity facets (historical Python YAML parity)

Skip: `*.show_by_id` (intentional Java `document_extraction`).

| Intent | Status | Golden |
|--------|--------|--------|
| `instruction.show_by_id` / `payment.show_by_id` | `done` | document_extraction (API) |
| `payment.status_by_id` / `instruction.status_by_id` | `done` | document_extraction (API) |
| `payment.creator_by_id` / `instruction.creator_by_id` | `done` | document_extraction (API); goldens `golden_payment_creator`, `golden_instruction_creator` |
| `payment.creator_and_approver_by_id` / `instruction.creator_and_approver_by_id` | `done` | document_extraction (API) |
| `instruction.list_by_status` | `done` | `golden_instructions_list_by_status` (API) |
| `instruction.list_standing` | `done` | API list `instruction_type=STANDING` |
| `instruction.list_single_use` | `done` | API list `instruction_type=SINGLE_USE` |
| `instruction.created_by_user` | `done` | API list `created_by_user_id=` |
| `instruction.versions_by_id` / `payment.versions_by_id` | `done` | domain `/versions` APIs |
| `payment.approver_by_id` / `instruction.approver_by_id` | `done` | domain GET + lifecycle/approved_by (`golden_events_who_approved_payment`, `golden_instruction_who_approved`) |
| `instruction.self_approval` | `done` | `golden_instructions_self_approval` (soft empty-or-found) |
| `instruction.subordinate_approver` | `done` | `golden_instructions_subordinate_approver` |
| `instruction.duplicate_routes` | `done` | `golden_instructions_duplicate_routes` |
| `instruction.mutual_approval` | `done` | `golden_instructions_mutual_approval` (+ demo seed in prove) |
| `instruction.cross_entity_reciprocal_approval` | `done` | `golden_cross_entity_reciprocal_approval` (+ demo seed in prove) |
| `events.instruction_timeline_by_id` | `done` | `golden_events_instruction_timeline` |
| Facet counts / group-by (document_extraction list APIs) | `done` | Soft: status/LOB group-by + day/week/month/quarter/year counts |

---

## Milestone M1 (shipped)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| M1.1 | `ssi-chat-j` listening on **8096** | `done` | Root Compose service `ssi-chat-j` |
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
| P3.1 | Pipeline: route → handler lanes (path is law) | `done` | Eligibility + directory + summary + me + document_extraction + neo4j_direct + vector/full_rag |
| P3.2 | Eligibility / policy tools as needed by golden | `done` | Eligibility + directory + `policy_summary` |
| P3.3 | Me / who-am-i if in golden | `done` | All Python meKinds live |
| P3.4 | neo4j_direct + formatters for golden graph cases | `done` | Counts / lists / ranking / status / creator; LOB scope |
| P3.5 | Vector / hybrid only if a golden case needs it | `done` | `golden_vector_security_summary` green on `:8096` |
| P3.6 | Skills only if a golden case needs them | `deferred` | Likely after golden |

### Golden case checklist — Java bank green (54)

| Golden case id | Status | Notes |
|----------------|--------|-------|
| `golden_policies_eligible_approvers_payment` | `done` | |
| `golden_policies_eligible_submitters_payment` | `done` | |
| `golden_policies_eligible_approvers_instruction` | `done` | |
| `golden_policies_amount_club_directory` | `done` | |
| `golden_policies_covering_lob_directory` | `done` | |
| `golden_policies_instruction_approval_summary` | `done` | |
| `golden_policies_payment_approval_summary` | `done` | |
| `golden_policies_payment_create_summary` | `done` | |
| `golden_policies_payment_cancel_summary` | `done` | |
| `golden_policies_amount_club_inclusive_1b` | `done` | |
| `golden_policies_amount_and_covering_combo` | `done` | |
| `golden_me_*` (18 cases) | `done` | who_am_i through can_approve_payment_no_fo |
| `golden_instruction_show_by_id_*` / `golden_payment_show_by_id_*` (8) | `done` | `document_extraction` |
| `golden_events_count_today` | `done` | neo4j_direct via cypher bridge |
| `golden_instruction_denials_count_week` | `done` | Thymeleaf count template |
| `golden_instruction_denials_list_week` | `done` | Thymeleaf list template |
| `golden_payment_denials_count_today` | `done` | Thymeleaf count template |
| `golden_alerts_list_today_entity_ids` | `done` | Thymeleaf list template |
| `golden_events_top_denial_user` | `done` | Thymeleaf ranking template |
| `golden_fo_rates_instruction_denials_scoped` | `done` | subject LOB scope (DESK_RATES negative) |
| `golden_fo_fx_payment_denials_scoped` | `done` | subject LOB scope |
| `golden_fo_ficc_instruction_denials_positive` | `done` | subject LOB scope |
| `golden_payment_status` | `done` | entity detail via cypher bridge |
| `golden_instruction_status` | `done` | entity detail via cypher bridge |
| `golden_payment_creator` | `done` | entity detail via cypher bridge |
| `golden_events_who_approved_payment` | `done` | payment_approval_lookup + Thymeleaf WHO/WHEN/WHY |
| `golden_instruction_view_fo_ficc` | `done` | FO FICC desk LOB VIEW via neo4j_direct status |
| `golden_instruction_view_mo_covering_ficc` | `done` | MO covering-FICC VIEW via neo4j_direct status |
| `golden_vector_security_summary` | `done` | vector → `full_rag` + `gemini_full`; cypher_class=none |

### Remaining Python-only (0) — A/B parity closed

No Python-only golden cases remain open for the Java success bar.

### Hygiene (deferred for success bar)

| Item | Status | Notes |
|------|--------|-------|
| Promote 27 Java-only goldens into Python bank | `deferred` | A/B hygiene; not blocking Java success bar |

---

## Phase 4 — Golden eval green

| ID | Item | Status | Notes |
|----|------|--------|-------|
| P4.1 | Run seed + eligibility golden against `:8096` | `done` | `prove-eligibility.sh` / warm `--no-seed` |
| P4.2 | Triage failures into Phase 3 backlog | `done` | Last Python-only case closed |
| P4.3 | Document A/B how-to (switch `CHAT_BASE_URL`) | `done` | `ssi-chat-j/README.md` + `eval/README.md` |
| P4.4 | **Success bar met** | `done` | Java bank **54**; Python-only **0** |

---

## Deferred (after golden)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| D.1 | Full `questions.yaml` bank | `deferred` | |
| D.2 | Payment skills parity | `done` | Soft bank green on `:8096` (4 forbidden + 4 phase1 No Go); Go mutate implemented for API parity (not in golden bank yet) |
| D.3 | Replace Python chat | `done` | Python `ssi-chat` + `cypher-builder-svc` retired; Java is the chat surface |
| D.4 | Native Java `cypher_builder` port | `done` | In-process `com.sanjuthomas.policypilot.cypher` (alerts + SoD + timeline); no HTTP bridge |

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
| 2026-07-20 | Merged [#99](https://github.com/sanjuthomas/policy-pilot/pull/99) to main; next focus = P3.4 denial/alert formatters (15 Python-only remaining) |
| 2026-07-21 | P3.4: Thymeleaf neo4j_direct count/list/ranking templates + subject LOB scope on cypher-builder-svc; 8 denial/alert goldens |
| 2026-07-21 | Entity status/creator: cypher-builder-svc YAML-parity plan fallback + Thymeleaf formatters; `golden_payment_status` / `golden_instruction_status` / `golden_payment_creator` |
| 2026-07-21 | FO/MO instruction VIEW goldens (`fo-ficc-101`, `pay-101`); formatter `generation_ms=0` parity with Python neo4j_direct |
| 2026-07-21 | P3.5: vector/full_rag lane (`EmbeddingModel` + Neo4j `queryNodes` + Gemini synthesize); `golden_vector_security_summary` green — A/B Python parity closed |
| 2026-07-22 | `instruction.list_by_status`: cypher-builder inventory plan + Thymeleaf inventory table; `golden_instructions_list_by_status` |
| 2026-07-22 | Entity inventory/detail (status/creator/combo/list/versions) moved to `document_extraction` domain APIs; Neo4j reserved for alerts/SoD/who-approved |
| 2026-07-23 | Dropped cypher-builder HTTP bridge for Java; in-process `GraphCypherPlanner` covers alerts + SoD + timeline |
| 2026-07-23 | Six Neo4j SoD goldens added to prove bank (self/subordinate/duplicate/mutual/cross/timeline); mutual+cross demo-seeded in prove |
| 2026-07-24 | Skill slots via `RouterDecision` (no free-text amount/date regex); UI parity (integrity + login roles); retire Python chat + cypher HTTP bridge from git/Compose; prove bank **98** |
