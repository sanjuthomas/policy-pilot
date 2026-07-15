# Domain models

Instruction and payment entities in the cash SSI demo — what they represent and how they lifecycle.

## Instruction model

An **instruction** is an **SSI settlement route template** — accounts, agent chain, currency, and validity. It is **not** a payment message; no amount, value date, or remittance information lives here.

```
instruction_type    STANDING | SINGLE_USE
wire_scope          DOMESTIC | INTERNATIONAL
currency            ISO 4217 (e.g. USD, EUR)
funding_account     source account
debtor / creditor   legal entities
*_agent             bank chain (ABA / BIC / CHIPS)
effective_date      template validity start
end_date            template validity end
```

Lifecycle: `DRAFT` → `SUBMITTED` → `APPROVED` or `REJECTED`; approved instructions may become `SUSPENDED`, `USED`, `EXPIRED`, or `CANCELLED`. `STANDING` and `SINGLE_USE` remain instruction types, not lifecycle statuses.

API and UI: `instruction-service/` — see [instruction-service/README.md](../instruction-service/README.md).

## Payment model

A **payment** is a cash transfer request against an approved SSI instruction. Middle-office users create payments; front-office desk users submit them; funding approvers approve or reject.

```
instruction_id      linked approved SSI route
amount              payment amount (USD in demo)
currency            ISO 4217
value_date          settlement date
owning_lob          inherited from instruction
```

Lifecycle: `DRAFT` → `SUBMITTED` → `APPROVED` or `REJECTED` (or `CANCELLED` if the instruction becomes invalid at approval time).

Policy denials (self-approval, wrong LOB, amount over club limit, subordinate approver) emit `ALERT` security events; authorized actions emit `INFO`.

API and UI: `payment-service/` — see [payment-service/README.md](../payment-service/README.md).

## Demo users

All passwords are `Password1!`. Login names follow `{user_id}@ssi.local`.

| User | Name | Role | LOB |
|------|------|------|-----|
| `mo-100` | Sarah Chen | Analyst — middle office creator | — |
| `mo-101` | James Patel | Analyst — middle office creator | — |
| `ficc-300` | Elena Vasquez | VP — approver | FICC |
| `ficc-400` | Robert Kim | MD — approver | FICC |
| `pay-101` | Emily Rodriguez | Analyst — payment creator | FICC, FX |
| `pay-201` | Sophie Laurent | VP — funding approver | FICC, FX |
| `comp-001` / `comp-002` | Compliance analysts | Policy Pilot + live eligible-approvers | — |
| `admin-001` | Platform Administrator | Secured UIs + Policy Pilot | — |

Service accounts: `svc-instruction`, `svc-payment` (OBO to authorization-service).

Full roster, payment amount clubs, and metadata keys: `zitadel-seed/users.yaml` and [zitadel-seed/README.md](../zitadel-seed/README.md). That YAML is **seed-only**; runtime directory and eligibility use ZITADEL.

After changing `users.yaml`, re-seed ZITADEL (`zitadel-seed` container or manual seed script).
