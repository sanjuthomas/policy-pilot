Live OPA evaluation for payment [(${m.paymentId})] ([(${m.status})], [(${money.format(m.amount, m.currency)})], desk [(${m.owningLob})], [# th:if="${m.instructionId != null}"]backing instruction [(${m.instructionId})] ([(${m.instructionStatus})])[/][# th:if="${m.instructionId == null}"]instruction [(${m.instructionStatus})][/]).

[# th:if="${m.blockedReason != null}"]
[(${m.blockedReason})]

[# th:if="${!#lists.isEmpty(m.prospectiveEligible)}"]
After the payment is submitted (DRAFT → SUBMITTED), these users would satisfy APPROVE policy:

[# th:with="rows=${m.prospectiveEligible}"][# th:insert="~{fragments/approver-table}"][/][/]
[# th:if="${m.candidatesEvaluated != null}"]

Evaluated [(${m.candidatesEvaluated})] FUNDING_APPROVER candidate(s) from the user directory.[/]
[/]
[/]
[# th:if="${m.blockedReason == null}"]
[# th:if="${#lists.isEmpty(m.eligible)}"]
No users currently satisfy APPROVE policy for this payment.
[/]
[# th:if="${!#lists.isEmpty(m.eligible)}"]
Users who can approve this payment:

[# th:with="rows=${m.eligible}"][# th:insert="~{fragments/approver-table}"][/][/]
[# th:if="${m.candidatesEvaluated != null}"]

Evaluated [(${m.candidatesEvaluated})] FUNDING_APPROVER candidate(s) from the user directory.[/]
[/]
[/]
