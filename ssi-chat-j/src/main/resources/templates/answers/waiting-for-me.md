[# th:switch="${m.variant}"]
[# th:case="'not_approver'"]You (`[(${m.userId})]`) do not hold the `FUNDING_APPROVER` role, so no payments are waiting for your approval. Payment creators submit drafts for funding review; funding approvers authorize them.
[/]
[# th:case="'empty'"]No SUBMITTED payments currently list you (`[(${m.userId})]`) as an eligible funding approver under live OPA (four-eyes, covering LOBs, amount club, reporting line).
[/]
[# th:case="'found'"]SUBMITTED payments waiting for your funding approval (`[(${m.userId})]` — live OPA eligible-approvers check):

[# th:each="item : ${m.items}"]
- **`[(${item.paymentId})]`** — [(${money.format(item.amount, item.currency)})], desk [(${item.owningLob})][# th:if="${item.instructionId != null}"], instruction `[(${item.instructionId})]`[/]
[/]
[/]
[/]
