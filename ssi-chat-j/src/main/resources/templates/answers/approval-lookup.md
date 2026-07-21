[# th:if="${m.missing}"]No approval record was found for that [(${m.entityNoun})] in the graph.[/][# th:if="${!m.missing}"]WHO: [(${m.who})]
[# th:if="${m.when != null}"]WHEN: [(${m.when})]
[/][# th:each="line : ${m.authLines}"][(${line})]
[/][/]
