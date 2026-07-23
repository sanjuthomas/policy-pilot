[# th:if="${#lists.isEmpty(m.rows)}"][(${m.emptyMessage})][/][# th:if="${!#lists.isEmpty(m.rows)}"]Payment [(${m.entityId})] versions ([(${#lists.size(m.rows)})]):

| Ver | Status | Amount | Currency | Created At | Creator | Approver |
|---|---|---|---|---|---|---|
[# th:each="row : ${m.rows}"]| [(${row.versionNumber})] | [(${row.status})] | [(${row.amount})] | [(${row.currency})] | [(${row.createdAt})] | [(${row.creatorDisplay})] | [(${row.approverDisplay})] |
[/][/]
