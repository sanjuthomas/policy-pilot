# PolicyPilot (`ssi-chat`)

**PolicyPilot** is the conversational assistant for policy Q&A over indexed security events,
instructions, and payments — built for **middle-office supervisors** and **compliance officers**
who need a truthful, cross-system view of cash SSI and cash payment activity without opening
tickets across half the bank.

Modeled after
[sec-edgar-filings-chat](https://github.com/sanjuthomas/sec-edgar-filings-chat). Each question runs **Route → Retrieve → Synthesize**: Gemini returns a `RouterDecision` (eligibility, graph, vector, or hybrid), then only the required backends run — no store picker in the UI.

See the root [README.md](../README.md#why-this-exists) for the problem narrative. Full pipeline detail: [docs/intent-determination.md](../docs/intent-determination.md).

## URL

http://localhost:8092

## ML stack

| Role | Provider | Model |
|------|----------|-------|
| Semantic routing | **Vertex AI** | `gemini-2.5-flash` → `RouterDecision` JSON |
| Query embedding (vector search) | **Vertex AI** | `text-embedding-004` (768-dim) |
| Answer synthesis | **Vertex AI** | `gemini-2.5-flash` |
| Authorization WHY rewrite | **Vertex AI** | `gemini-2.5-flash` |
| Graph plan extraction (fallback) | **Vertex AI** | `gemini-2.5-flash` → `cypher_builder` |

Planned Cypher for counts, rankings, hierarchy, and known audit shapes comes from **[`shared/cypher_builder`](../shared/cypher_builder/README.md)** with no LLM call. Graph queries use `CREATED_IV`, `APPROVED_IV`, `CREATED_PV`, `FOR`, … — see [neo4j-graph-model/README.md](../neo4j-graph-model/README.md).

`PolicyPilotMlClient` (`gemini/client.py`) orchestrates Vertex embeddings and Gemini generation; retrieval and context assembly run locally.

## Search modes

The sidebar radio buttons select what the **Neo4j vector store** and graph focus on:

| Mode | Vector document `source` filter | Use for |
|------|---------------|---------|
| **Security Events** (`events`) | `instruction_security_event` + `payment_security_event` | Policy denials, audit trail, ALERT/INFO counts |
| **Instructions** (`instructions`) | `instruction_state` | Instruction state, duplicate routes, **Who/When/Why approval audit** |
| **Payments** (`payments`) | `payment_fact` | Payment amounts, statuses, approvers |
| **All entities** (`all`) | no filter | Cross-domain questions |

Pass `"mode"` in the API request body (default `"events"`).

## RAG pipeline

See **[Intent Determination in Policy Pilot](../docs/intent-determination.md)** for the full flow, strategy table, and code map.

Summary:

1. **Route** — Gemini structured `RouterDecision` (eligibility / graph / vector / hybrid)
2. **Skills** — scripted mutations (create / submit / approve / cancel payment: OPA preflight → Go / No Go → payment-service)
3. **Fast paths** — live OPA eligibility API; Neo4j direct YAML intents (planned Cypher + formatters); me-intents
4. **Selective retrieve** — graph only, vector only, or hybrid (RRF of vector + graph when both run)
5. **Synthesize** — deterministic formatters, Who/When/Why audit, or Gemini over context

### Create-payment skill

Natural-language create for payment creators (`PAYMENT_CREATOR` + middle office). Example:

> Can you create a payment for instruction ID 20260705-FICC-I-31? Value date tomorrow; amount: 12 million USD.

Flow: detect/parse → load instruction → dry-run authz `CREATE` → confirmation card (parties + accounts) → **Go** creates a DRAFT via payment-service, **No Go** cancels.

Full sequence diagram and API map: **[Create-payment skill](../docs/create-payment-skill.md)**. Package README: [`src/chat_application/skills/README.md`](src/chat_application/skills/README.md). Confirm API: `POST /api/chat/skills/create-payment/confirm`.

### Submit-payment skill

Owning-LOB desk analyst submits a **DRAFT** for funding approval. Example:

> Please submit payment 20260715-FICC-P-9 for approval.

Flow: parse payment id → load DRAFT → dry-run authz `SUBMIT` → confirmation card (same party details as create) → **Go** calls `POST …/payments/{id}/submit`.

Full write-up: **[Submit-payment skill](../docs/submit-payment-skill.md)**. Confirm API: `POST /api/chat/skills/submit-payment/confirm`.

### Approve-payment skill

Funding approver green-lights a **SUBMITTED** payment. Example:

> Please approve payment 20260715-FICC-P-9.

Flow: parse payment id → load SUBMITTED → dry-run authz `APPROVE` → confirmation card → **Go** calls `POST …/payments/{id}/approve`.

Full write-up: **[Approve-payment skill](../docs/approve-payment-skill.md)**. Confirm API: `POST /api/chat/skills/approve-payment/confirm`.

### Cancel-payment skill

Middle-office payment creator cancels a **DRAFT** or **SUBMITTED** payment. Example:

> Please cancel payment 20260715-FICC-P-9.

Flow: parse payment id → capability gate (`PAYMENT_CREATOR` + `MIDDLE_OFFICE`) → load DRAFT/SUBMITTED → dry-run authz `CANCEL` → confirmation card → **Go** calls `POST …/payments/{id}/cancel`.

Full write-up: **[Cancel-payment skill](../docs/cancel-payment-skill.md)**. Confirm API: `POST /api/chat/skills/cancel-payment/confirm`.

## Who / When / Why (approval audit)

For questions like _"Who approved instruction `<uuid>`?"_ in **Instructions** mode, or _"Who approved payment `<uuid>`?"_ in **Payments** mode:

| Part | Source | Method |
|------|--------|--------|
| **WHO** | `approver_display` from instruction state or graph | Deterministic — no LLM |
| **WHEN** | `approved_at` or APPROVE event timestamp | Deterministic — no LLM |
| **WHY** | `authorization_summary` + `allow_basis` from OPA | **Gemini rewrite** into 2–4 readable sentences; preserves all material policy checks; falls back to raw OPA text if Vertex fails |

Example answer shape:

```
WHO: Vasquez, Elena (ficc-300)
WHEN: 2026-06-27T02:48:09.697763
BASIS: Elena Vasquez was authorized to approve because her Vice President title satisfies the approval matrix for Analyst work in FICC, her LOB matched the instruction, and there was no reporting relationship between approver and creator. The instruction met duration, role, and valid-transition requirements.
```

Requires indexed `authorization_summary` on instruction state or APPROVE security events (populated automatically on new lifecycle actions).

## Live eligibility (“who can approve?”)

Questions like _“Who can approve payment `<uuid>`?”_ or _“Who can approve instruction `<uuid>`?”_ **bypass RAG** and call domain services directly:

| Question target | API |
|-----------------|-----|
| Payment | `POST http://payment-service:8093/api/v1/payments/{id}/eligible-approvers` |
| Instruction | `POST http://instruction-service:8000/api/v1/instructions/{id}/eligible-approvers` |

Requires **compliance sign-in** at http://localhost:8092 (`comp-001` / `comp-002`, or platform admin). Chat calls domain services with **svc-chat OBO** (`Authorization: svc-chat` + `X-On-Behalf-Of: compliance JWT`). Domain services resolve the compliance subject, load entity context (compliance may VIEW any LOB), and delegate batch OPA evaluation to authorization-service.

## Retrieval routing metrics

Every `POST /api/chat` answer records retrieval routing:

- **Structured log** — `chat.answer.completed strategy=… path=… requested=… override=… cypher=… synthesis=…` plus `chat.retrieval_strategy`, source channel counts, and timing fields on the log record.
- **OTel counters** — `chat.retrieval.route.count` (by strategy/path/mode), `chat.routing.path_decision.count` (requested vs executed path + `chat.route_override`), `chat.retrieval.source.channel.count` (vector/neo4j/exact hits), duration histograms.
- **Live distribution** — `GET /api/routing-stats` returns in-process counts since startup (`route_override_total`, `route_honored_total`, `by_path_pair`, …):

```bash
curl -s http://localhost:8092/api/routing-stats | jq
```

`retrieval_strategy` values align with the regression bank: `deterministic`, `graph`, `vector`, `eligibility`.

### Answer feedback (thumbs up/down)

Each assistant answer in the UI includes 👍/👎 controls. Feedback is posted to `POST /api/chat/feedback` with the answer's routing metadata. Logs and OTel counter `chat.feedback.count` are tagged by `chat.feedback_rating` and `chat.retrieval_strategy` so you can see satisfaction by mechanism (e.g. deterministic liked 90% of the time).

```bash
curl -s http://localhost:8092/api/feedback-stats | jq
```

## Example questions

See **`regression/questions.yaml`** for the full regression bank (56 cases, each tagged with `retrieval: deterministic | graph | vector | eligibility`) and **`regression/README.md`** for how to run it.

**Security Events mode:**
- How many ALERT events happened today?
- How many payment policy denial alerts happened today?
- Which user triggered the most policy denial alerts this week?

**Instructions mode:**
- Who approved instruction `<uuid>`? (Who / When / Why audit trail)
- Are there any instructions approved by someone who directly reports to the creator?
- Are there active instructions sharing the same creditor account and currency?

**Payments mode:**
- Who approved payment `<uuid>`? (Who / When / Why audit trail with OPA policy basis)
- How many payments were approved today for FICC?
- Show payments over $10M approved this week.

## Configuration (Docker)

Copy `.env.example` to `.env` at the repo root to override defaults. Docker Compose and pydantic-settings both read it.

| Variable | Default |
|----------|---------|
| `GCP_PROJECT_ID` | `rag-demos-501323` |
| `GCP_REGION` | `us-central1` |
| `VERTEX_EMBEDDING_MODEL` | `text-embedding-004` |
| `VERTEX_GEMINI_MODEL` | `gemini-2.5-flash` |
| `EMBEDDING_DIMENSION` | `768` |
| `GCP_SA_KEY_PATH` | host path to service account JSON (Compose mount) |
| `GOOGLE_APPLICATION_CREDENTIALS` | `/run/secrets/gcp-sa.json` (in container) |
| `MULTIMODAL_VECTOR_INDEX` | `multimodal_embedding` |
| `NEO4J_URI` | `bolt://neo4j:7687` |
| `NEO4J_USER` | `svc_chat` (compose); override for local runs |
| `NEO4J_PASSWORD` | `Password1!` (compose / default) |
| `PAYMENT_SERVICE_URL` | `http://payment-service:8093` |
| `INSTRUCTION_SERVICE_URL` | `http://instruction-service:8000` |
| `OIDC_ISSUER_URL` | `http://localhost:8080` |

Requires Neo4j vector documents (`MultimodalDocument` nodes) populated by **ssi-indexer** and **GCP Vertex AI** credentials.

For a populated graph with ALERT demo data, run `./ssi-demo-harness/seed-demo-data.sh` from the repo root (see [ssi-demo-harness/README.md](../ssi-demo-harness/README.md)).

## Run locally

```bash
cd ssi-chat
pip install -e ../shared/cypher_builder -e ../shared/vertex_client -e ../shared/telemetry -e .
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/your-vertex-key.json
ssi-chat
```

## API

```bash
curl -s -X POST http://localhost:8092/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Who approved instruction ID 242cf85e-6ae5-49bb-befb-9141d5053307?","mode":"instructions","history":[]}'
```

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness |
| POST | `/api/chat` | Ask a question (`mode`, multi-turn via `history`) |

## Docker

```bash
docker compose up -d ssi-chat
```

Ensure `GCP_SA_KEY_PATH` in `.env` points to a valid service account key (same as ssi-indexer).

## Unit tests (CI, no Gemini)

Hermetic coverage uses fixture `RouterDecision` values
([`tests/fixtures/router_decisions.py`](tests/fixtures/router_decisions.py)) as the
production routing contract. Happy-path tests must **not** treat
`heuristic_router_decision` as Gemini NLU — heuristics are LLM-failure fallback only
([issue #13](https://github.com/sanjuthomas/policy-pilot/issues/13)).

Coverage gate for `chat_application` is **70%** (other packages remain 80%).

## Regression suite

Harness seed from `questions.yaml` runs **by default** (use `--no-seed` to skip):

```bash
cd ssi-chat
pip install -e ".[regression]"
PYTHONPATH=. python -m regression.runner --report regression-report.json
```

See `regression/README.md` for filters (`--mode`, `--tags`, `--retrieval`, `--ids`) and CI usage via `RUN_CHAT_REGRESSION=1 pytest`.
