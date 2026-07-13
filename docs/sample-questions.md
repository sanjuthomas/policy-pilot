# Sample questions

Curated natural-language questions for demoing Policy Pilot. Prefer these over inventing phrasing on the fly — small wording changes can change routing.

**Demo tags** (see [intent determination](intent-determination.md)):

| Tag | Meaning |
|-----|---------|
| **`graph`** | Planned Neo4j Cypher (counts, lists, relationships) |
| **`tools`** | Live OPA / policy directory / person entitlements |
| **`skill`** | Scripted mutation skill (create-payment with Go / No Go) |
| **`vector`** | Semantic retrieval over security-event audit text |

**Chat modes:** **Policies** for `tools` questions (sign in as `comp-001` / `Password1!`). **Payments** for create-payment **`skill`** (sign in as `pay-101` or `pay-205`). **Events** for vector audit questions. **Instructions** / **Payments** for domain graph questions.

Demo personas and seed users: **[Domain models and demo users](domain-models.md)**. Automated regression bank: **[ssi-chat/regression/questions.yaml](../ssi-chat/regression/questions.yaml)**.

---

## Graph

- _Are there any instances of approving each other's instructions?_ **`graph`**
- _Are there cases where one user created an instruction that another user approved, and that approver later created a payment on the same instruction that the original creator then approved?_ **`graph`**
- _Can you list all instructions without any payments?_ **`graph`**
- _Are there instructions approved by someone who reports directly to the creator?_ **`graph`**
- _Are there active instructions sharing the same creditor account and currency?_ **`graph`**
- _Who approved instruction X, and why was it allowed?_ **`graph`** **`vector`**
- _Can you show me the payment 20260712-FICC-P-2?_ **`graph`**

---

## Tools (live policy)

Use **Policies** mode. Sign in as compliance analyst `comp-001`.

### Normative policy summaries (OPA `policy_summary`)

- _What is the funding approval policy?_ **`tools`**
- _Can you summarize the payment approval policy?_ **`tools`**
- _What is the instruction approval policy?_ **`tools`**
- _Explain the payment creation policy_ **`tools`**
- _What is the payment rejection policy?_ **`tools`**

### Who may approve (directory — no payment ID)

- _Who has permission to approve payments worth more than $25 billion, and for which lines of business?_ **`tools`**
- _Who can approve payments of at least $1 billion?_ **`tools`**
- _Who has permission to approve payments belong to LOB FICC?_ **`tools`**
- _Who has permission to approve payments for LOB FX?_ **`tools`**
- _Who has permission to approve payments exceeding $1 million for FICC?_ **`tools`**

### Person entitlements (ZITADEL directory projection)

- _Can you list the permissions of Kowalski, Anna?_ **`tools`**
- _Summarize permissions for pay-203_ **`tools`**
- _What can Sophie Laurent do?_ **`tools`**
- _List the permissions of Wei Chen_ **`tools`**
- _Permissions for pay-204_ **`tools`**

### Live eligibility (include a real payment or instruction ID)

- _Who can approve payment Y?_ **`tools`**
- _Who can approve instruction X?_ **`tools`**

Grab IDs from the [demo harness](http://localhost:8091) or instruction/payment UIs after seeding.

---

## Skills (mutation)

Use **Payments** mode. Sign in as a middle-office payment creator (`pay-101`, `pay-205`, …) with `Password1!`.

Skills are **scripted pipelines**, not free-form agent tool loops. Create-payment always dry-runs OPA `CREATE`, shows a confirmation card, and mutates only after **Go**. Details: **[Create-payment skill](create-payment-skill.md)**.

- _Can you create a payment for instruction ID 20260705-FICC-I-31? Value date tomorrow; amount: 12 million USD._ **`skill`**
- _Can you create a payment using instruction 20260705-FX-I-12? Value date today and amount 10 million._ **`skill`**

After create, try:

- _Can you show me the payment 20260712-FICC-P-2?_ **`graph`**

---

## Vector

Use **Events** mode.

- _Show payment policy denial ALERT events today with actor and reason._ **`vector`**
- _What explanations appear in the audit trail when a payment approval is blocked because the approver reports directly to the payment creator?_ **`vector`**
- _Show ALERT events for LOB coverage violations on payments._ **`vector`**
- _Show all REJECT events this week with the rejection reason._ **`vector`**
- _Show all ALERT events for FICC instructions in the last 7 days._ **`vector`**
