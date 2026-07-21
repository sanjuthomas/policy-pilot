[(${m.title})] ([(${#lists.size(m.rows)})]):

| Event ID | Event Time | Entity Type | Entity ID | Actor | Action |
|---|---|---|---|---|---|
[# th:each="row : ${m.rows}"]| [(${row.eventId})] | [(${row.timestamp})] | [(${row.entityType})] | [(${row.entityId})] | [(${row.actorDisplay})] | [(${row.action})] |
[/]
