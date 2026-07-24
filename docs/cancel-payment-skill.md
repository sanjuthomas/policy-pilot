# Cancel-payment skill

Policy Pilot mutation skill: cancel an existing **DRAFT** or **SUBMITTED** payment after an OPA preflight and explicit **Go / No Go** confirmation.

| | |
|--|--|
| **Package** | [`ssi-chat-j/.../skill/`](../ssi-chat-j/src/main/java/com/sanjuthomas/policypilot/skill/) (`CancelPaymentSkill`) |
| **Demo users** | `pay-101`, `pay-205` (`PAYMENT_CREATOR` + `MIDDLE_OFFICE`) |
| **Chat mode** | **Payments** |
| **Router** | `path=skill`, `skill=cancel_payment` |

Related: **[Create-payment](create-payment-skill.md)** → **[Submit-payment](submit-payment-skill.md)** → **[Approve-payment](approve-payment-skill.md)** → this skill.

---

## Example

```text
Please cancel payment 20260715-FICC-P-9.
```

Sign in as `pay-101` / `Password1!`, select **Payments**, then send the question. The payment must be **DRAFT** or **SUBMITTED**.

---

## Sequence (happy path)

1. Gemini routes `path=skill` / `skill=cancel_payment` (slot: payment id).
2. Capability gate: subject must be `PAYMENT_CREATOR` **and** `MIDDLE_OFFICE` (FO-only creators are refused).
3. Load payment → must be `DRAFT` or `SUBMITTED`.
4. Load backing instruction (parties for the confirmation card).
5. OPA dry-run `CANCEL` via authz OBO (`svc-chat` + user JWT).
6. Confirmation card — same party/amount/value-date/LOB details as create/submit — **Go** / **No Go**.
7. On **Go**: re-check then `POST /api/v1/payments/{id}/cancel` as the user; report cancelled status.

---

## Design rules

| Rule | Meaning |
|------|---------|
| Scripted pipeline | Fixed steps; LLM selects the skill, regex parses the payment id |
| OPA stays normative | Preflight and domain cancel both use payment `CANCEL` |
| Fail closed on deny / No Go / authz re-check error | Nothing cancelled |
| Status gate | Only DRAFT and SUBMITTED are cancellable |
| Card parity | Debtor / creditor / intermediaries / amount / value date / LOB match create/submit |
| Role + group | Cancel requires middle-office creator — not front-office desk-only creators |
