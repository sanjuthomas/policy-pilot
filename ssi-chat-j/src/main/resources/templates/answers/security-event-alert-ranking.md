[# th:if="${#lists.isEmpty(m.rows)}"]No policy denial alert rankings were found in the graph.[/][# th:if="${!#lists.isEmpty(m.rows)}"][# th:if="${#lists.size(m.rows) == 1}"]The user with the most [(${m.domainLabel})] ([(${m.periodLabel})]) is [(${m.rows[0].actorDisplay})] with [(${m.rows[0].alertCount})] alert(s).

[/][# th:if="${#lists.size(m.rows) > 1}"]User ranking by [(${m.domainLabel})] ([(${m.periodLabel})]): [(${#lists.size(m.rows)})] user(s).

[/]| User | User ID | Total Alerts | Payment Alerts | Instruction Alerts |
|---|---|---|---|---|
[# th:each="row : ${m.rows}"]| [(${row.actorDisplay})] | [(${row.userId})] | [(${row.alertCount})] | [(${row.paymentAlerts})] | [(${row.instructionAlerts})] |
[/][/]
