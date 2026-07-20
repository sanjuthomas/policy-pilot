[# th:if="${m.amount != null}"]
[# th:with="amountText=${money.formatUsdCompact(m.amount)}, comparison=${m.strictThreshold ? 'exceeding' : 'of at least'}, ceilingPhrase=${m.strictThreshold ? 'above' : 'at or above'}, lobNote=${m.coveringLob != null ? ' for desk ' + m.coveringLob : ''}"]
[# th:if="${#lists.size(m.groups) == 1}"]Users in [(${m.groups[0]})] who may approve payments [(${comparison})] [(${amountText})][(${lobNote})] (policy ceiling lookup — not a live payment evaluation):[/]
[# th:if="${#lists.size(m.groups) != 1}"]Users who may approve payments [(${comparison})] [(${amountText})][(${lobNote})] (amount-limit clubs with ceiling [(${ceilingPhrase})] [(${amountText})]: [# th:each="g,gstat : ${m.groups}"][(${g})][# th:unless="${gstat.last}"], [/][/]; policy ceiling lookup — not a live payment evaluation):[/]
[/]
[/]
[# th:if="${m.amount == null}"]
[# th:if="${m.coveringLob != null}"]Users with role FUNDING_APPROVER covering desk [(${m.coveringLob})] (policy directory — not a live payment evaluation):[/]
[# th:if="${m.coveringLob == null and #lists.size(m.groups) == 1}"]Members of [(${m.groups[0]})] (policy directory):[/]
[# th:if="${m.coveringLob == null and #lists.size(m.groups) > 1}"]Members of [# th:each="g,gstat : ${m.groups}"][(${g})][# th:unless="${gstat.last}"], [/][/] (policy directory):[/]
[# th:if="${m.coveringLob == null and #lists.isEmpty(m.groups)}"]Matching users (policy directory):[/]
[/]

[# th:if="${#lists.isEmpty(m.members)}"]
No matching users were found.
[/]
[# th:if="${!#lists.isEmpty(m.members)}"]
| User ID | Name | Title | Groups | Covering LOBs |
|---------|------|-------|--------|---------------|
[# th:each="row : ${m.members}"]| [(${row.userId != null ? row.userId : '—'})] | [(${row.displayName != null ? row.displayName : '—'})] | [(${row.title != null ? row.title : '—'})] | [(${row.groups != null ? row.groups : '—'})] | [(${row.coveringLobs != null ? row.coveringLobs : '—'})] |
[/]
[/]
