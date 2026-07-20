Live OPA evaluation for submitting payment [(${m.paymentId})] ([(${m.status})], [(${money.format(m.amount, m.currency)})], desk [(${m.owningLob})], [# th:if="${m.instructionId != null}"]backing instruction [(${m.instructionId})] ([(${m.instructionStatus})])[/][# th:if="${m.instructionId == null}"]instruction [(${m.instructionStatus})][/]).

[# th:if="${m.submitBlockedReason != null}"]
[(${m.submitBlockedReason})]
[/]
[# th:if="${m.submitBlockedReason == null}"]
[# th:if="${#lists.isEmpty(m.eligible)}"]
No eligible desk submitters were found for this payment (need `PAYMENT_CREATOR` with desk LOB matching the instruction).
[/]
[# th:if="${!#lists.isEmpty(m.eligible)}"]
Users who can submit this payment for funding approval:

[# th:with="rows=${m.eligible}"][# th:insert="~{fragments/approver-table}"][/][/]
[# th:if="${m.candidatesEvaluated != null}"]

Evaluated [(${m.candidatesEvaluated})] PAYMENT_CREATOR candidate(s) from the user directory.[/]
[/]
[/]
