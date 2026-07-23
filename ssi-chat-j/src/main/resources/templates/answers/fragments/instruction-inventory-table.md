Found [(${#lists.size(m.rows)})] instruction(s).

| Instruction ID | Status | LOB | Currency | Creator | Approver |
|---|---|---|---|---|---|
[# th:each="row : ${m.rows}"]| [(${row.instructionId})] | [(${row.status})] | [(${row.owningLob})] | [(${row.currency})] | [(${row.creatorDisplay})] | [(${row.approverDisplay})] |
[/]
