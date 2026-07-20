[# th:switch="${m.variant}"]
[# th:case="'create_payment_yes'"]**Yes** — `[(${m.userId})]` ([(${m.displayName})]) may **create** draft payments under policy, for covering LOBs **[(${m.coveringLobs})]** within amount club(s) [(${m.amountClubs})].

OPA still checks the specific instruction (usable status, not expired) and that the amount is within your club ceiling at create time.
[/]
[# th:case="'create_payment_fo_submitter'"]**No** — you cannot **create** a draft payment.

You (`[(${m.userId})]`) hold `PAYMENT_CREATOR` with desk LOB **[(${m.deskLob})]**, which is the **front-office submit** profile. CREATE requires `MIDDLE_OFFICE`, covering LOBs, and an amount-limit club (e.g. `pay-101`).

You **can submit** an existing **[(${m.deskLob})]** draft for funding approval when the backing instruction is APPROVED.
[/]
[# th:case="'create_payment_no'"]**No** — `[(${m.userId})]` ([(${m.displayName})]) is missing what payment CREATE requires: [# th:each="g,stat : ${m.gaps}"][(${g})][# th:unless="${stat.last}"], [/][/].

Payment CREATE needs `PAYMENT_CREATOR` + `MIDDLE_OFFICE` + covering LOBs + amount club, then OPA checks the instruction and amount.

This is different from **instruction** create, which needs `INSTRUCTION_CREATOR` (e.g. mo-100).
[/]
[# th:case="'create_instruction_yes'"]**Yes** — `[(${m.userId})]` ([(${m.displayName})]) may **create** draft instructions under policy (role `INSTRUCTION_CREATOR`, group `MIDDLE_OFFICE`, title `[(${m.title})]`).

OPA still checks account LOB match, valid profit center, and duration limits for the specific instruction.
[/]
[# th:case="'create_instruction_no'"]**No** — `[(${m.userId})]` ([(${m.displayName})]) cannot **create** instructions. Missing: [# th:each="g,stat : ${m.gaps}"][(${g})][# th:unless="${stat.last}"], [/][/].[# th:if="${m.extra != null and !m.extra.isEmpty()}"][(${m.extra})][/]
[/]
[# th:case="'submit_yes'"]**Yes** — you may **submit** draft payments whose instruction owning LOB is **[(${m.deskLob})]** (your desk LOB).

OPA also requires the payment to be DRAFT and the backing instruction APPROVED and not expired.
[/]
[# th:case="'submit_mo_no_desk'"]**Partially** — `[(${m.userId})]` ([(${m.displayName})]) is a middle-office `PAYMENT_CREATOR` (create/update/cancel drafts). SUBMIT normally uses front-office desk `lob` matching the instruction. Your subject has no desk `lob`, so submit may be denied unless that attribute is set.
[/]
[# th:case="'submit_no'"]**No** — SUBMIT needs `PAYMENT_CREATOR` and desk `lob` matching the instruction owning LOB. Your subject (`[(${m.userId})]`) does not meet that profile.
[/]
[# th:case="'approve_yes'"]**Yes** — `[(${m.userId})]` ([(${m.displayName})]) may **approve** payments under policy for covering LOBs **[(${m.coveringLobs})]** within amount club(s) [(${m.amountClubs})].

For a specific payment, OPA still enforces four-eyes, reporting-line, instruction status, and amount ceiling. Ask “Do I have permission to approve payment <id>?” for a live check.
[/]
[# th:case="'approve_no'"]**No** — `[(${m.userId})]` ([(${m.displayName})]) is missing what payment APPROVE requires: [# th:each="g,stat : ${m.gaps}"][(${g})][# th:unless="${stat.last}"], [/][/].

Funding approval needs `FUNDING_APPROVER` + `MIDDLE_OFFICE` + covering LOBs + amount club, then per-payment OPA checks (four-eyes, reporting line, amount).
[/]
[# th:case="'approve_instruction_yes'"]**Yes** — `[(${m.userId})]` ([(${m.displayName})]) may **approve** instructions for desk LOB **[(${m.deskLob})]** under policy (role `INSTRUCTION_APPROVER`, title `[(${m.title})]`).

For a specific instruction, OPA still enforces four-eyes, reporting-line, and the approval-matrix title check. Ask “Do I have permission to approve instruction <id>?” for a live check.
[/]
[# th:case="'approve_instruction_no'"]**No** — `[(${m.userId})]` ([(${m.displayName})]) cannot **approve** instructions. Missing: [# th:each="g,stat : ${m.gaps}"][(${g})][# th:unless="${stat.last}"], [/][/].[# th:if="${m.extra != null and !m.extra.isEmpty()}"][(${m.extra})][/]

Instruction APPROVE needs `INSTRUCTION_APPROVER` and desk `lob` matching the instruction owning LOB (e.g. `ficc-300`). This is different from **payment** funding approval (`FUNDING_APPROVER`).
[/]
[# th:case="'need_id'"]Include a payment id when asking about a specific payment action, for example: “Do I have permission to approve payment 20260705-FX-P-534?”
[/]
[# th:case="'not_approver'"]You (`[(${m.userId})]`) do not hold `FUNDING_APPROVER`, so you cannot approve payment `[(${m.entityId})]` under current policy.
[/]
[# th:case="'pending'"]Live OPA evaluate for “can I approve payment `[(${m.entityId})]`?” is wired next (service + on-behalf-of). You hold `FUNDING_APPROVER`; the next step checks amount club, covering LOBs, four-eyes, and reporting line against that payment.
[/]
[# th:case="'pending_instruction'"]Live OPA evaluate for “can I approve instruction `[(${m.entityId})]`?” is not wired in chat yet. Directory-level instruction approve needs `INSTRUCTION_APPROVER` and desk `lob`; ask “Can I approve an instruction?” for that capability check.
[/]
[/]
