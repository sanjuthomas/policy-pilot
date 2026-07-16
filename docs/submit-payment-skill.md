# Submit-payment skill

Policy Pilot mutation skill: submit an existing **DRAFT** payment for funding approval after an OPA preflight and explicit **Go / No Go** confirmation.

Middle-office creators draft payments; a **front-office desk analyst** whose `subject.lob` matches the instruction owning LOB submits them (`PAYMENT_CREATOR` + LOB match — see OPA `SUBMIT`).

| | |
|--|--|
| **Package** | [`ssi-chat/src/chat_application/skills/`](../ssi-chat/src/chat_application/skills/) (`submit_payment.py`) |
| **Demo users** | `fo-ficc-101`, `fo-fx-101`, `fo-rates-101` (desk submitters) |
| **Chat mode** | **Payments** |
| **Router** | `path=skill`, `skill=submit_payment` |

Related: **[Create-payment skill](create-payment-skill.md)** (draft first), **[Approve-payment skill](approve-payment-skill.md)** (funding approve after submit), **[Cancel-payment skill](cancel-payment-skill.md)** (cancel draft/submitted).

---

## Example

```text
Please submit payment 20260715-FICC-P-9 for approval.
```

Sign in as `fo-ficc-101` / `Password1!` (FICC desk), select **Payments**, then send the question. The payment must already exist as **DRAFT**.

---

## Sequence (happy path)

1. Gemini routes `path=skill` / `skill=submit_payment` (slot: payment id).
2. Load payment → must be `DRAFT`.
3. Load backing instruction (parties for the confirmation card).
4. OPA dry-run `SUBMIT` via authz OBO (`svc-chat` + user JWT).
5. Confirmation card — same party/amount/value-date/LOB details as create-payment, plus payment id/status — **Go** / **No Go**.
6. On **Go**: re-check then `POST /api/v1/payments/{id}/submit` as the user; report + eligible approvers.

---

## Design rules

| Rule | Meaning |
|------|---------|
| Scripted pipeline | Fixed steps; LLM selects the skill, regex parses the payment id |
| OPA stays normative | Preflight and domain submit both use payment `SUBMIT` |
| Fail closed on deny / No Go | Nothing submitted |
| Card parity | Debtor / creditor / intermediaries / amount / value date / LOB match create-payment |
