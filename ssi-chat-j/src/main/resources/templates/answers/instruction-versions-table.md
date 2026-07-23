[# th:if="${#lists.isEmpty(m.rows)}"][(${m.emptyMessage})][/][# th:if="${!#lists.isEmpty(m.rows)}"]Instruction [(${m.entityId})] versions ([(${#lists.size(m.rows)})]):

| Ver | Status | Created At | Creator | Approver |
|---|---|---|---|---|
[# th:each="row : ${m.rows}"]| [(${row.versionNumber})] | [(${row.status})] | [(${row.createdAt})] | [(${row.creatorDisplay})] | [(${row.approverDisplay})] |
[/][/]
