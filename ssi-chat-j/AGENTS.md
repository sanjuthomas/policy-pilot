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
| `src/main/resources/templates/answers/` | Thymeleaf TEXT answer templates |
| `src/test/java/` | Unit tests |
| `scripts/prove-m1.sh` | Optional live golden against `:8096` |

## Conventions

### Thumb rule — no heuristic routing

**Intent / `RouterDecision.path` comes from Spring AI structured output only.** Do not add regex, keyword, or fuzzy classifiers that choose the path. Grow `RouterPrompts.ROUTER_SYSTEM` and `RouterDecision` slots instead.

For `policy_directory`, money size is an LLM slot only (`directoryAmount`, `directoryAmountStrict`) — no regex amount NLU. Regex remains OK for **stable tokens** (sequence ids, explicit `UP_TO_*_CLUB`).

Cursor rule: [`.cursor/rules/ssi-chat-j-intent-routing.mdc`](../.cursor/rules/ssi-chat-j-intent-routing.mdc) (mirrors Python [`intent-semantic-routing.mdc`](../.cursor/rules/intent-semantic-routing.mdc)).

### Other

- **Route** = producing `RouterDecision`; **path** = dispatch key (path is law). No silent slot defaults on the model.
- Router system prompt lives in `prompts/RouterPrompts.ROUTER_SYSTEM` (grow that string as paths are added).
- Answer prose in Thymeleaf templates under `templates/answers/`; Java maps API data → view models.
- Shared display helpers (e.g. `MoneyFormat`, `PolicyBasisFormat`) are Spring beans exposed to answer templates via `AnswerRenderer` context variables — keep view models as state only.
- Keep changes focused; do not replace Python `ssi-chat`.
- Only create git commits when the user explicitly asks.

## CI

The root Build workflow runs `mvn -B verify` (tests + 80% JaCoCo check) and a Docker image build for `ssi-chat-j`.
