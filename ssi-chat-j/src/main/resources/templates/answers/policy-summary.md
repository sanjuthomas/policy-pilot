**[(${m.title})]**[# th:if="${m.domain != null and !m.domain.isEmpty() and m.action != null and !m.action.isEmpty()}"] (`[(${m.domain})]` / `[(${m.action})]`)[/]

[# th:if="${m.narrative != null and !m.narrative.isEmpty()}"]
[(${m.narrative})]

[/]
[# th:if="${!#lists.isEmpty(m.requires)}"]
Requirements:
[# th:each="r : ${m.requires}"]
- **[(${r.kind})]**: [(${r.value})]
[/]

[/]
_Source: live OPA policy via authorization-service._
