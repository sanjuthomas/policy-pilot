# Agent instructions — ssi-chat-j

Guidance for AI agents working in this Java / Spring Boot chat A/B module.

Python `ssi-chat` (8092) remains production chat. This service listens on **8096**.

## Before commit and push

### Lint / compile / coverage (required)

From `ssi-chat-j/`:

```bash
mvn -B verify
```

That runs unit tests, writes a JaCoCo report, and **fails if line coverage is below 80%** on `com.policypilot.chatj` (entrypoint `ChatJApplication` excluded).

Report: `target/site/jacoco/index.html`

Do **not** commit or push if `mvn verify` fails.

### Coverage gate

| Target | Gate |
|--------|------|
| `ssi-chat-j` (`com.policypilot.chatj`) | **≥ 80%** line coverage |

Match root [AGENTS.md](../AGENTS.md) Python service expectations: add or update tests when you change code so coverage stays at or above the gate.

Prefer hermetic unit tests (mocks for ZITADEL, payment-service, Spring AI `ChatClient`). Do not require live Vertex or Compose for the coverage gate.

## Layout

| Path | Role |
|------|------|
| `src/main/java/com/policypilot/chatj/` | Application code |
| `src/main/resources/templates/answers/` | Thymeleaf TEXT answer templates |
| `src/test/java/` | Unit tests |
| `scripts/prove-m1.sh` | Optional live golden against `:8096` |

## Conventions

- **Route** = producing `RouterDecision`; **path** = dispatch key (path is law). No silent slot defaults on the model.
- Intent from Spring AI structured `RouterDecision` — not regex heuristics for classification. Regex is OK for **slots** (e.g. payment id) after path is known.
- Router system prompt lives in `prompts/RouterPrompts.ROUTER_SYSTEM` (grow that string as paths are added).
- Answer prose in Thymeleaf templates under `templates/answers/`; Java maps API data → view models.
- Shared display helpers (e.g. `MoneyFormat`) live under `formatting/` as static utilities when reused across lanes.
- Keep changes focused; do not replace Python `ssi-chat`.
- Only create git commits when the user explicitly asks.

## CI

The root Build workflow runs `mvn -B verify` (tests + 80% JaCoCo check) and a Docker image build for `ssi-chat-j`.
