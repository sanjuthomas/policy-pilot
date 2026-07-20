| # | Approver | Title | Policy basis |
|---|----------|-------|--------------|
[# th:each="row,stat : ${rows}"]| [(${stat.count})] | [(${row.displayName != null ? row.displayName : (row.userId != null ? row.userId : '—')})] | [(${row.title != null ? row.title : '—'})] | [# th:if="${#lists.isEmpty(row.allowBasis)}"]—[/][# th:if="${!#lists.isEmpty(row.allowBasis)}"][# th:each="point,bstat : ${row.allowBasis}"][(${basis.humanizePoint(point)})][# th:unless="${bstat.last}"]; [/][/][/] |
[/]
