# Authorization audit trail (Who / When / Why)

How Policy Pilot answers approval questions with evidence grounded in OPA decisions at mutation time.

## What gets stored

Every authorized instruction or payment mutation stores an OPA **authorization block** on the security event:

| Field | Purpose |
|-------|---------|
| `details.authorization.summary` | Human-readable allow/deny sentence |
| `details.authorization.allow_basis` | List of policy checks that passed (allows only) |
| `details.authorization.violations` | Named violation codes (denials) |
| `details.authorization.subject_at_decision` | Actor snapshot at decision time |
| `event.reason` | Copy of `summary` on successful actions |

The ETL denormalizes these onto vector documents (`authorization_summary`, `authorization_basis`, `approved_at` on `instruction_state`) and Neo4j (`InstructionVersion.approved_at`, `authorization_summary`, `authorization_basis`).

## Past-tense approval audit (who *did* approve?)

**Chat behaviour (Instructions mode, approval questions):**

| Part | Source | Method |
|------|--------|--------|
| **WHO** | `approver_display` / graph | Deterministic |
| **WHEN** | `approved_at` / event timestamp | Deterministic |
| **WHY** | OPA `authorization_summary` + `allow_basis` | Gemini rewrite into readable prose (falls back to raw summary if Vertex fails) |

These questions use the **graph** retrieval strategy — not live OPA. The router distinguishes *who approved* (audit) from *who can approve* (eligibility). See [Intent Determination](intent-determination.md).

## Live eligibility (who *can* approve?)

Compliance analysts sign in at http://localhost:8096 (`comp-001` / `comp-002`, password `Password1!`). Questions like _"Who can approve payment &lt;payment-id&gt;?"_ bypass RAG and call **payment-service** (`POST /api/v1/payments/{id}/eligible-approvers`), which loads the payment, fetches backing instruction context from instruction-service, and delegates OPA batch evaluation to authorization-service. Instruction eligibility questions call **instruction-service** (`POST /api/v1/instructions/{id}/eligible-approvers`) the same way.

This path uses the **eligibility** strategy in the pipeline — live policy evaluation, not indexed history.

## Related reading

- [Architecture decisions — Why OPA?](architecture-decisions.md#why-opa)
- [Data flow](data-flow.md)
- OPA policies: `opa-policy-seed/policies/`
