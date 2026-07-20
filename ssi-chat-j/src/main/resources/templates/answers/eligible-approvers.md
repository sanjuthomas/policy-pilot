Live OPA evaluation for payment [(${m.paymentId})] ([(${m.status})], [(${m.amountText})], desk [(${m.owningLob})], [(${m.instructionSummary})]).

[# th:if="${m.blockedReason != null}"]
[(${m.blockedReason})]
[/]
[# th:if="${m.blockedReason == null}"]
[# th:if="${#lists.isEmpty(m.eligible)}"]
No users currently satisfy APPROVE for this payment.
[/]
[# th:if="${!#lists.isEmpty(m.eligible)}"]
Users who can approve this payment:

| # | Approver | Title | Policy basis |
|---|----------|-------|--------------|
[# th:each="row : ${m.eligible}"]| [(${row.index})] | [(${row.name})] | [(${row.title})] | [(${row.policyBasis})] |
[/][# th:if="${m.candidatesEvaluated != null}"]

Evaluated [(${m.candidatesEvaluated})] FUNDING_APPROVER candidate(s) from the user directory.[/]
[/]
[/]
