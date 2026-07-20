# ssi-chat-j

Java / Spring Boot + Spring AI **A/B** chat experiment. Python `ssi-chat` stays on **8092**; this service listens on **8096**.

## M1 (current)

- `GET /health`
- `POST /api/auth/login` (ZITADEL session, parity with Python)
- `POST /api/chat` routed by Spring AI `RouterDecision`
- One Policies path: **Who can approve payment {id}?** via payment-service `eligible-approvers` with svc-chat OBO

## Run (Compose)

```bash
docker compose up -d --build ssi-chat-j
curl -s http://localhost:8096/health
```

## Prove M1 (golden case)

Requires a warm stack with harness seed context (`submitted_payment_id`). From repo root:

```bash
./ssi-chat-j/scripts/prove-m1.sh
```

Or manually:

```bash
cd ssi-chat
CHAT_BASE_URL=http://localhost:8096 \
  python -m regression.runner --eval-golden --ids golden_policies_eligible_approvers_payment --no-seed
```

## Local Maven

```bash
cd ssi-chat-j
mvn -q spring-boot:run
```

Plan / todo: [`docs/ssi-chat-j-plan.md`](../docs/ssi-chat-j-plan.md), [`docs/ssi-chat-j-todo.md`](../docs/ssi-chat-j-todo.md).
