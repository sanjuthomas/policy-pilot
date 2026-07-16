# Skills (`chat_application.skills`)

Mutation skills for Policy Pilot — scripted multi-step actions with confirmation gates.

## Create-payment

Full design, sequence diagram, APIs, and demo notes:

→ **[docs/create-payment-skill.md](../../../../docs/create-payment-skill.md)**

Quick start: sign in as `pay-205`, **Payments** mode:

```text
Can you create a payment for instruction ID <APPROVED-ID>?
Value date tomorrow; amount: 12 million USD.
```

## Submit-payment

Desk analyst (owning LOB) submits a **DRAFT** payment for funding approval:

→ **[docs/submit-payment-skill.md](../../../../docs/submit-payment-skill.md)**

Quick start: sign in as `fo-ficc-101`, **Payments** mode:

```text
Please submit payment <DRAFT-PAYMENT-ID> for approval.
```
