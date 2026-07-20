[(${m.header})]
[# th:if="${m.empty}"]

No other directory users share your operational roles, groups, amount clubs, or covering LOBs.
[/]
[# th:if="${!m.empty}"]

Closest matches:
[# th:each="row : ${m.matches}"]
- **[(${row.displayName})]** (`[(${row.userId})]`) — [(${row.title})]. Overlap: [(${row.why})].
[/]
[/]
