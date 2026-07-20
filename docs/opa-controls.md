# OPA policy controls

Policy Pilot’s authorization rules are expressed in **Rego** under [`opa-policy-seed/policies/`](../opa-policy-seed/policies/). They mirror controls found in large-bank SSI and cash-management operations: **segregation of duties**, **inversion of control** on reporting lines, **desk / LOB boundaries**, **delegated financial authority**, and **immutable audit** of every allow and deny.

At runtime only **authorization-service** calls OPA. Domain services receive allow/deny plus named **violation codes** and **allow_basis** reasons that flow into Mongo security events → Kafka → Neo4j for **Who / When / Why** investigation in chat.

Technical layout and curl examples: **[opa-policy-seed/README.md](../opa-policy-seed/README.md)**.

---

## Control map

```mermaid
mindmap
  root((OPA controls))
    Actors and scope
      Middle office creators
      Profit center approvers
      Payment creators
      Funding approvers
      Service accounts OBO
    Segregation of duties
      Creator cannot approve own work
      Suspend vs reactivate pairing
      Human cannot mark instruction USED
    Reporting line inversion of control
      Subordinate cannot approve manager
      Manager cannot approve direct report
      Applies instruction and payment
    Desk and LOB boundaries
      Approver LOB matches instruction
      Payment approver covers owning LOB
      Account LOB matches instruction
    Financial authority
      Amount limit clubs ZITADEL
      Absolute 100B ceiling
      Positive amounts only
    Lifecycle and validity
      State machine transitions
      Approved non expired instruction
      Standing vs SINGLE_USE USE rules
      Three year instruction horizon
    Misconfiguration detection
      Role without MIDDLE_OFFICE group
      Approver without limit club
      Invalid profit center LOB
```

---

## Design principles

| Principle | What it means in this demo | Where enforced |
|-----------|----------------------------|----------------|
| **Four-eyes** | Creator and approver must be different people on instructions and payments | `creator_is_not_approver`, `payment_creator_is_not_approver` |
| **Inversion of control** | Instruction: block supervisor ↔ subordinate on approve. Payment: block only subordinate approving manager’s payment — manager approving a report’s payment is allowed (manager stays answerable) | Instruction: both reporting-line helpers; Payment: `payment_approver_not_subordinate_of_creator` |
| **Desk integrity** | Profit-center approvers act only on their LOB; middle-office funding approvers must **cover** the instruction’s owning LOB | `same_lob_as_instruction`, `covers_lob` |
| **Delegated limits** | No one may create or approve above their ZITADEL amount club; no payment may exceed **$100 B** absolute | `amount_limits.rego`, `within_amount_limit` |
| **Lifecycle gates** | Payments cannot fund against draft, expired, or wrong-state instructions | `instruction_is_approved`, `instruction_not_expired`, transitions |
| **Privileged automation** | Only service accounts with `INSTRUCTION_MARKER` may mark instructions USED / RELEASE_USE (payment saga) | `USE`, `RELEASE_USE` + OBO delegation |
| **Deny loudly** | Policy violations emit named codes; `ALERT_*` codes escalate to compliance-grade security events | `violations.rego`, `is_alert` |

---

## Actor model

| Actor | Roles / groups | Typical actions | Scope |
|-------|----------------|-----------------|-------|
| **Middle office (instruction)** | `INSTRUCTION_CREATOR`, `MIDDLE_OFFICE` | Create, update, submit, cancel instructions | All LOBs; title Analyst–MD |
| **Profit center (instruction)** | `INSTRUCTION_APPROVER`, `lob` | Approve, reject, suspend, reactivate | Own desk LOB only (`FICC`, `FX`, `DESK_*`) |
| **Middle office (payment)** | `PAYMENT_CREATOR`, `MIDDLE_OFFICE`, `covering_lobs` | Create, update, cancel draft/submitted payments | LOBs listed in `covering_lobs` |
| **Front office (payment)** | `PAYMENT_CREATOR`, `lob` | Submit payment for desk review | `subject.lob` must equal instruction owning LOB |
| **Funding (payment)** | `FUNDING_APPROVER`, `MIDDLE_OFFICE`, amount club, `covering_lobs` | Approve / reject submitted payments | Covered LOBs + club ceiling |
| **Service (payment saga)** | `INSTRUCTION_MARKER` via OBO | `USE` / `RELEASE_USE` on instructions | No direct human access |

Instruction creators and payment operators intentionally use **different identity namespaces** (desk `ficc-*` / `mo-*` vs middle-office `pay-*`), which prevents cross-entity collusion patterns from arising through policy-allowed API calls alone.

---

## Instruction controls

| Control | Rule | Violation code | Alert? |
|---------|------|----------------|--------|
| Creator role | CREATE / UPDATE / CANCEL / SUBMIT require `INSTRUCTION_CREATOR` | `MISSING_ROLE_INSTRUCTION_CREATOR` | |
| Approver role | APPROVE / REJECT / SUSPEND / REACTIVATE require `INSTRUCTION_APPROVER` | `MISSING_ROLE_INSTRUCTION_APPROVER` | |
| Middle-office membership | Creators must be in `MIDDLE_OFFICE` group | `NOT_MIDDLE_OFFICE_GROUP` | ✓ |
| Creator title band | Only Analyst → Managing Director may mutate drafts | `CREATOR_TITLE_INELIGIBLE` | ✓ |
| Account ↔ instruction LOB | Funding account `owning_lob` must match instruction | `ACCOUNT_LOB_MISMATCH` | ✓ |
| Valid profit center | LOB must be `FICC`, `FX`, or `DESK_<name>` | `INVALID_PROFIT_CENTER` | ✓ |
| Instruction type | CREATE allows `STANDING` or `SINGLE_USE` only | `INVALID_INSTRUCTION_TYPE` | |
| Draft-only edits | UPDATE / SUBMIT only from `DRAFT` | `INVALID_INSTRUCTION_STATUS` | |
| Cancel window | CANCEL only from `DRAFT` or `SUBMITTED` | `INVALID_INSTRUCTION_STATUS` | |
| Duration ceiling | Effective → end date positive and ≤ **3 years** | `INSTRUCTION_DURATION_EXCEEDS_3Y` | ✓ |
| State machine | Valid transitions only (e.g. APPROVE from `SUBMITTED`) | `INVALID_STATE_TRANSITION` | |
| **Approver LOB match** | Approver’s `lob` must equal instruction `owning_lob` | `ALERT_LOB_MISMATCH` | ✓ |
| **Self-approval** | Creator cannot approve own instruction | `SELF_APPROVAL` | ✓ |
| **Manager → report** | Supervisor cannot approve direct report’s instruction | `ALERT_SUPERVISOR_APPROVING_SUBORDINATE` | ✓ |
| **Report → manager** | Subordinate cannot approve manager’s instruction (inversion of control) | `ALERT_SUBORDINATE_APPROVING_CREATOR` | ✓ |
| **Title seniority** | Approver title must be senior per approval matrix | `ALERT_APPROVAL_MATRIX_VIOLATION` | ✓ |
| Suspend authority | SUSPEND requires Managing Director title | `SUSPEND_REQUIRES_MANAGING_DIRECTOR` | |
| Suspend / reactivate pairing | User who suspended cannot reactivate same instruction | `SELF_REACTIVATION` | ✓ |
| Instruction USE | Only `INSTRUCTION_MARKER` service via OBO; instruction must be `APPROVED`, not expired | `ALERT_UNAUTHORIZED_SERVICE`, `ALERT_UNAPPROVED_INSTRUCTION`, `ALERT_EXPIRED_INSTRUCTION` | ✓ |
| Read access | VIEW / USE: MO via `covering_lobs`; desk/FO via matching `subject.lob`; plus creator/admin | `VIEWER_ACCESS_DENIED`, `INSTRUCTION_LOB_ACCESS_DENIED` | |

### Instruction approval matrix (title seniority)

Junior titles cannot approve work created by more senior titles on the same desk:

| Creator title | Approver must be |
|---------------|------------------|
| Analyst | Associate, VP, MD, Partner |
| Associate | VP, MD, Partner |
| Vice President | MD, Partner |
| Managing Director | Partner |

---

## Payment controls

| Control | Rule | Violation code | Alert? |
|---------|------|----------------|--------|
| **Absolute ceiling** | No payment may exceed **$100 billion** | `ALERT_AMOUNT_EXCEEDS_100B_LIMIT` | ✓ |
| **Club ceiling** | Amount ≤ subject’s ZITADEL club (`UP_TO_100_MILLION_CLUB`, `UP_TO_1_BILLION_CLUB`, `UP_TO_100_BILLION_CLUB`) | `ALERT_AMOUNT_EXCEEDS_SUBJECT_LIMIT` | ✓ |
| Limit club assigned | CREATE / UPDATE / APPROVE require a club group | `NO_LIMIT_GROUP_ASSIGNED` | ✓ |
| Instruction backing (draft) | CREATE / UPDATE: instruction `DRAFT`, `SUBMITTED`, or `APPROVED` | `ALERT_UNAPPROVED_INSTRUCTION` | ✓ |
| Instruction backing (submit) | SUBMIT: instruction must be `APPROVED` | `ALERT_UNAPPROVED_INSTRUCTION` | ✓ |
| Instruction backing (approve) | APPROVE: `APPROVED` (standing) or `USED` (single-use after submit saga) | `ALERT_UNAPPROVED_INSTRUCTION` | ✓ |
| Expired instruction | Backing instruction `end_date` not passed | `ALERT_EXPIRED_INSTRUCTION` | ✓ |
| Middle-office approver | APPROVE requires `MIDDLE_OFFICE` group | `ALERT_NOT_MIDDLE_OFFICE_GROUP` | ✓ |
| **LOB coverage** | Approver `covering_lobs` must include instruction owning LOB | `ALERT_LOB_COVERAGE_VIOLATION` | ✓ |
| **Self-approval** | Payment creator cannot approve own payment (even dual-role users) | `SELF_APPROVAL` | ✓ |
| **Report → manager** | Subordinate cannot approve payment created by their supervisor | `ALERT_SUBORDINATE_APPROVING_CREATOR` | ✓ |
| CREATE scope | `PAYMENT_CREATOR` + `MIDDLE_OFFICE` + covers LOB + positive amount within limits | (allow rule) | |
| SUBMIT scope | Front-office `PAYMENT_CREATOR` with `subject.lob` = instruction LOB | (allow rule) | |
| REJECT | Same funding team as approve; no four-eyes block on rejection | (allow rule) | |
| CANCEL | Creator may cancel `DRAFT` or `SUBMITTED` payments on covered LOBs | (allow rule) | |

### Amount-limit clubs

| ZITADEL group | Maximum payment (USD) |
|---------------|----------------------|
| `UP_TO_100_MILLION_CLUB` | $100,000,000 |
| `UP_TO_1_BILLION_CLUB` | $1,000,000,000 |
| `UP_TO_100_BILLION_CLUB` | $100,000,000,000 |
| *(absolute, all users)* | $100,000,000,000 hard cap |

---

## Reporting-line controls (inversion of control)

Banks routinely block approvals that would let **subordinates sign off on their boss’s work** (coercion / rubber-stamp upward). On **instructions**, Policy Pilot also blocks the reverse (manager approving a direct report’s instruction) — undue influence on the desk maker–checker chain.

On **payments**, the asymmetry is intentional: a funding manager **may** approve a payment created by their direct report. That keeps the manager **answerable** for the funding decision; only the upward conflict (subordinate approving the manager’s payment) is blocked.

```mermaid
flowchart LR
    subgraph blocked_instruction["Instruction APPROVE — blocked both ways"]
        M1[Manager] -->|created| I1[Instruction]
        S1[Subordinate] -.->|cannot approve| I1
        M1 -.->|cannot approve| I2[Instruction]
        S1 -->|created| I2
    end

    subgraph payment_reporting["Payment APPROVE — reporting line"]
        M2[Manager] -->|created payment| P1[Payment]
        S2[Subordinate] -.->|cannot approve| P1
        S3[Creator / report] -->|created payment| P2[Payment]
        M3[Manager / funding approver] -->|may approve| P2
    end
```

| Scenario | Instruction | Payment |
|----------|-------------|---------|
| Subordinate approves manager’s work | **Blocked** (`ALERT_SUBORDINATE_APPROVING_CREATOR`) | **Blocked** (`ALERT_SUBORDINATE_APPROVING_CREATOR`) |
| Manager approves direct report’s work | **Blocked** (`ALERT_SUPERVISOR_APPROVING_SUBORDINATE`) | **Allowed** — manager remains answerable for funding |
| Creator approves own work | **Blocked** (`SELF_APPROVAL`) | **Blocked** (`SELF_APPROVAL`) |

---

## Collusion patterns the control plane is designed to prevent

These graph investigation questions describe scenarios that **normal product execution should not produce**. Demo seeds such as [`seed_mutual_approval.py`](../ssi-demo-harness/seed_mutual_approval.py) and [`seed_cross_entity_reciprocal.py`](../ssi-demo-harness/seed_cross_entity_reciprocal.py) rewire Neo4j to simulate collusion for compliance analytics — they are not obtainable through allowed identity + OPA paths alone.

| Pattern | Description | How we prevent it | Deep dive |
|---------|-------------|-------------------|-----------|
| **Mutual instruction approval** | A approves B’s instruction and B approves A’s | **Identity SoD:** no dual creator/approver roles; approver `lob` must equal instruction `owning_lob` (OPA enforces both) | **[Showcase](sod-mutual-approval.md#instruction--prevent-mutual-approval)** |
| **Mutual payment approval** | A creates \(P_1\) / B approves; B creates \(P_2\) / A approves | **Not a primary target.** Instruction is the high-stakes control. Payments are day-to-day; four-eyes + one-way reporting line still apply. Extra separation: **only front office** may **SUBMIT** (MO creates DRAFT; FO submits; funding APPROVE) — so create → submit → approve is already a three-party path even when dual-role MO users exist | **[Showcase](sod-mutual-approval.md#payment--not-the-same-primary-target)** |
| **Subordinate approves creator** | Approver reports directly to the creator | **OPA:** `ALERT_SUBORDINATE_APPROVING_CREATOR` (instruction + payment); instruction also blocks manager→report | |
| **Cross-entity reciprocal approval** | A creates instruction / B approves; B creates payment / A approves | Separate desk vs middle-office roles; four-eyes on each entity | |
| **Dual-role self-approval** | User holds creator + approver roles | Explicit `SELF_APPROVAL` even when both roles present (defense in depth; seed avoids dual roles) | |
| **Cross-desk interference** | Approver acts outside their LOB or `covering_lobs` | `ALERT_LOB_MISMATCH`, `ALERT_LOB_COVERAGE_VIOLATION` | |
| **Limit shopping** | Payment above delegations | Club ceiling + absolute $100 B cap | |

---

## Lifecycle overview

### Instruction state machine

```mermaid
stateDiagram-v2
    direction LR

    [*] --> DRAFT: CREATE\n(mo INSTRUCTION_CREATOR)

    DRAFT --> DRAFT: UPDATE
    DRAFT --> SUBMITTED: SUBMIT
    DRAFT --> CANCELLED: CANCEL

    SUBMITTED --> APPROVED: APPROVE\n(desk INSTRUCTION_APPROVER,\nlob = owning_lob)
    SUBMITTED --> REJECTED: REJECT
    SUBMITTED --> CANCELLED: CANCEL

    APPROVED --> SUSPENDED: SUSPEND\n(MD title)
    SUSPENDED --> APPROVED: REACTIVATE\n(≠ suspender)

    APPROVED --> USED: USE\n(svc INSTRUCTION_MARKER,\nSINGLE_USE)
    USED --> APPROVED: RELEASE_USE\n(payment saga)

    APPROVED --> EXPIRED: end_date passed
    USED --> EXPIRED: end_date passed

    REJECTED --> [*]
    CANCELLED --> [*]
    EXPIRED --> [*]
```

| Status | Kind | Notes |
|--------|------|--------|
| `DRAFT` | Working | Create / update; middle office |
| `SUBMITTED` | Working | Awaiting desk approve or reject |
| `APPROVED` | Active | Payments may reference (standing) |
| `SUSPENDED` | Active hold | Reactivate returns to `APPROVED` |
| `USED` | Single-use consumed | Saga may `RELEASE_USE` → `APPROVED` |
| `REJECTED` | **Terminal** | Desk rejected from `SUBMITTED` |
| `CANCELLED` | **Terminal** | Cancelled from `DRAFT` or `SUBMITTED` only |
| `EXPIRED` | **Terminal** | Past `end_date` |

### Payment state machine

```mermaid
stateDiagram-v2
    direction LR

    [*] --> DRAFT: CREATE\n(mo PAYMENT_CREATOR)

    DRAFT --> DRAFT: UPDATE
    DRAFT --> SUBMITTED: SUBMIT\n(fo PAYMENT_CREATOR,\nlob = owning_lob)
    DRAFT --> CANCELLED: CANCEL

    SUBMITTED --> APPROVED: APPROVE\n(FUNDING_APPROVER,\ncovering_lobs + amount club)
    SUBMITTED --> REJECTED: REJECT
    SUBMITTED --> CANCELLED: CANCEL

    APPROVED --> [*]
    REJECTED --> [*]
    CANCELLED --> [*]
```

| Status | Kind | Notes |
|--------|------|--------|
| `DRAFT` | Working | Middle office create / update against a backing instruction |
| `SUBMITTED` | Working | Front office submitted for funding; awaiting approve / reject |
| `APPROVED` | **Terminal** | Funding approved (cash path complete in this demo) |
| `REJECTED` | **Terminal** | Funding rejected from `SUBMITTED` |
| `CANCELLED` | **Terminal** | Cancelled from `DRAFT` or `SUBMITTED` only |

Actors (identity SoD):

| Action | Who |
|--------|-----|
| CREATE / UPDATE / CANCEL (draft) | Middle office `PAYMENT_CREATOR` + `MIDDLE_OFFICE` + `covering_lobs` |
| SUBMIT | Front office `PAYMENT_CREATOR` with `subject.lob` = instruction `owning_lob` |
| APPROVE / REJECT | `FUNDING_APPROVER` + amount club + covers LOB; not payment creator; not subordinate of creator |

Create → submit → approve is intentionally a **three-step / multi-party** path: middle office drafts, **front office alone** submits for funding, funding approves. That operational split is the main extra control on payments; reciprocal MO funding approve is not treated like mutual instruction SoD (instruction is the high-stakes control).

Backing instruction: create allows instruction `DRAFT`/`SUBMITTED`/`APPROVED`; submit requires instruction `APPROVED` (or `USED` for single-use after saga).

### Instruction + payment (together)

```mermaid
stateDiagram-v2
    direction LR

    state "Instruction" as instr {
        [*] --> DRAFT
        DRAFT --> SUBMITTED: SUBMIT
        SUBMITTED --> APPROVED: APPROVE
        SUBMITTED --> REJECTED: REJECT
        DRAFT --> CANCELLED: CANCEL
        SUBMITTED --> CANCELLED: CANCEL
        APPROVED --> SUSPENDED: SUSPEND
        SUSPENDED --> APPROVED: REACTIVATE
        APPROVED --> USED: USE single-use via service
        USED --> APPROVED: RELEASE_USE
    }

    state "Payment" as pay {
        [*] --> PDRAFT: CREATE
        PDRAFT --> PSUBMITTED: SUBMIT
        PSUBMITTED --> PAPPROVED: APPROVE
        PSUBMITTED --> PREJECTED: REJECT
        PDRAFT --> PCANCELLED: CANCEL
        PSUBMITTED --> PCANCELLED: CANCEL
    }

    APPROVED --> PDRAFT: CREATE payment
    USED --> PSUBMITTED: SUBMIT single-use
```

OPA evaluates **every** action at the arrow: role, group, LOB, reporting line, amount, and backing instruction state must all pass before the domain service mutates Mongo.

---

## Audit and investigation

| OPA query | Purpose |
|-----------|---------|
| `/v1/data/{instruction\|payment}/lifecycle/allow` | Boolean decision |
| `…/violations` | Named denial codes (table above) |
| `…/is_alert` | Escalation-worthy violation present |
| `…/allow_basis` | Human-readable allow reasons on success |

Denied or alerted decisions become **security events** indexed into Neo4j. Policy Pilot chat answers *who approved*, *why was it allowed*, and *show ALERT events* from that trail. See **[Authorization audit trail](authorization-audit-trail.md)**.

---

## Related documentation

| Document | Contents |
|----------|----------|
| [sod-mutual-approval.md](sod-mutual-approval.md) | Showcase: Mutual Approval SoD for instruction (prevent) vs payment (FO submit + four-eyes) |
| [opa-policy-seed/README.md](../opa-policy-seed/README.md) | Rego layout, local curl evaluation |
| [authorization-audit-trail.md](authorization-audit-trail.md) | Who / When / Why in chat |
| [domain-models.md](domain-models.md) | Demo users, roles, and personas |
| [zitadel-seed/README.md](../zitadel-seed/README.md) | Groups, amount clubs, seed users |
