# Golden eval catalog

Hand-labeled chat cases with **strict quality gates** (routing, entity recall, faithfulness, source channels). Source of truth for case definitions: [`eval_golden.yaml`](eval_golden.yaml).

Unlike the main bank in [`questions.yaml`](questions.yaml) (mostly soft keywords / any-digit counts), golden cases fail when answer expectations **or** quality gates fail.

## How to run

Stack up, preferably after a clean slate + harness seed (same context placeholders as the main bank):

```bash
cd ssi-chat
pip install -e ".[regression]"
PYTHONPATH=. python -m regression.runner --eval-golden --report golden-eval.json
```

Seed runs by default (`--no-seed` if the graph is already warm). Offline schema / metric checks (no live stack):

```bash
pytest tests/test_eval_metrics.py -v
```

## Case catalog (11)

| ID | Mode | Retrieval | Question | Context | Quality gates | Answer expects |
|----|------|-----------|----------|---------|---------------|----------------|
| `golden_payment_creator` | payments | deterministic | Who created payment `{approved_payment_id}`? | `approved_payment_id` | `require_routing`, path `neo4j_direct`, Cypher `deterministic`, synthesis `formatter`, `require_entity_recall` | contains any: created, creator, submitted; min length 5 |
| `golden_payment_status` | payments | deterministic | What is the status of payment `{approved_payment_id}`? | `approved_payment_id` | `require_routing`, path `neo4j_direct`, `require_entity_recall` | contains any: approved, status, payment |
| `golden_events_count_today` | events | graph | How many ALERT events happened today? | — | `require_routing`, `min_groundedness` 0.05 | `answer_has_number` |
| `golden_events_top_denial_user` | events | deterministic | Which user triggered the most policy denial alerts this week? | — | `require_routing`, path `neo4j_direct`, Cypher `deterministic`, synthesis `formatter` | contains all: `pay-101`; min length 10 |
| `golden_instruction_status` | instructions | deterministic | What is the status of instruction `{approved_instruction_id}`? | `approved_instruction_id` | `require_routing`, path `neo4j_direct`, `require_entity_recall` | contains any: approved, status, instruction |
| `golden_events_who_approved_payment` | events | graph | Who approved payment `{approved_payment_id}` and why? | `approved_payment_id` | `require_routing`, `require_entity_recall` | contains any: approv, allowed, because, role; min length 20 |
| `golden_vector_security_summary` | events | graph (tag: vector) | Write a brief narrative about recent policy denial activity in the audit log. | — | `require_routing`, path `full_rag`, `min_faithfulness` 0.05 | min length 40; contains denial/alert/policy |
| `golden_instruction_denials_count_week` | events | deterministic | How many instruction policy denials happened this week? | — | `require_routing`, path `neo4j_direct`, Cypher `deterministic`, synthesis `formatter` | exact: “There were 2 instruction policy denial events this week.” |
| `golden_instruction_denials_list_week` | events | deterministic | Can you list all instruction denial events for this week? | — | same deterministic gates | `exact_graph_rows: 2`; title `(2)`; Entity ID; instruction / `-I-` |
| `golden_payment_denials_count_today` | events | deterministic | How many payment policy denial alerts happened today? | — | same deterministic gates | exact: “There were 4 payment policy denial events today.” |
| `golden_alerts_list_today_entity_ids` | events | deterministic | Can you report all ALERTS today? | — | same deterministic gates | `min_graph_rows: 2`; Entity ID + ALERT; `-I-` / `-P-` |

Pinned exact totals assume the shared harness seed in `eval_golden.yaml` / `questions.yaml` after truncate+reload. Do not re-seed on a warm graph before golden runs (`--no-seed`) or counts inflate.

### By theme

| Theme | Case IDs |
|-------|----------|
| Payment entity lookup | `golden_payment_creator`, `golden_payment_status` |
| Instruction entity lookup | `golden_instruction_status` |
| Denial / alert counts & lists | `golden_instruction_denials_count_week`, `golden_instruction_denials_list_week`, `golden_payment_denials_count_today`, `golden_alerts_list_today_entity_ids`, `golden_events_top_denial_user` |
| Other alert counts | `golden_events_count_today` |
| Auth narrative (who / why) | `golden_events_who_approved_payment` |
| Vector / full RAG | `golden_vector_security_summary` |

### By retrieval tag

| Retrieval | Count | Case IDs |
|-----------|------:|----------|
| deterministic | 8 | `golden_payment_creator`, `golden_payment_status`, `golden_events_top_denial_user`, `golden_instruction_status`, `golden_instruction_denials_count_week`, `golden_instruction_denials_list_week`, `golden_payment_denials_count_today`, `golden_alerts_list_today_entity_ids` |
| graph | 3 | `golden_events_count_today`, `golden_events_who_approved_payment`, `golden_vector_security_summary` |
| vector | 0 | (vector channel gate deferred; narrative case tagged graph for routing defaults) |

## Gate reference

Fields under each case’s `expect:` (see also [README.md](README.md#golden-labeled-set)):

| Field | Role |
|-------|------|
| `require_routing` | Fail if routing path / strategy does not satisfy declared expectations |
| `routing_path` | Expected `ChatResponse.routing.path` (e.g. `neo4j_direct`, `full_rag`) |
| `cypher_class` | Expected Cypher provenance class (`deterministic`, `llm`, `none`) |
| `answer_synthesis` | Expected synthesis path (e.g. `formatter`) |
| `require_entity_recall` | Seeded entity IDs from the question must appear in answer / sources / graph rows |
| `source_channels_any` | At least one retrieved source uses one of these channels (e.g. `vector`) |
| `min_sources` | Minimum number of sources |
| `min_groundedness` / `min_faithfulness` | Lightweight overlap proxies vs graph / retrieved context |
| `requires_context` | Skip (or fail) if seed context keys are missing |

## Out of scope today

Product surfaces that are **not** deterministic formatter paths (keep out of the todo list below):

- Vector / full-RAG summaries (`golden_vector_security_summary` already covers a soft variant)
- LLM-planned Cypher or Gemini synthesis answers
- Me-intents and create-payment skill (multi-turn / persona-dependent)
- Chat history / follow-ups

When adding cases: define them in `eval_golden.yaml` first, then update the **Case catalog** and check off the todo item below.

---

## Golden eval @To Do list

**Deterministic only** — Neo4j direct / planned Cypher + **formatter** (no Gemini answer synthesis, no vector RAG). Assumes **truncate + reload** with a fixed harness seed so counts, ranks, and entity bindings are stable.

Shared quality gates for every item unless noted:

```yaml
retrieval: deterministic
expect:
  require_routing: true
  routing_path: neo4j_direct   # or planned_graph if that is how the path is labeled
  cypher_class: deterministic
  answer_synthesis: formatter
```

Promote from the soft `questions.yaml` bank where listed; pin **exact** totals / row counts / user ids after one clean-slate measurement (re-measure before committing).

Denial / alert count & list goldens (former P0) now live only in the **Case catalog** above.

### P1 — Instruction inventory (planned counts / who)

| Proposed ID | Source / promote | Question (sketch) | Deterministic asserts to add | Notes |
|-------------|------------------|-------------------|------------------------------|-------|
| `golden_instructions_created_today` | `instructions_created_today` | How many instructions were created today? | Exact count from seed (`create-instructions` count + policy side effects — measure) | Wall-clock “today” OK after same-day seed |
| `golden_instructions_standing_ficc` | `instructions_standing_ficc` | How many STANDING instructions are there for LOB FICC? | Exact FICC STANDING total | Synonym taxonomy already predefined |
| `golden_instructions_pending_submitted` | `instructions_pending_approval` | How many instructions are in SUBMITTED? | Exact SUBMITTED total | |
| `golden_instructions_per_lob` | `instructions_per_lob` | How many instructions exist per LOB? | Facet rows include known LOBs (FICC, …) with exact per-LOB counts | Formatter facet |
| `golden_instructions_who_approved` | `instructions_who_approved` | Who approved instruction `{approved_instruction_id}`? | Entity recall + exact approver user id / name from seed personas | Partial overlap with status golden |
| `golden_instructions_creator_and_approver` | `instructions_creator_and_approver` | Who created … and who approved …? | Both creator and approver ids present | |
| `golden_instructions_group_by_status` | `instructions_group_by_status_facet` | Can you group instructions by status? | Every seeded status bucket present with exact counts | |

### P2 — Payment inventory (planned counts / who / facets)

| Proposed ID | Source / promote | Question (sketch) | Deterministic asserts to add | Notes |
|-------------|------------------|-------------------|------------------------------|-------|
| `golden_payments_approved_ficc_today` | `payments_approved_ficc_today` | How many payments were approved today for FICC? | Exact count | |
| `golden_payments_submitted_count` | `payments_submitted_count` | How many payments are in SUBMITTED status? | Exact count | |
| `golden_payments_created_week` | `payments_created_week` | How many payments were created this week? | Exact count | |
| `golden_payments_rejected_week` | `payments_rejected_week` | How many payments were rejected this week? | Exact **1** if seed `reject-payments: 1` stays fixed | |
| `golden_payments_total_approved_ficc_today` | `payments_total_approved_ficc_today` | Total approved payment amount for FICC today? | Exact amount **only if** harness amounts are fixed; else skip or pin ±0 from seed script | Verify amount determinism first |
| `golden_payments_who_approved` | `payments_who_approved` | Who approved payment `{approved_payment_id}`? | Entity recall + exact approver id | Related soft golden exists under events |
| `golden_payments_creator_and_approver` | `payments_creator_and_approver` (+ overlaps `golden_payment_creator`) | Who created … and who approved …? | Creator + approver ids | Extend existing creator golden |
| `golden_payments_for_instruction` | `payments_for_instruction` | List APPROVED payments for instruction `{approved_payment_instruction_id}` | Row count + payment ids subset | |
| `golden_payments_mo_ficc_week` | `payments_mo_ficc_week` | Payments created by middle office for FICC this week? | Exact count | |
| `golden_payments_group_by_approver` | `payments_group_by_approver` | Group payments by approver | Known approver buckets + counts | |
| `golden_payments_top_creator` | `payments_superlative_top_creator` | Who created the most payments? | Exact winning `user_id` if seed makes a unique top | Skip if tie-prone |
| `golden_payments_largest_creator` | `payments_largest_who_created` | Who created the payment with the maximum dollar value? | Exact creator **only if** max amount is unique in seed | Skip if amounts collide |

### P3 — Auth / why formatters (still deterministic Neo4j)

| Proposed ID | Source / promote | Question (sketch) | Deterministic asserts to add | Notes |
|-------------|------------------|-------------------|------------------------------|-------|
| `golden_events_who_approved_payment_why` | `events_who_approved_payment_why` (retag); strengthen soft `golden_events_who_approved_payment` | Who approved payment `{id}` and why were they allowed? | Path + formatter; entity recall; require funding / role tokens **without** allowing empty escapes | Drop `no`/`0` soft escapes |
| `golden_events_when_instruction_approved_why` | `events_when_instruction_approved_why` | When was instruction `{id}` approved, and authorization basis? | Timestamp presence from graph row + basis keywords | Measure formatter output shape first |

### P4 — Policies-mode tools (deterministic, no RAG)

Not in `questions.yaml` today; answers come from live policy / AuthZ tools (static catalogs + seed directory). Still **deterministic** if we lock persona (`comp-001`) and OPA/seed fixtures.

| Proposed ID | Question (sketch) | Deterministic asserts to add | Notes |
|-------------|-------------------|------------------------------|-------|
| `golden_policies_payment_approve_summary` | What are the payment APPROVE policy rules? | Routing to policy tools; stable section headings / key rule phrases from Rego catalog | Normative summary |
| `golden_policies_amount_club_directory` | Which users are in amount clubs that cover 10M? | Exact user id set from seed directory for a fixed club | Directory tool |
| `golden_policies_person_permissions` | What can user `pay-101` create / approve? | Exact capability list for that subject | Person permissions |
| `golden_policies_eligible_approvers_payment` | Who can approve payment `{approved_payment_id}`? | Exact eligible user set vs instruction/payment services | Eligibility-via-chat |

### Explicitly not on this list

| Topic | Why excluded from deterministic golden |
|-------|----------------------------------------|
| Vector summaries / open audit prose | Non-deterministic wording even with static docs |
| LLM Cypher for ad-hoc shapes | Not formatter-stable |
| Create-payment skill Go / No Go | Mutation + multi-turn |
| Me-intents under `pay-*` / `mo-*` | Persona matrix; separate suite |
| Compliance SoD graph finds that currently allow `no`/`0`/`none` | Need seed that **always** produces the violation before exact asserts |

### Suggested rollout

1. P1–P2 inventory counts (cheapest asserts: `answer_contains_all` for the digit / facet lines, or a future `exact_total` expect field).
2. P3 once formatter strings for who/why are frozen.
3. P4 once runner supports `mode: policies` and compliance session in golden runs.
