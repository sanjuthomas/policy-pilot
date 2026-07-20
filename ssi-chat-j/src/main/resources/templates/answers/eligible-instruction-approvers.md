Live OPA evaluation for instruction [(${m.instructionId})] ([(${m.status})], [(${m.instructionType})], desk [(${m.owningLob})], created by [(${m.createdByUserId})] / [(${m.createdByTitle})]).

[# th:if="${m.blockedReason != null}"]
[(${m.blockedReason})]

[# th:if="${!#lists.isEmpty(m.prospectiveEligible)}"]
After submission (DRAFT → SUBMITTED), these users would satisfy APPROVE policy:

[# th:with="rows=${m.prospectiveEligible}"][# th:insert="~{fragments/approver-table}"][/][/]
[# th:if="${m.candidatesEvaluated != null}"]

Evaluated [(${m.candidatesEvaluated})] INSTRUCTION_APPROVER candidate(s) from the user directory.[/]
[/]
[/]
[# th:if="${m.blockedReason == null}"]
[# th:if="${#lists.isEmpty(m.eligible)}"]
[# th:if="${m.status == 'APPROVED'}"]This instruction is already APPROVED.[/]
[# th:if="${m.status == 'REJECTED' or m.status == 'USED' or m.status == 'EXPIRED' or m.status == 'CANCELLED'}"]This instruction is [(${m.status})] and cannot be approved.[/]
[# th:if="${m.status != 'APPROVED' and m.status != 'REJECTED' and m.status != 'USED' and m.status != 'EXPIRED' and m.status != 'CANCELLED'}"]No users currently satisfy APPROVE policy for this instruction.[/]
[/]
[# th:if="${!#lists.isEmpty(m.eligible)}"]
Users who can approve this instruction:

[# th:with="rows=${m.eligible}"][# th:insert="~{fragments/approver-table}"][/][/]
[# th:if="${m.candidatesEvaluated != null}"]

Evaluated [(${m.candidatesEvaluated})] INSTRUCTION_APPROVER candidate(s) from the user directory.[/]
[/]
[/]
