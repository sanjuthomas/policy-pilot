# ssi-chat-j

Java / Spring Boot + Spring AI **A/B** chat experiment. Python `ssi-chat` stays on **8092**; this service listens on **8096**.

## Current surface

- `GET /health`
- `POST /api/auth/login` (ZITADEL session)
- Shared PolicyPilot static UI (build-time copy of assets)
- `POST /api/chat` eligibility lanes:
  - payment APPROVE → payment-service `eligible-approvers`
  - payment SUBMIT → authz `eligible-submitters`
  - instruction APPROVE → instruction-service `eligible-approvers`

## Run (Compose)

```bash
docker compose up -d --build ssi-chat-j
curl -s http://localhost:8096/health
```

## Eligibility golden eval (HTTP black-box)

Cases live under [`eval/`](eval/) (owned by this module — not loaded at Java runtime).

Warm stack with harness entity context (`submitted_payment_id`, `draft_payment_id`, `pending_instruction_id`):

```bash
./ssi-chat-j/scripts/prove-eligibility.sh
```

That runs the three goldens against `http://localhost:8096` via the temporary Python regression CLI (`--golden` points at `eval/eligibility_golden.yaml`).

## Local Maven

```bash
cd ssi-chat-j
mvn -q spring-boot:run
```

Coverage: `mvn verify` (≥ 80% JaCoCo). See [`AGENTS.md`](AGENTS.md).

Plan / todo: [`docs/ssi-chat-j-plan.md`](../docs/ssi-chat-j-plan.md), [`docs/ssi-chat-j-todo.md`](../docs/ssi-chat-j-todo.md).
