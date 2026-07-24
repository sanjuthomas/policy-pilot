# Agent instructions — ssi-chat-j

Guidance for AI agents working in this Java / Spring Boot chat A/B module.

Python `ssi-chat` (8092) remains production chat. This service listens on **8096**.

## Before commit and push

### Lint / compile / coverage (required)

From `ssi-chat-j/`:

```bash
mvn -B verify
```

That runs unit tests, writes a JaCoCo report, and **fails if line coverage is below 80%** on `com.sanjuthomas.policypilot` (entrypoint `ChatJApplication` excluded).

Report: `target/site/jacoco/index.html`

Do **not** commit or push if `mvn verify` fails.

### Coverage gate

| Target | Gate |
|--------|------|
| `ssi-chat-j` (`com.sanjuthomas.policypilot`) | **≥ 80%** line coverage |

Match root [AGENTS.md](../AGENTS.md) Python service expectations: add or update tests when you change code so coverage stays at or above the gate.

Prefer hermetic unit tests (mocks for ZITADEL, payment-service, Spring AI `ChatClient`). Do not require live Vertex or Compose for the coverage gate.

## Layout

| Path | Role |
|------|------|
| `src/main/java/com/sanjuthomas/policypilot/` | Application code |
| `src/main/java/.../cypher/` | In-process neo4j_direct Cypher planner — plan from `RouterDecision.graphIntent` (+ time/scope/kind); stable tokens for instruction ids / LOB codes only |
| `src/main/java/.../skill/` | Payment mutation skills (`path=skill`) — create/submit/approve/cancel with phase1 preflight + Go/No Go confirm + Go mutate (OPA dry-run/recheck + payment-service OBO). Confirm endpoints: `POST /api/chat/skills/{create,submit,approve,cancel}-payment/confirm` |
| `src/main/resources/templates/answers/` | Thymeleaf TEXT answer templates |
| `src/test/java/` | Unit tests |
| `scripts/prove-m1.sh` | Optional live golden against `:8096` |

## Conventions

### Thumb rule — no heuristic routing

**Primary intent / `RouterDecision.path` comes from Spring AI structured output.** Do not add regex, keyword, or fuzzy classifiers that *choose* the path. Grow `RouterPrompts.ROUTER_SYSTEM` and `RouterDecision` slots instead.

For **open-vocabulary** filters (lifecycle status, instruction type, worded money amounts), use LLM slots (`entityStatus`, `instructionType`, `directoryAmount`, …) — **not** synonym/lemma/typo tables in Java. Regex remains OK only for **stable tokens** (sequence ids, explicit `UP_TO_*_CLUB`, literal enum strings already in the question) and documented post-route clamps.

#### Documented exception — post-route clamps

After Spring AI returns a decision, `routing.RouteClamps` may **rewrite `path` before dispatch**. These clamps are **not** phrase NLU — they only act on LLM slots already set or stable tokens (sequence ids, literal enums):

| Clamp | When | Effect |
|-------|------|--------|
| Entity API preference | `extractionFacet` / `entityStatus` / `instructionType` slots (or literal inventory enums) while on `neo4j_direct` / `eligibility` / … | → `document_extraction` |
| Person permissions | LLM `personQuery` already set while on `me` / `eligibility` | → `person_permissions` |

- **Do** grow clamps only for slot/token repair with tests in `RouteClampsTest` — not who-approved / open-narrative / SoD / named-person phrase lists.
- **Do not** add ad-hoc regex that invents new primary lanes. Intent paraphrases belong in `RouterPrompts` + `RouterDecision` slots.
- Open narrative, past who-approved vs who-can, graph SoD, and named-person display names are **router-only** (no Java phrase clamp / `PersonQueryParser`).

Cursor rule: [`.cursor/rules/ssi-chat-j-intent-routing.mdc`](../.cursor/rules/ssi-chat-j-intent-routing.mdc) (mirrors Python [`intent-semantic-routing.mdc`](../.cursor/rules/intent-semantic-routing.mdc)).

### Other

- **Route** = producing `RouterDecision`; **path** = dispatch key (path is law). No silent slot defaults on the model.
- Router system prompt lives in `prompts/RouterPrompts.ROUTER_SYSTEM` (grow that string as paths are added).
- **Payment skills** (`path=skill`, `skill=create_payment|submit_payment|approve_payment|cancel_payment`) — LLM picks the skill **and** skill slots (`skillInstructionId` / `skillPaymentId` / `skillAmount` / `skillValueDate`). Amount and value date are never scraped from free text; sequence ids may fall back to `InstructionIdParser` / `PaymentIdParser` stable-token extractors only. Mode gate (`payments`/`all`) + role fence before dispatch; soft No Go + role-gated forbidden covered by `golden_skill_*` in the prove bank.
- Answer prose in Thymeleaf templates under `templates/answers/`; Java maps API data → view models.
- Shared display helpers (e.g. `MoneyFormat`, `PolicyBasisFormat`) are Spring beans exposed to answer templates via `AnswerRenderer` context variables — keep view models as state only.
- Keep changes focused; do not replace Python `ssi-chat`.
- Only create git commits when the user explicitly asks.

## CI

The root Build workflow runs `mvn -B verify` (tests + 80% JaCoCo check) and a Docker image build for `ssi-chat-j`.
