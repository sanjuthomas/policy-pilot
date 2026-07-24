# Approve-payment skill

Policy Pilot mutation skill: funding-approve an existing **SUBMITTED** payment after an OPA preflight and explicit **Go / No Go** confirmation.

| | |
|--|--|
| **Package** | [`ssi-chat-j/.../skill/`](../ssi-chat-j/src/main/java/com/sanjuthomas/policypilot/skill/) (`ApprovePaymentSkill`) |
| **Demo users** | `pay-201`, `pay-202`, `pay-204`, `pay-400` (`FUNDING_APPROVER`) |
| **Chat mode** | **Payments** |
| **Router** | `path=skill`, `skill=approve_payment` |

Related: **[Create-payment](create-payment-skill.md)** → **[Submit-payment](submit-payment-skill.md)** → this skill → **[Cancel-payment](cancel-payment-skill.md)**.

---

## Example

```text
Please approve payment 20260715-FICC-P-9.
```

Sign in as `pay-400` / `Password1!`, select **Payments**, then send the question. The payment must already be **SUBMITTED**.

---

## Sequence (happy path)

1. Gemini routes `path=skill` / `skill=approve_payment` (slot: payment id).
2. Load payment → must be `SUBMITTED`.
3. Load backing instruction (parties for the confirmation card).
4. OPA dry-run `APPROVE` via authz OBO (`svc-chat` + user JWT).
5. Confirmation card — same party/amount/value-date/LOB details as create/submit — **Go** / **No Go**.
6. On **Go**: re-check then `POST /api/v1/payments/{id}/approve` as the user; report approved status.

---

## Design rules

| Rule | Meaning |
|------|---------|
| Scripted pipeline | Fixed steps; LLM selects the skill, regex parses the payment id |
| OPA stays normative | Preflight and domain approve both use payment `APPROVE` |
| Fail closed on deny / No Go / authz re-check error | Nothing approved |
| Card parity | Debtor / creditor / intermediaries / amount / value date / LOB match create/submit |
| Maker–checker | Approver must satisfy four-eyes and reporting-line rules vs the payment creator |
