[# th:if="${m.shape == 'empty'}"]
No users matched `[(${m.query})]` in the policy directory. Try a user id (e.g. `pay-203`) or `Family, Given` display name.
[/]
[# th:if="${m.shape == 'ambiguous'}"]
Multiple users matched `[(${m.query})]`. Ask again with a specific user id:

[# th:each="row : ${m.matches}"]
- **[(${row.displayName})]** (`[(${row.userId})]`) — [(${row.title})]
[/]
[/]
[# th:if="${m.shape == 'single' and m.detail != null}"]
**[(${m.detail.displayName})]** (`[(${m.detail.userId})]`) — [(${m.detail.title})]

[# th:if="${m.detail.narrative != null and !m.detail.narrative.isEmpty()}"]
[(${m.detail.narrative})]

[/]
- **roles**: [(${m.detail.roles})]
- **groups**: [(${m.detail.groups})]
- **amount clubs**: [(${m.detail.amountClubs})]
- **covering LOBs**: [(${m.detail.coveringLobs})]
- **desk LOB**: [(${m.detail.deskLob})]

[# th:if="${!#lists.isEmpty(m.detail.capabilities)}"]
Derived capabilities:
[# th:each="c : ${m.detail.capabilities}"]
- **[(${c.kind})]**: [(${c.description})]
[/]

[/]
_Source: ZITADEL user directory via authorization-service (not a live OPA evaluation)._
[/]
