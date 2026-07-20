# ssi-chat-j

Java / Spring Boot + Spring AI **A/B** chat experiment. Python `ssi-chat` stays on **8092**; this service listens on **8096**.

Not wired into the root `docker-compose.yml` yet — run locally with Maven against a warm stack.

## Current surface

- `GET /health`
- `POST /api/auth/login` (ZITADEL session)
- Shared PolicyPilot static UI (build-time copy of assets)
- `POST /api/chat` eligibility lanes:
  - payment APPROVE → payment-service `eligible-approvers`
  - payment SUBMIT → authz `eligible-submitters`
  - instruction APPROVE → instruction-service `eligible-approvers`
- `POST /api/chat` policy directory (amount club):
  - authz `payment-amount-limits` + `groups/{club}/members`

## Run (Maven)

With the usual Compose stack up (Python chat, payment, instruction, authz, ZITADEL, …):

```bash
cd ssi-chat-j
mvn -q spring-boot:run
curl -s http://localhost:8096/health
```

Coverage: `mvn verify` (≥ 80% JaCoCo). See [`AGENTS.md`](AGENTS.md).

## Eligibility golden eval (HTTP black-box)

Cases live under [`eval/`](eval/) (owned by this module — not loaded at Java runtime).

Warm stack with harness entity context (`submitted_payment_id`, `draft_payment_id`, `pending_instruction_id`) and Java chat on `:8096`:

```bash
./ssi-chat-j/scripts/prove-eligibility.sh
```

That runs the three goldens via the temporary Python regression CLI (`--golden` points at `eval/eligibility_golden.yaml`).

Plan / todo: [`docs/ssi-chat-j-plan.md`](../docs/ssi-chat-j-plan.md), [`docs/ssi-chat-j-todo.md`](../docs/ssi-chat-j-todo.md).
